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
