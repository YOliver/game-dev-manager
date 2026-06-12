# 缩略图自适应网格排列设计

## 概述

Game Dev Manager 的缩略图视图目前使用固定网格宽度（160px），窗口缩放时缩略图行
尾留有大量空白。本设计将网格宽度从硬编码常量改为窗口宽度自适应计算，让缩略图填
满每行可用空间。

## 改动范围

仅涉及 `gdm/gui/thumbnail_view.py` 一个文件，不修改任何外部接口。

## 核心机制

窗口尺寸变化时，通过以下逻辑计算最优网格宽度：

1. 获取 `QListWidget.viewport().width()` 作为可用宽度
2. 用 `可用宽度 ÷ (基础网格宽度 + 间距)` 估算列数
3. 用 `(可用宽度 ÷ 列数) - 间距` 算出实际网格宽度，使元素均匀分布
4. 将结果限定在合理范围 `[MIN_WIDTH, MAX_WIDTH]` 内
5. 如果被 clamp 了，重新调整列数后再次计算

## 详细计算逻辑

```
available_width = viewport.width()
SPACING = 8
BASE_GRID_WIDTH = 160

cols = max(1, available_width // (BASE_GRID_WIDTH + SPACING))
grid_width = (available_width // cols) - SPACING
grid_width = clamp(grid_width, MIN_WIDTH, MAX_WIDTH)

# 如被 clamp，重新确定列数
cols = max(1, available_width // (grid_width + SPACING))
grid_width = (available_width // cols) - SPACING
```

### 边界值

| 常量 | 值 | 说明 |
|------|----|------|
| `MIN_WIDTH` | 140 | 最小网格宽，保证文字区可读 |
| `MAX_WIDTH` | 176 | 最大网格宽，防止间距过大 |
| `BASE_GRID_WIDTH` | 160 | 基础值，用于初始列数推算 |
| `GRID_HEIGHT` | 184 | 固定不变，垂直方向不受影响 |

## 坐标计算

### sizeHint

对于 IconMode，`setGridSize()` 是实际控制布局的参数，`sizeHint()` 返回值作为保
护。为保持一致性，返回当前网格宽度值（在 delegate 中用实例变量持有）。

### paint 中的矩形区域

绘制代码中使用 `option.rect.width()`（即单元格的当前宽度）替代硬编码的
`GRID_WIDTH`：

| 区域 | 公式 |
|------|------|
| 图标水平居中 | `rect.x() + (rect.width() - ICON_SIZE) // 2` |
| 文字区域宽度 | `rect.width() - 8` |
| 文字区域位置 | `rect.x() + 4` |

### ICON_SIZE 维持 128 不变

缩略图始终以 128×128 正方形显示，`QListWidget.setIconSize()` 不变，异步加载缓存
不受影响。网格宽度变化只影响格子间距和文字区域。

## 布局触发方式

在 `ThumbnailView` 中重写 `resizeEvent`：

- **首次 resize**：立即触发 `_relayout()`
- **连续拖拽**：用 `QTimer.singleShot(80)` 防抖，停止拖拽后执行一次
- **重排操作**：计算新网格宽度 → `setGridSize()` → 恢复滚动条位置

## 滚动位置保持

`setGridSize()` 会导致 QListWidget 重排，滚动位置可能跳变。在 `_relayout()` 末尾
保存并恢复 `verticalScrollBar().value()`。

## 边界情况处理

| 场景 | 处理方式 |
|------|----------|
| 窗口极窄（< MIN_WIDTH） | `clamp` + `max(1, ...)` 保证至少 1 列 |
| 加载完成后首次渲染 | 首次 resizeEvent 自动触发布局 |
| 滚动条出现/消失 | resizeEvent 响应，防抖后重算 |
| 无精灵图数据 | `_relayout` 在 `_sprites` 为空时跳过 |
| setGridSize 触发内部布局 | 这是 QListWidget 标准行为，不会产生循环 |

## 测试方案

### 单元测试（`_relayout` 计算逻辑）

- 给定不同 `available_width` 输入，验证返回的列数和网格宽度正确
- 验证边界值 clamp 行为（窄窗口、超宽窗口）
- 验证回调中网格宽度不会低于 140 或超过 176

### 手动测试

- 在不同窗口宽度下确认缩略图排列正常，行尾空白减少
- 连续拖拽窗口大小，确认防抖机制生效，无高频闪烁
- 检查超长文件名在动态宽度下的省略行为
- 检查有大数量图片时的重排性能
- 检查滚动位置在重排后是否保持

## 依赖项

无新增依赖。

## 未纳入范围

- 图标大小自适应（ICON_SIZE 保持 128 不变）
- 用户手动缩放功能（Ctrl+滚轮等）
- 网格居中对齐（保持左对齐）
