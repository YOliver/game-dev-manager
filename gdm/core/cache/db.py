"""SQLite 连接管理、schema 初始化、损坏恢复。

硬性规则：本模块不持有任何模块级 connection。
每个调用方在自己的线程里创建并关闭 connection。
"""

import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 配置常量
MAX_CACHED_FOLDERS = 200
MAX_DB_SIZE_BYTES = 1_500_000_000
THUMB_SIZE = 128
THUMB_FORMAT = "WEBP"
THUMB_QUALITY = 80
BATCH_EMIT_SIZE = 20

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS folders (
    folder_path    TEXT PRIMARY KEY,
    last_scan_at   INTEGER NOT NULL,
    last_access_at INTEGER NOT NULL,
    entry_count    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS entries (
    folder_path    TEXT NOT NULL,
    file_name      TEXT NOT NULL,
    mtime_ns       INTEGER NOT NULL,
    size           INTEGER NOT NULL,
    width          INTEGER,
    height         INTEGER,
    format         TEXT,
    color_mode     TEXT,
    thumb_blob     BLOB,
    thumb_mtime_ns INTEGER,
    PRIMARY KEY (folder_path, file_name),
    FOREIGN KEY (folder_path) REFERENCES folders(folder_path) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entries_folder ON entries(folder_path);
"""


def open_connection(db_path: Optional[Path]) -> sqlite3.Connection:
    """创建 SQLite connection，应用必要的 PRAGMA。

    auto_vacuum 必须在建任何表之前设置，否则不生效。
    """
    if db_path is None:
        db_path = Path(":memory:")
    else:
        db_path = Path(db_path)
    
    is_new = not db_path.exists() or db_path.stat().st_size == 0
    conn = sqlite3.connect(str(db_path))
    if is_new:
        conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """创建表与索引（幂等）。"""
    conn.executescript(_SCHEMA_SQL)
    # 幂等迁移：旧 DB 无 entry_count 列时新增
    try:
        conn.execute(
            "ALTER TABLE folders ADD COLUMN entry_count INTEGER NOT NULL DEFAULT 0"
        )
    except sqlite3.OperationalError:
        pass  # 列已存在
    conn.commit()


def integrity_check(db_path: Path) -> bool:
    """对 DB 文件运行 PRAGMA integrity_check。

    Returns:
        True 表示完整；False 表示损坏或无法打开。
    """
    if not db_path.exists():
        return True  # 不存在不算损坏，由调用方决定是否新建
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            return row is not None and row[0] == "ok"
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False


def recover_if_corrupted(db_path: Path) -> None:
    """若 DB 损坏，重命名为 cache.db.corrupted-<timestamp>。下次调用时自动新建。"""
    if not db_path.exists():
        return
    if integrity_check(db_path):
        return
    backup = db_path.with_name(f"{db_path.name}.corrupted-{int(time.time())}")
    db_path.rename(backup)
    logger.warning("缓存 DB 损坏，已备份为 %s", backup)
