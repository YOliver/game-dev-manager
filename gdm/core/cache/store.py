"""DB CRUD + 递归查询 + LRU 淘汰。

硬性规则：所有公开函数 conn 由调用方传入。
本模块不持有任何模块级 connection。
"""

import sqlite3
from typing import Iterable, List, Optional, Tuple

from gdm.core.cache import CachedEntry
from gdm.core.cache import db


def upsert_folder(conn: sqlite3.Connection, folder_path: str, now: int) -> None:
    """插入或刷新 folders 行。调用方负责 commit。"""
    conn.execute(
        """
        INSERT INTO folders(folder_path, last_scan_at, last_access_at)
        VALUES (?, ?, ?)
        ON CONFLICT(folder_path) DO UPDATE SET
            last_scan_at = excluded.last_scan_at,
            last_access_at = excluded.last_access_at
        """,
        (folder_path, now, now),
    )


def touch_folders_under(conn: sqlite3.Connection, root: str, now: int) -> None:
    """更新 root 及其所有后代叶子目录的 last_access_at。"""
    prefix = root + "/%"
    conn.execute(
        """
        UPDATE folders SET last_access_at = ?
        WHERE folder_path = ? OR folder_path LIKE ?
        """,
        (now, root, prefix),
    )
    conn.commit()


def mark_scan_done(
    conn: sqlite3.Connection, folder_paths: Iterable[str], now: int
) -> None:
    """标记若干叶子目录扫描完成（UPSERT folders 行）。"""
    rows = [(p, now, now) for p in folder_paths]
    conn.executemany(
        """
        INSERT INTO folders(folder_path, last_scan_at, last_access_at)
        VALUES (?, ?, ?)
        ON CONFLICT(folder_path) DO UPDATE SET
            last_scan_at = excluded.last_scan_at,
            last_access_at = excluded.last_access_at
        """,
        rows,
    )
    conn.commit()


def upsert_entry(conn: sqlite3.Connection, e: CachedEntry) -> None:
    """插入或刷新 entries 行。调用方负责 commit。"""
    conn.execute(
        """
        INSERT INTO entries(
            folder_path, file_name, mtime_ns, size,
            width, height, format, color_mode,
            thumb_blob, thumb_mtime_ns
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(folder_path, file_name) DO UPDATE SET
            mtime_ns = excluded.mtime_ns,
            size = excluded.size,
            width = excluded.width,
            height = excluded.height,
            format = excluded.format,
            color_mode = excluded.color_mode,
            thumb_blob = excluded.thumb_blob,
            thumb_mtime_ns = excluded.thumb_mtime_ns
        """,
        (
            e.folder_path, e.file_name, e.mtime_ns, e.size,
            e.width, e.height, e.format, e.color_mode,
            e.thumb_blob, e.thumb_mtime_ns,
        ),
    )


