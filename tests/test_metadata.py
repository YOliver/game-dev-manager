"""测试图片元数据提取：extract()"""

import pytest
from pathlib import Path
from PIL import Image
from gdm.core.metadata import extract


class TestExtract:
    """测试 extract() 函数"""

    def test_extract_valid_png(self, tmp_path):
        """测试从有效 PNG 文件提取元数据"""
        # 创建一个 32x64 的 RGBA PNG 文件
        img = Image.new("RGBA", (32, 64), (255, 0, 0, 255))
        file_path = tmp_path / "sprite.png"
        img.save(file_path, "PNG")

        result = extract(str(file_path))

        assert result.file_name == "sprite.png"
        assert result.file_path == str(file_path)
        assert result.width == 32
        assert result.height == 64
        assert result.format == "PNG"
        assert result.color_mode == "RGBA"
        assert result.file_size > 0

    def test_extract_valid_jpeg(self, tmp_path):
        """测试从有效 JPEG 文件提取元数据"""
        img = Image.new("RGB", (100, 200), (0, 255, 0))
        file_path = tmp_path / "photo.jpg"
        img.save(file_path, "JPEG")

        result = extract(str(file_path))

        assert result.file_name == "photo.jpg"
        assert result.width == 100
        assert result.height == 200
        assert result.format == "JPEG"
        assert result.color_mode == "RGB"
        assert result.file_size > 0

    def test_extract_file_size_matches_actual(self, tmp_path):
        """测试 file_size 与实际文件大小一致"""
        img = Image.new("RGB", (10, 10), (0, 0, 0))
        file_path = tmp_path / "tiny.png"
        img.save(file_path, "PNG")

        actual_size = Path(file_path).stat().st_size
        result = extract(str(file_path))

        assert result.file_size == actual_size

    def test_extract_invalid_file_returns_partial_info(self, tmp_path):
        """测试无效图片文件时返回部分信息（文件大小可读，图片信息标注为未知）"""
        # 创建一个无效文件（不是合法图片）
        file_path = tmp_path / "not_an_image.png"
        file_path.write_text("this is not an image file")

        result = extract(str(file_path))

        # 文件基本信息应可读
        assert result.file_name == "not_an_image.png"
        assert result.file_path == str(file_path)
        assert result.file_size == Path(file_path).stat().st_size
        # 图片信息应标注为未知
        assert result.width == 0
        assert result.height == 0
        assert result.format == "UNKNOWN"
        assert result.color_mode == "UNKNOWN"

    def test_extract_nonexistent_file_raises(self):
        """测试不存在的文件会抛出异常"""
        with pytest.raises(OSError):
            extract("nonexistent_file.png")

    def test_extract_webp_format(self, tmp_path):
        """测试 WebP 格式提取"""
        img = Image.new("RGB", (50, 50), (128, 128, 128))
        file_path = tmp_path / "icon.webp"
        img.save(file_path, "WebP")

        result = extract(str(file_path))

        assert result.format == "WEBP"
        assert result.width == 50
        assert result.height == 50
