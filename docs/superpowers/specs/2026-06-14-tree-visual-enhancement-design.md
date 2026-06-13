# 目录树视觉优化设计

## 概述

两个优化：1) 修复目录树选中项文字与背景色混淆的问题；2) 将含有图片的目录名显示为绿色，辅助快速定位资源目录。

## 当前问题

- 目录树应用紧凑布局样式后，未定义 `:selected` 状态，选中项的背景色与文字颜色接近，难以辨认
- 所有目录名颜色一致，无法直观区分哪些目录包含图片资源

## 改动方案

仅修改 `gdm/gui/project_panel.py`。

### 需求 1：选中态样式

在 `_init_ui()` 的 stylesheet 中新增：

```css
QTreeWidget::item:selected {
    background-color: #0078d4;
    color: white;
}
QTreeWidget::item:selected:active {
    background-color: #0078d4;
    color: white;
}
```

蓝底白字，确保与被选中的目录名有足够对比度。

### 需求 2：含图片目录标绿色

**流程：**

```
set_root(path)
  ├─ _build_img_dirs(path) — 轻量扩展名扫描
  ├─ 构建 _img_dirs 集合
  └─ _populate_tree() 中检查每个目录 → 命中的标绿
```

**具体改动：**

| 项 | 内容 |
|------|------|
| 新增 import | `QColor`（`PySide6.QtGui`）、`SUPPORTED_EXTENSIONS`（`gdm.core.scanner`） |
| 新增属性 | `self._img_dirs: set[str]` — 含图片的目录路径集合 |
| 新增常量 | `_GREEN = QColor("#22c55e")` — 绿色字体类常量 |
| `set_root()` | 调用 `_build_img_dirs(path)` 构建集合，根节点命中则 `setForeground(0, self._GREEN)` |
| `_populate_tree()` | 对每个子目录检查 `str(entry)` 是否在 `_img_dirs` 中，是则 `setForeground(0, self._GREEN)` |

### 轻量扫描算法

实际实现不使用 `scanner.scan()`（避免 PIL 元数据开销），仅检查文件扩展名：

```python
    def _build_img_dirs(self, root_path: str) -> set[str]:
        """轻量扫描，仅检查扩展名，返回含图片的目录及所有父目录。"""
        from gdm.core.scanner import SUPPORTED_EXTENSIONS
        img_dirs: set[str] = set()
        root = Path(root_path)
        try:
            for file_path in root.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    img_dirs.add(str(file_path.parent))
        except PermissionError:
            pass
        # 补全所有父目录
        all_parents: set[str] = set(img_dirs)
        for d in img_dirs:
            parent = Path(d).parent
            while str(parent) != root_path and str(parent) not in all_parents:
                all_parents.add(str(parent))
                parent = parent.parent
        if img_dirs:
            all_parents.add(root_path)
        return all_parents
```

### 不变的部分

- 信号 `folder_selected` 不变
- 主窗口布局不变
- 目录树折叠/展开行为不变

## 验证标准

- 选中任意目录时，蓝底白字清晰可辨
- 包含图片的目录显示为绿色（直接包含或子目录包含均有效）
- 不包含图片的目录保持默认颜色
- 根目录也正确标绿（如果包含图片）
- 所有测试通过
