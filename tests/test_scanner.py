"""测试文件夹扫描：scan()"""

import pytest
from pathlib import Path
from PIL import Image
from gdm.core.scanner import scan, SUPPORTED_EXTENSIONS


class TestScan:
    """测试 scan() 函数"""

    def _create_test_images(self, directory: Path):
        """在指定目录创建测试图片文件"""
        # 创建几个不同格式的图片
        img_png = Image.new("RGBA", (32, 32), (255, 0, 0, 255))
        img_png.save(directory / "sprite1.png", "PNG")

        img_jpg = Image.new("RGB", (64, 64), (0, 255, 0))
        img_jpg.save(directory / "photo.jpg", "JPEG")

        img_webp = Image.new("RGB", (16, 16), (0, 0, 255))
        img_webp.save(directory / "icon.webp", "WebP")

    def test_scan_directory_with_images(self, tmp_path):
        """测试扫描包含图片的目录，返回正确数量的 SpriteInfo"""
        self._create_test_images(tmp_path)

        result = scan(str(tmp_path), recursive=False)

        assert len(result) == 3
        assert all(hasattr(sprite, 'file_path') for sprite in result)
        assert all(hasattr(sprite, 'file_name') for sprite in result)

    def test_scan_filters_non_image_files(self, tmp_path):
        """测试非图片文件（.txt 等）应被过滤"""
        # 创建图片文件
        self._create_test_images(tmp_path)
        # 创建非图片文件
        (tmp_path / "readme.txt").write_text("这是一个文本文件")
        (tmp_path / "data.json").write_text('{"key": "value"}')
        (tmp_path / "no_extension").write_text("无扩展名文件")

        result = scan(str(tmp_path), recursive=False)

        # 只应返回 3 个图片文件
        assert len(result) == 3
        extensions = {Path(sprite.file_name).suffix.lower() for sprite in result}
        assert extensions == {".png", ".jpg", ".webp"}

    def test_scan_recursive_false_skips_subdirectories(self, tmp_path):
        """测试 recursive=False 时不扫描子目录"""
        # 创建根目录图片
        self._create_test_images(tmp_path)
        # 创建子目录及子目录中的图片
        sub_dir = tmp_path / "subdir"
        sub_dir.mkdir()
        img_sub = Image.new("RGB", (10, 10), (128, 128, 128))
        img_sub.save(sub_dir / "sub_sprite.png", "PNG")

        result = scan(str(tmp_path), recursive=False)

        # 只应返回根目录的 3 个图片
        assert len(result) == 3
        paths = [sprite.file_path for sprite in result]
        assert all("subdir" not in p for p in paths)

    def test_scan_recursive_true_includes_subdirectories(self, tmp_path):
        """测试 recursive=True 时扫描子目录"""
        # 创建根目录图片
        self._create_test_images(tmp_path)
        # 创建子目录及子目录中的图片
        sub_dir = tmp_path / "subdir"
        sub_dir.mkdir()
        img_sub = Image.new("RGB", (10, 10), (128, 128, 128))
        img_sub.save(sub_dir / "sub_sprite.png", "PNG")
        # 创建嵌套子目录
        nested_dir = sub_dir / "nested"
        nested_dir.mkdir()
        img_nested = Image.new("RGBA", (20, 20), (255, 255, 0, 255))
        img_nested.save(nested_dir / "nested_sprite.gif", "GIF")

        result = scan(str(tmp_path), recursive=True)

        # 应返回根目录 3 个 + 子目录 1 个 + 嵌套目录 1 个 = 5 个
        assert len(result) == 5

    def test_scan_nonexistent_directory_returns_empty(self):
        """测试不存在的目录返回空列表"""
        result = scan("nonexistent_directory_12345", recursive=False)
        assert result == []

    def test_scan_empty_directory_returns_empty(self, tmp_path):
        """测试空目录返回空列表"""
        result = scan(str(tmp_path), recursive=False)
        assert result == []

    def test_supported_extensions_constant(self):
        """测试 SUPPORTED_EXTENSIONS 包含预期的扩展名"""
        expected = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
        assert SUPPORTED_EXTENSIONS == expected

    def test_scan_returns_sprite_info_with_correct_fields(self, tmp_path):
        """测试返回的 SpriteInfo 包含正确的字段值"""
        img = Image.new("RGBA", (32, 64), (255, 0, 0, 255))
        file_path = tmp_path / "test_sprite.png"
        img.save(file_path, "PNG")

        result = scan(str(tmp_path), recursive=False)

        assert len(result) == 1
        sprite = result[0]
        assert sprite.file_name == "test_sprite.png"
        assert sprite.file_path == str(file_path)
        assert sprite.width == 32
        assert sprite.height == 64
        assert sprite.format == "PNG"
        assert sprite.color_mode == "RGBA"
        assert sprite.file_size > 0

    def test_scan_case_insensitive_extensions(self, tmp_path):
        """测试扩展名大小写不敏感"""
        img = Image.new("RGB", (10, 10), (0, 0, 0))
        # 使用大写扩展名
        img.save(tmp_path / "photo.PNG", "PNG")
        img.save(tmp_path / "image.JPG", "JPEG")
        img.save(tmp_path / "icon.WEBP", "WebP")

        result = scan(str(tmp_path), recursive=False)

        assert len(result) == 3
