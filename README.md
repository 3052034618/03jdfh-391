# 🎭 对白树自检工具 (Dialogue Tree Checker)

面向叙事程序开发者的命令行对白树自检工具，专门在版本提交前检查心理恐怖分支是否可走通。

## ✨ 功能特性

### 🔍 三类检测结果

1. **🚫 死路分支** - 指出玩家选择某个回答后没有后续台词，适合快速修补试玩中突然黑屏或沉默的问题
2. **⚔️ 条件冲突** - 提示同一段对白同时要求"主角记得真相"和"主角尚未发现照片"，避免剧情逻辑互相打架
3. **🎵 恐惧节奏异常** - 按分支列出连续高压、连续解释、缺少缓冲的段落，帮助调整恐怖节奏

### 🎮 其他功能

- **交互式预览** - 在终端里模拟选择路径，确认对白树接入游戏前没有明显断裂
- **统计信息** - 查看对白树的节点分布、路径数量、节奏分布等详细数据
- **文件列表** - 快速浏览所有对白文件的基本信息

## 📦 安装

```bash
pip install -e .
```

## 🚀 快速开始

### 1. 初始化示例文件

```bash
dt-check init
```

这会在 `./dialogues` 目录下创建一个示例对白文件 `example_scene.json`。

### 2. 检查对白树

```bash
# 检查默认目录 ./dialogues
dt-check check

# 检查指定文件
dt-check check dialogues/example_scene.json

# 检查指定目录
dt-check check path/to/dialogues

# 显示所有结果（包括通过的）
dt-check check --show-all

# 自定义节奏阈值
dt-check check --max-continuous-high 2 --max-continuous-exposition 2
```

### 3. 交互式预览

```bash
dt-check preview dialogues/example_scene.json
```

在预览模式下：
- 输入选项序号进行选择
- 输入 `h` 查看历史路径
- 输入 `v` 查看当前变量状态
- 输入 `q` 退出预览

### 4. 列出对白文件

```bash
dt-check list

# 显示详细信息
dt-check list --verbose
```

### 5. 查看统计信息

```bash
dt-check stats dialogues/example_scene.json
```

## 📝 对白文件格式

对白文件采用JSON格式，以下是完整的格式规范：

```json
{
  "tree_id": "scene_001",
  "title": "场景标题",
  "description": "场景描述（可选）",
  "start_node": "n_001",
  "nodes": {
    "n_001": {
      "node_id": "n_001",
      "node_type": "narration",
      "text": "旁白文本",
      "next_node": "n_002",
      "fear_intensity": "medium",
      "dialogue_type": "tension",
      "conditions": [
        {
          "variable": "has_memory",
          "operator": "==",
          "value": true,
          "negation": false
        }
      ],
      "set_variables": {
        "found_photo": true
      }
    }
  }
}
```

### 字段说明

**节点类型 (node_type):**
- `dialogue` - 角色台词，需要配合 `speaker` 字段
- `choice` - 玩家选择，需要配合 `choices` 字段
- `narration` - 旁白/心理描写
- `ending` - 结局节点

**恐惧强度 (fear_intensity):**
- `high` - 高压恐怖场景（jump scare、血腥、直面怪物）
- `medium` - 中等紧张（悬念、暗示、诡异氛围）
- `low` - 缓冲/放松（日常对话、解释剧情、安全屋）

**对白类型 (dialogue_type):**
- `tension` - 高压情节
- `exposition` - 解释说明
- `buffer` - 缓冲过渡

**条件表达式 (conditions):**
- `variable` - 变量名
- `operator` - 比较运算符: `==`, `!=`, `>`, `<`, `>=`, `<=`, `in`
- `value` - 比较值
- `negation` - 是否取反

## 🔧 命令参数

### `check` 命令

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `PATH` | 要检查的文件或目录 | `dialogues` |
| `--show-all` | 显示所有文件的结果，包括通过的 | `False` |
| `--no-summary` | 不显示汇总表格 | `False` |
| `--max-continuous-high` | 最大连续高压节点数 | `3` |
| `--max-continuous-exposition` | 最大连续解释节点数 | `3` |
| `--no-buffer-required` | 不要求高压后必须有缓冲 | `False` |
| `--fail-on-warning` | 遇到警告也返回非零退出码 | `False` |

## 🧪 测试

```bash
pytest tests/
```

## 📁 项目结构

```
dialogue_checker/
├── __init__.py           # 包初始化
├── models.py             # 数据模型定义
├── parser.py             # 文件解析器
├── checker.py            # 检查器管理器
├── preview.py            # 交互式预览
├── cli.py                # 命令行入口
└── checkers/
    ├── __init__.py
    ├── base.py           # 检查结果基础类
    ├── dead_end_checker.py      # 死路分支检测
    ├── condition_checker.py     # 条件冲突检测
    └── pace_checker.py          # 节奏异常检测
dialogues/                # 对白文件目录
tests/                    # 测试用例
```

## 📄 许可证

MIT License
