# 文件夹树紧凑布局 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化左侧项目面板的文件夹树，通过压缩边距、缩进、字号、隐藏标题使其外观更紧凑。

**架构:** 纯样式和布局参数修改，仅改动 `gdm/gui/project_panel.py` 中 `_init_ui()` 方法。功能逻辑完全不变。

**Tech Stack:** Python, PySide6, pytest

---

### Task 1: 应用紧凑布局样式

**Files:**
- Modify: `gdm/gui/project_panel.py:16-25`

- [ ] **Step 1: 修改 `_init_ui()` 方法**

将 `project_panel.py` 中 `_init_ui()` 的现有内容：

```python
    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("文件夹")
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)
```

改为：

```python
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # 面板边距归零

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)          # 隐藏"文件夹"列标题
        self.tree.setIndentation(10)             # 缩进从默认20→10
        self.tree.setStyleSheet("""
            QTreeWidget {
                font-size: 11px;
            }
            QTreeWidget::item {
                padding: 1px 0px;
                margin: 0px;
                border: none;
            }
            QTreeWidget::branch {
                margin: 0px;
                padding: 0px;
            }
        """)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)
```

- [ ] **Step 2: 运行测试确认无回归**

```bash
cd D:/UGit/game-dev-manager && python -m pytest tests/ -v
```

预期输出：61 passed, 1 skipped（与改动前一致）。所有功能测试不受样式变化影响。

- [ ] **Step 3: 提交修改**

```bash
cd D:/UGit/game-dev-manager
git add gdm/gui/project_panel.py
git commit -m "style: 优化文件夹树紧凑布局

隐藏列标题、压缩缩进(20→10px)、缩小字号(11px)、
面板边距归零，提升信息密度和美观度。

Co-Authored-By: Claude <noreply@anthropic.com>"
```