def get_entries(
    conn: sqlite3.Connection, root: str, *, recursive: bool = False
) -> List[CachedEntry]:
    """返回 root 下的缓存条目。

    Args:
        conn: 数据库连接
        root: 目录路径（已规范化）
        recursive: True 时递归包含所有子目录；False 时仅当前目录

    Returns:
        CachedEntry 列表
    """
    if recursive:
        prefix = root + "/%"
        rows = conn.execute(
            """
            SELECT folder_path, file_name, mtime_ns, size,
                   width, height, format, color_mode,
                   thumb_blob, thumb_mtime_ns
            FROM entries
            WHERE folder_path = ? OR folder_path LIKE ?
            """,
            (root, prefix),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT folder_path, file_name, mtime_ns, size,
                   width, height, format, color_mode,
                   thumb_blob, thumb_mtime_ns
            FROM entries
            WHERE folder_path = ?
            """,
            (root,),
        ).fetchall()
    return [
        CachedEntry(
            folder_path=r[0], file_name=r[1], mtime_ns=r[2], size=r[3],
            width=r[4] if r[4] is not None else 0,
            height=r[5] if r[5] is not None else 0,
            format=r[6] or "UNKNOWN",
            color_mode=r[7] or "UNKNOWN",
            thumb_blob=r[8],
            thumb_mtime_ns=r[9],
        )
        for r in rows
    ]


def delete_entries(
    conn: sqlite3.Connection, keys: Iterable[Tuple[str, str]]
) -> None:
    """删除 entries 行。调用方负责 commit。"""
    conn.executemany(
        "DELETE FROM entries WHERE folder_path = ? AND file_name = ?",
        list(keys),
    )


def delete_folders_under(conn: sqlite3.Connection, root: str) -> None:
    """删除 root 及所有后代 folders 行（CASCADE 清理 entries）。"""
    prefix = root + "/%"
    conn.execute(
        "DELETE FROM folders WHERE folder_path = ? OR folder_path LIKE ?",
        (root, prefix),
    )
    conn.commit()


def evict_lru_if_needed(conn: sqlite3.Connection) -> None:
    """folders 行数超过 MAX_CACHED_FOLDERS 时淘汰最旧的若干行。"""
    count_row = conn.execute("SELECT COUNT(*) FROM folders").fetchone()
    if not count_row:
        return
    count = count_row[0]
    if count <= db.MAX_CACHED_FOLDERS:
        return
    excess = count - db.MAX_CACHED_FOLDERS
    victims = [
        row[0]
        for row in conn.execute(
            """
            SELECT folder_path FROM folders
            ORDER BY last_access_at ASC
            LIMIT ?
            """,
            (excess,),
        )
    ]
    conn.executemany(
        "DELETE FROM folders WHERE folder_path = ?",
        [(v,) for v in victims],
    )
    conn.commit()


def clear_all(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM entries")
    conn.execute("DELETE FROM folders")
    conn.commit()


def _norm_path_parent(path: str) -> Optional[str]:
    """返回标准化路径的父目录，根目录返回 None。

    >>> _norm_path_parent("d/sub")
    'd'
    >>> _norm_path_parent("d")
    None
    """
    idx = path.rfind("/")
    if idx <= 0:
        return None
    return path[:idx]


def _ensure_ancestor_folders(conn: sqlite3.Connection, root: str) -> None:
    """为 root 下所有叶子目录的缺失祖先目录补充 folders 行。"""
    norm_root = root.rstrip("/")

    # 收集 root 下所有已有 folder_path
    existing = {
        r[0] for r in conn.execute(
            "SELECT folder_path FROM folders WHERE folder_path = ? OR folder_path LIKE ?",
            (norm_root, norm_root + "/%"),
        ).fetchall()
    }

    # 计算所有需要存在的祖先路径
    ancestors = set()
    for path in existing:
        while True:
            parent = _norm_path_parent(path)
            if parent is None or parent in ancestors or parent in existing:
                break
            if not parent.startswith(norm_root):
                break
            ancestors.add(parent)
            path = parent

    if not ancestors:
        return

    # 批量插入缺失的祖先行
    conn.executemany(
        "INSERT OR IGNORE INTO folders (folder_path, last_scan_at, last_access_at) VALUES (?, 0, 0)",
        [(a,) for a in sorted(ancestors)],
    )
    conn.commit()


def update_folder_counts(conn: sqlite3.Connection, root: str) -> None:
    """统计 root 下各目录的递归 entry 数量并更新 folders.entry_count。"""
    _ensure_ancestor_folders(conn, root)
    conn.execute("""
        UPDATE folders
        SET entry_count = (
            SELECT COUNT(*)
            FROM entries
            WHERE entries.folder_path = folders.folder_path
               OR entries.folder_path LIKE (folders.folder_path || '/%')
        )
        WHERE folder_path = ? OR folder_path LIKE ?
    """, (root, root + "/%"))
    conn.commit()
