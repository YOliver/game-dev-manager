"""测试 extractor.py 的解压逻辑。"""

import io
import os
import zipfile
import tarfile
import gzip
import bz2
import lzma
from pathlib import Path

import pytest

from gdm.core.extractor import (
    SUPPORTED_ARCHIVE_EXTENSIONS,
    find_archives,
    extract_archive,
    extract_all,
)


class TestSupportedExtensions:
    """测试支持的压缩包扩展名。"""

    def test_includes_common_formats(self):
        assert ".zip" in SUPPORTED_ARCHIVE_EXTENSIONS
        assert ".tar" in SUPPORTED_ARCHIVE_EXTENSIONS
        assert ".gz" in SUPPORTED_ARCHIVE_EXTENSIONS
        assert ".bz2" in SUPPORTED_ARCHIVE_EXTENSIONS
        assert ".xz" in SUPPORTED_ARCHIVE_EXTENSIONS
        assert ".tgz" in SUPPORTED_ARCHIVE_EXTENSIONS


class TestFindArchives:
    """测试 find_archives() 递归搜索压缩包。"""

    def test_finds_archives_recursively(self, tmp_path):
        d = Path(tmp_path)
        sub = d / "sub"
        sub.mkdir()
        (d / "a.zip").touch()
        (d / "b.tar").touch()
        (sub / "c.gz").touch()
        (d / "readme.txt").touch()

        result = find_archives(str(d))

        assert len(result) == 3
        assert str(d / "a.zip") in result
        assert str(d / "b.tar") in result
        assert str(sub / "c.gz") in result

    def test_empty_directory_returns_empty(self, tmp_path):
        result = find_archives(str(tmp_path))
        assert result == []

    def test_skips_unsupported_extensions(self, tmp_path):
        d = Path(tmp_path)
        (d / "readme.txt").touch()
        (d / "image.png").touch()

        result = find_archives(str(d))
        assert result == []


class TestExtractArchive:
    """测试 extract_archive() 单压缩包解压。"""

    def test_extract_zip(self, tmp_path):
        archive = tmp_path / "test.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("hello.txt", "hello world")

        result = extract_archive(str(archive))

        assert os.path.isdir(result)
        assert os.path.isfile(os.path.join(result, "hello.txt"))
        assert not os.path.exists(archive)

    def test_extract_tar(self, tmp_path):
        archive = tmp_path / "test.tar"
        with tarfile.open(archive, "w") as tf:
            info = tarfile.TarInfo("hello.txt")
            s = io.BytesIO(b"hello world")
            info.size = s.getbuffer().nbytes
            tf.addfile(info, s)

        result = extract_archive(str(archive))

        assert os.path.isdir(result)
        assert os.path.isfile(os.path.join(result, "hello.txt"))
        assert not os.path.exists(archive)

    def test_extract_gz_single_file(self, tmp_path):
        archive = tmp_path / "data.gz"
        with gzip.open(archive, "wb") as f:
            f.write(b"hello world")

        result = extract_archive(str(archive))

        assert os.path.isdir(result)
        assert os.path.isfile(os.path.join(result, "data"))
        assert not os.path.exists(archive)

    def test_extract_bz2_single_file(self, tmp_path):
        archive = tmp_path / "data.bz2"
        with bz2.open(archive, "wb") as f:
            f.write(b"hello world")

        result = extract_archive(str(archive))

        assert os.path.isdir(result)
        assert os.path.isfile(os.path.join(result, "data"))
        assert not os.path.exists(archive)

    def test_extract_tar_gz(self, tmp_path):
        import shutil
        archive = tmp_path / "test.tar.gz"
        tgz_path = tmp_path / "test.tgz"

        with tarfile.open(archive, "w:gz") as tf:
            info = tarfile.TarInfo("hello.txt")
            s = io.BytesIO(b"hello world")
            info.size = s.getbuffer().nbytes
            tf.addfile(info, s)

        shutil.copyfile(archive, tgz_path)

        result = extract_archive(str(tgz_path))
        assert os.path.isdir(result)
        assert not os.path.exists(tgz_path)

    def test_duplicate_name_adds_copy_suffix(self, tmp_path):
        archive = tmp_path / "test.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("hello.txt", "hello")

        existing_dir = tmp_path / "test"
        existing_dir.mkdir()

        result = extract_archive(str(archive))

        assert os.path.basename(result) == "test 副本"
        assert os.path.isdir(result)

    def test_unsupported_format_raises(self, tmp_path):
        archive = tmp_path / "test.unknown"
        archive.touch()

        with pytest.raises(ValueError):
            extract_archive(str(archive))


class TestExtractAll:
    """测试 extract_all() 递归解压全部。"""

    def test_extract_all_basic(self, tmp_path):
        d = Path(tmp_path)
        with zipfile.ZipFile(d / "a.zip", "w") as zf:
            zf.writestr("a.txt", "a")

        with zipfile.ZipFile(d / "b.zip", "w") as zf:
            zf.writestr("b.txt", "b")

        success, fail, failed_list = extract_all(str(d))

        assert success == 2
        assert fail == 0
        assert failed_list == []
        assert not os.path.exists(d / "a.zip")
        assert not os.path.exists(d / "b.zip")

    def test_extract_all_nested(self, tmp_path):
        d = Path(tmp_path)
        outer = d / "outer.zip"
        with zipfile.ZipFile(outer, "w") as zf:
            inner = d / "inner.zip"
            with zipfile.ZipFile(inner, "w") as if_zf:
                if_zf.writestr("data.txt", "data")
            zf.write(inner, "inner.zip")
        os.remove(inner)

        success, fail, _ = extract_all(str(d))

        assert success == 2  # outer + inner
        assert fail == 0

    def test_extract_all_no_archives(self, tmp_path):
        success, fail, _ = extract_all(str(tmp_path))
        assert success == 0
        assert fail == 0

    def test_extract_all_with_progress_callback(self, tmp_path):
        """progress_callback 应在每个压缩包处理后被调用。"""
        d = Path(tmp_path)
        with zipfile.ZipFile(d / "a.zip", "w") as zf:
            zf.writestr("a.txt", "a")
        with zipfile.ZipFile(d / "b.zip", "w") as zf:
            zf.writestr("b.txt", "b")

        calls = []
        def cb(current, total, filename):
            calls.append((current, total, filename))

        success, fail, _ = extract_all(str(d), progress_callback=cb)

        assert success == 2
        assert len(calls) >= 2
        assert calls[-1][1] >= 2
