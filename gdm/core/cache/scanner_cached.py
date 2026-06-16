"""编排器：取缓存 → 列文件 → diff → 增量更新 → 通知 UI。

包含：路径规范化、os.walk 快照、process_diff_sync（核心同步逻辑）、
DiffWorker（QRunnable 包装）、_WorkerSignals。

硬性规则：DiffWorker 在 run() 开头创建独立 connection，结束 close()。
不与 UI 线程共享 connection。
"""

import io
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Optional

from PIL import Image
from PySide6.QtCore import QObject, QRunnable, Signal

from gdm.core.cache import CachedEntry, get_db_path
from gdm.core.cache import db, store
from gdm.core.cache.diff import FileSnapshot, compute_diff
from gdm.core.scanner import SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------- #
# 路径规范化
# ---------------------------------------------------------------------- #

def normalize_folder(p: str) -> str:
    """规范化为小写、正斜杠、无尾斜杠的绝对路径。

    Windows-only：不区分大小写的文件系统假设。
    """
    abs_p = os.path.abspath(p).replace("\\", "/").rstrip("/").lower()
    return abs_p


# ---------------------------------------------------------------------- #
# 文件系统快照
# ---------------------------------------------------------------------- #

def snapshot_folder(root: str) -> List[FileSnapshot]:
    """递归列出 root 下所有图片文件，返回 FileSnapshot 列表。

    遇到不可读目录 / 文件时跳过，不抛异常。
    """
    out: List[FileSnapshot] = []
    if not os.path.isdir(root):
        return out
    for sub_dir, _dirs, files in os.walk(root):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            full = os.path.join(sub_dir, fname)
            try:
                st = os.stat(full)
            except OSError:
                continue
            out.append(FileSnapshot(
                folder_path=normalize_folder(sub_dir),
                file_name=fname,
                mtime_ns=st.st_mtime_ns,
                size=st.st_size,
            ))
    return out


# ---------------------------------------------------------------------- #
# 单张图的元数据 + 缩略图
# ---------------------------------------------------------------------- #

def _read_metadata_and_thumb(full_path: str) -> dict:
    """读元数据 + 生成 WebP 缩略图。失败则各字段为 None / 默认值。"""
    info = {
        "width": 0, "height": 0,
        "format": "UNKNOWN", "color_mode": "UNKNOWN",
        "thumb_blob": None,
    }
    try:
        with Image.open(full_path) as img:
            info["width"], info["height"] = img.size
            info["format"] = img.format or "UNKNOWN"
            info["color_mode"] = img.mode

            # 生成 128x128 WebP 缩略图
            thumb = img.copy()
            thumb.thumbnail(
                (db.THUMB_SIZE, db.THUMB_SIZE), Image.Resampling.LANCZOS
            )
            buf = io.BytesIO()
            # WebP 不支持 P / palette 模式，先转 RGBA
            if thumb.mode not in ("RGB", "RGBA"):
                thumb = thumb.convert("RGBA")
            thumb.save(buf, db.THUMB_FORMAT, quality=db.THUMB_QUALITY)
            info["thumb_blob"] = buf.getvalue()
    except Exception as e:
        logger.warning("读取图片失败 %s: %s", full_path, e)
    return info


# ---------------------------------------------------------------------- #
# 同步版核心逻辑（供 DiffWorker 与测试复用）
# ---------------------------------------------------------------------- #

def process_diff_sync(
    conn: sqlite3.Connection,
    root: str,
    cancelled: Optional[threading.Event] = None,
    on_removed=None,
    on_batch_updated=None,
) -> None:
    """对 root 做一次完整 diff 并写回 DB。

    这是 DiffWorker 的同步实现。测试与生产代码共享。

    Args:
        conn: 已打开的 SQLite connection（本线程独占）
        root: 用户点击的目录（任何形式，会被 normalize）
        cancelled: 可选取消事件；每张图前检查
        on_removed: 可选回调 fn(List[(folder, name)])
        on_batch_updated: 可选回调 fn(List[CachedEntry])
    """
    norm_root = normalize_folder(root)
    cached = store.get_entries_recursive(conn, norm_root)
    current = snapshot_folder(root)
    added, changed, removed = compute_diff(cached, current)

    now = int(time.time())

    if removed:
        store.delete_entries(conn, removed)
        if on_removed:
            on_removed(list(removed))

    todo = list(added) + list(changed)
    batch: List[CachedEntry] = []
    touched_folders = set()
    for snap in todo:
        if cancelled is not None and cancelled.is_set():
            break
        # 确保 folder_path 存在于 folders 表（外键约束）
        store.upsert_folder(conn, snap.folder_path, now)
        full = os.path.join(snap.folder_path, snap.file_name)
        meta = _read_metadata_and_thumb(full)
        entry = CachedEntry(
            folder_path=snap.folder_path,
            file_name=snap.file_name,
            width=meta["width"], height=meta["height"],
            size=snap.size,
            format=meta["format"], color_mode=meta["color_mode"],
            mtime_ns=snap.mtime_ns,
            thumb_blob=meta["thumb_blob"],
            thumb_mtime_ns=snap.mtime_ns if meta["thumb_blob"] else None,
        )
        store.upsert_entry(conn, entry)
        touched_folders.add(snap.folder_path)
        batch.append(entry)
        if len(batch) >= db.BATCH_EMIT_SIZE:
            if on_batch_updated:
                on_batch_updated(list(batch))
            batch.clear()

    if batch and on_batch_updated:
        on_batch_updated(list(batch))

    # 标记所有涉及的叶子目录扫描完成
    all_folders = (
        touched_folders
        | {snap.folder_path for snap in current}
        | {norm_root}
    )
    store.mark_scan_done(conn, all_folders, now)
    store.evict_lru_if_needed(conn)


# ---------------------------------------------------------------------- #
# Qt 信号封装
# ---------------------------------------------------------------------- #

class _WorkerSignals(QObject):
    """DiffWorker 的信号载体（QRunnable 不能直接 emit）。"""

    entries_removed = Signal(list)   # List[(folder_path, file_name)]
    entries_updated = Signal(list)   # List[CachedEntry]
    scan_done = Signal(str)          # 用户点击的根目录


class DiffWorker(QRunnable):
    """后台 diff 任务（QThreadPool 调度）。"""

    def __init__(self, root: str) -> None:
        super().__init__()
        self.root = root
        self.signals = _WorkerSignals()
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def run(self) -> None:
        db_path = get_db_path()
        try:
            conn = db.open_connection(db_path)
        except sqlite3.DatabaseError as e:
            logger.warning("DiffWorker 无法打开缓存 DB，跳过本次 diff: %s", e)
            self.signals.scan_done.emit(self.root)
            return
        try:
            db.init_schema(conn)
            process_diff_sync(
                conn, self.root,
                cancelled=self._cancelled,
                on_removed=self.signals.entries_removed.emit,
                on_batch_updated=self.signals.entries_updated.emit,
            )
        except sqlite3.OperationalError as e:
            # 写入失败（磁盘满等）：log 后继续，不阻断 UI
            logger.warning("缓存写入失败，本次 diff 已部分完成: %s", e)
        except Exception as e:
            logger.exception("DiffWorker 异常: %s", e)
        finally:
            conn.close()
            self.signals.scan_done.emit(self.root)
