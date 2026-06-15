"""压缩包解压模块。

支持 zip, tar, gz, bz2, xz 格式的递归解压。
"""

import gzip
import bz2
import lzma
import logging
import os
import tarfile
import zipfile
from pathlib import Path
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

SUPPORTED_ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".bz2", ".xz", ".tgz"}


def find_archives(directory: str) -> List[str]:
    """递归搜索目录下的所有压缩包，按文件名排序返回路径列表。"""
    archives = []
    for root, dirs, files in os.walk(directory):
        for fname in files:
            lower = fname.lower()
            # Check compound extensions first
            if lower.endswith(".tar.gz") or lower.endswith(".tar.bz2") or lower.endswith(".tar.xz"):
                archives.append(os.path.join(root, fname))
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in SUPPORTED_ARCHIVE_EXTENSIONS:
                archives.append(os.path.join(root, fname))
    return sorted(archives)


def _get_output_dir(archive_path: str) -> str:
    """根据压缩包路径生成输出目录名，重名时添加"副本"后缀。"""
    name = os.path.basename(archive_path)
    # Strip known extensions to get base name
    lower = name.lower()
    for ext in [".tar.gz", ".tar.bz2", ".tar.xz", ".tgz"]:
        if lower.endswith(ext):
            name = name[:-len(ext)]
            break
    else:
        name = os.path.splitext(name)[0]

    parent = os.path.dirname(archive_path)
    out_dir = os.path.join(parent, name)

    if not os.path.exists(out_dir):
        return out_dir

    # 重名处理
    counter = 1
    while True:
        if counter == 1:
            candidate = os.path.join(parent, f"{name} 副本")
        else:
            candidate = os.path.join(parent, f"{name} 副本{counter}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def extract_archive(archive_path: str) -> str:
    """解压单个压缩包到同级目录，返回解压后的目录路径。

    解压完成后删除原始压缩包。
    """
    out_dir = _get_output_dir(archive_path)
    os.makedirs(out_dir, exist_ok=True)
    fname = os.path.basename(archive_path).lower()

    try:
        if fname.endswith(".zip"):
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(out_dir)
        elif fname.endswith(".tar.gz") or fname.endswith(".tgz"):
            with tarfile.open(archive_path, "r:gz") as tf:
                tf.extractall(out_dir)
        elif fname.endswith(".tar.bz2"):
            with tarfile.open(archive_path, "r:bz2") as tf:
                tf.extractall(out_dir)
        elif fname.endswith(".tar.xz"):
            with tarfile.open(archive_path, "r:xz") as tf:
                tf.extractall(out_dir)
        elif fname.endswith(".tar"):
            with tarfile.open(archive_path, "r") as tf:
                tf.extractall(out_dir)
        elif fname.endswith(".gz"):
            basename = os.path.splitext(os.path.basename(archive_path))[0]
            out_file = os.path.join(out_dir, basename)
            with gzip.open(archive_path, "rb") as f_in:
                with open(out_file, "wb") as f_out:
                    while True:
                        chunk = f_in.read(8192)
                        if not chunk:
                            break
                        f_out.write(chunk)
        elif fname.endswith(".bz2"):
            basename = os.path.splitext(os.path.basename(archive_path))[0]
            out_file = os.path.join(out_dir, basename)
            with bz2.open(archive_path, "rb") as f_in:
                with open(out_file, "wb") as f_out:
                    while True:
                        chunk = f_in.read(8192)
                        if not chunk:
                            break
                        f_out.write(chunk)
        elif fname.endswith(".xz"):
            basename = os.path.splitext(os.path.basename(archive_path))[0]
            out_file = os.path.join(out_dir, basename)
            with lzma.open(archive_path, "rb") as f_in:
                with open(out_file, "wb") as f_out:
                    while True:
                        chunk = f_in.read(8192)
                        if not chunk:
                            break
                        f_out.write(chunk)
        else:
            os.rmdir(out_dir)
            raise ValueError(f"不支持的压缩包格式: {archive_path}")

        os.remove(archive_path)
        return out_dir

    except Exception:
        # 清理可能创建的空目录
        if os.path.isdir(out_dir) and not os.listdir(out_dir):
            os.rmdir(out_dir)
        raise


def extract_all(
    directory: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Tuple[int, int, List[str]]:
    """递归解压目录下所有压缩包（含嵌套）。

    返回 (成功数, 失败数, 失败文件路径列表)。
    """
    success_count = 0
    fail_count = 0
    failed_paths: List[str] = []

    while True:
        archives = find_archives(directory)
        if not archives:
            break

        total_count = len(archives)
        any_success = False
        for archive_path in archives:
            try:
                extract_archive(archive_path)
                success_count += 1
                any_success = True
            except Exception as e:
                logger.warning(f"解压失败: {archive_path}, 错误: {e}")
                fail_count += 1
                failed_paths.append(archive_path)

            if progress_callback is not None:
                processed = success_count + fail_count
                progress_callback(processed, total_count, os.path.basename(archive_path))

        if not any_success:
            break  # all failed, avoid infinite loop

    return success_count, fail_count, failed_paths
