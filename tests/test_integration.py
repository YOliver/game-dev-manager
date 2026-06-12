"""GDM 集成测试。"""

import pytest
from pathlib import Path


def test_full_workflow(tmp_path):
    """测试完整工作流：扫描 → 重命名 → 保存项目。"""
    # 创建测试图片
    from PIL import Image
    img = Image.new("RGB", (32, 32))
    img.save(tmp_path / "test1.png")
    img.save(tmp_path / "test2.png")

    # 扫描
    from gdm.core.scanner import scan
    sprites = scan(str(tmp_path), recursive=False)
    assert len(sprites) == 2

    # 重命名预览
    from gdm.core.renamer import preview
    from gdm.core.models import RenameRule, RenameMode
    rule = RenameRule(mode=RenameMode.PREFIX_NUMBER, prefix="sprite")
    results = preview(sprites, rule)
    assert "sprite_001.png" in results[0][1]

    # 保存项目
    from gdm.core.project import save, load
    from gdm.core.models import Project
    project = Project(root_path=str(tmp_path))
    save(project, str(tmp_path / ".gdm.json"))

    loaded = load(str(tmp_path / ".gdm.json"))
    assert loaded is not None
    assert loaded.root_path == str(tmp_path)
