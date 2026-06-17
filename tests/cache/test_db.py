"""测试 cache.db 模块"""

import os
import sqlite3
from pathlib import Path

import pytest

from gdm.core.cache import db


class TestInitSchema:
    def test_creates_required_tables(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        try:
            db.init_schema(conn)
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            assert "folders" in tables
            assert "entries" in tables
        finally:
            conn.close()

    def test_pragmas_applied(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        try:
            db.init_schema(conn)
            assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        finally:
            conn.close()

    def test_auto_vacuum_incremental(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        try:
            db.init_schema(conn)
            # auto_vacuum: 0=NONE, 1=FULL, 2=INCREMENTAL
            assert conn.execute("PRAGMA auto_vacuum").fetchone()[0] == 2
        finally:
            conn.close()

    def test_idempotent(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        try:
            db.init_schema(conn)
            db.init_schema(conn)  # 第二次不应抛异常
        finally:
            conn.close()


class TestMigration:
    """测试幂等迁移：旧 schema 无 entry_count 时自动 ADD COLUMN。"""

    def test_migration_adds_entry_count(self, tmp_path):
        """用旧 schema 建表 + 写数据，再 init_schema 应补上 entry_count。"""
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        try:
            # 用旧 DDL 建表（无 entry_count）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    folder_path    TEXT PRIMARY KEY,
                    last_scan_at   INTEGER NOT NULL,
                    last_access_at INTEGER NOT NULL
                )
            """)
            conn.execute(
                "INSERT INTO folders(folder_path, last_scan_at, last_access_at) "
                "VALUES (?, ?, ?)",
                ("d/a", 100, 100),
            )
            conn.commit()

            # 幂等迁移
            db.init_schema(conn)

            # 验证列存在且默认值正确
            rows = conn.execute(
                "SELECT folder_path, entry_count FROM folders"
            ).fetchall()
            assert rows == [("d/a", 0)]

            # 重复调用不抛异常
            db.init_schema(conn)
        finally:
            conn.close()


class TestIntegrityCheck:
    def test_passes_on_healthy_db(self, tmp_path):
        db_path = tmp_path / "cache.db"
        conn = db.open_connection(db_path)
        db.init_schema(conn)
        conn.close()
        assert db.integrity_check(db_path) is True

    def test_fails_on_corrupted_db(self, tmp_path):
        db_path = tmp_path / "cache.db"
        db_path.write_bytes(b"not a sqlite database")
        assert db.integrity_check(db_path) is False


class TestRecoverIfCorrupted:
    def test_renames_corrupted_db(self, tmp_path):
        db_path = tmp_path / "cache.db"
        db_path.write_bytes(b"corrupted")
        db.recover_if_corrupted(db_path)
        assert not db_path.exists()
        siblings = list(tmp_path.glob("cache.db.corrupted-*"))
        assert len(siblings) == 1

    def test_noop_when_db_missing(self, tmp_path):
        db_path = tmp_path / "cache.db"
        db.recover_if_corrupted(db_path)  # 应不抛异常
        assert not db_path.exists()
