"""交互式路径预览 - 在终端模拟选择路径，确认对白树没有断裂"""
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, IntPrompt
from rich.table import Table
import json

from .models import DialogueTree, DialogueNode, NodeType, ChoiceOption, Condition


class PathStatus(str, Enum):
    """路径状态"""
    COMPLETED = "completed"       # 成功到达结局
    BROKEN_NODE = "broken_node"   # 节点不存在
    BROKEN_CHOICE = "broken_choice"  # 所有选项条件不满足
    BROKEN_NO_NEXT = "broken_no_next"  # 节点缺少后续
    CONDITION_BLOCKED = "condition_blocked"  # 条件不满足无法进入
    LOOP_DETECTED = "loop_detected"    # 检测到循环


@dataclass
class PathResult:
    """单条路径的遍历结果"""
    path: List[str]
    choices: List[Tuple[str, str]]  # (choice_node_id, choice_text)
    status: PathStatus
    end_node_id: Optional[str] = None
    ending_text: Optional[str] = None
    error_message: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_successful(self) -> bool:
        return self.status == PathStatus.COMPLETED

    @property
    def path_display(self) -> str:
        return " → ".join(self.path)

    @property
    def choices_display(self) -> str:
        return " → ".join([c[1] for c in self.choices]) if self.choices else "无选择"

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "choices": [{"node_id": c[0], "text": c[1]} for c in self.choices],
            "status": self.status.value,
            "status_text": {
                PathStatus.COMPLETED: "✅ 成功到达结局",
                PathStatus.BROKEN_NODE: "❌ 节点不存在",
                PathStatus.BROKEN_CHOICE: "❌ 所有选项条件不满足",
                PathStatus.BROKEN_NO_NEXT: "❌ 节点缺少后续",
                PathStatus.CONDITION_BLOCKED: "❌ 条件不满足",
                PathStatus.LOOP_DETECTED: "⚠️  检测到循环",
            }[self.status],
            "end_node_id": self.end_node_id,
            "ending_text": self.ending_text,
            "error_message": self.error_message,
            "choices_display": self.choices_display,
            "path_display": self.path_display,
            "variables": self.variables,
        }


@dataclass
class PathExplorerReport:
    """路径遍历总报告"""
    tree_id: str
    tree_title: str
    total_paths: int
    successful_paths: List[PathResult]
    broken_paths: List[PathResult]
    all_paths: List[PathResult]

    @property
    def success_count(self) -> int:
        return len(self.successful_paths)

    @property
    def broken_count(self) -> int:
        return len(self.broken_paths)

    @property
    def success_rate(self) -> float:
        return self.success_count / self.total_paths if self.total_paths > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "tree_id": self.tree_id,
            "tree_title": self.tree_title,
            "summary": {
                "total_paths": self.total_paths,
                "successful_paths": self.success_count,
                "broken_paths": self.broken_count,
                "success_rate": f"{self.success_rate * 100:.1f}%",
            },
            "successful_paths": [p.to_dict() for p in self.successful_paths],
            "broken_paths": [p.to_dict() for p in self.broken_paths],
            "all_paths": [p.to_dict() for p in self.all_paths],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_markdown(self) -> str:
        lines = []
        lines.append(f"# 路径遍历报告 - {self.tree_title}")
        lines.append("")
        lines.append("## 汇总")
        lines.append("")
        lines.append("| 指标 | 数量 |")
        lines.append("|------|------|")
        lines.append(f"| 总路径数 | {self.total_paths} |")
        lines.append(f"| ✅ 成功到达结局 | {self.success_count} |")
        lines.append(f"| ❌ 路径断裂 | {self.broken_count} |")
        lines.append(f"| **成功率** | **{self.success_rate * 100:.1f}%** |")
        lines.append("")

        if self.successful_paths:
            lines.append("## ✅ 成功路径")
            lines.append("")
            for idx, result in enumerate(self.successful_paths, 1):
                lines.append(f"### 路径 {idx}")
                lines.append("")
                lines.append(f"- **选择路径**: {result.choices_display}")
                lines.append(f"- **节点路径**: {result.path_display}")
                lines.append(f"- **结局**: {result.ending_text}")
                lines.append("")

        if self.broken_paths:
            lines.append("## ❌ 断裂路径")
            lines.append("")
            for idx, result in enumerate(self.broken_paths, 1):
                lines.append(f"### 路径 {idx} - {result.status.value}")
                lines.append("")
                lines.append(f"- **选择路径**: {result.choices_display}")
                lines.append(f"- **节点路径**: {result.path_display}")
                lines.append(f"- **错误节点**: {result.end_node_id}")
                if result.error_message:
                    lines.append(f"- **错误信息**: {result.error_message}")
                lines.append("")

        return "\n".join(lines)


class PathExplorer:
    """自动路径遍历器 - 深度优先遍历所有可能的路径"""

    def __init__(self, tree: DialogueTree):
        self.tree = tree
        self.results: List[PathResult] = []

    def explore(self) -> PathExplorerReport:
        """遍历所有路径并生成报告"""
        self.results.clear()

        def dfs(node_id: str, path: List[str], choices: List[Tuple[str, str]], variables: Dict[str, Any], visited: set):
            if node_id in visited:
                self.results.append(PathResult(
                    path=list(path),
                    choices=list(choices),
                    status=PathStatus.LOOP_DETECTED,
                    end_node_id=node_id,
                    error_message=f"检测到循环，节点 {node_id} 已访问过",
                    variables=dict(variables),
                ))
                return

            node = self.tree.get_node(node_id)
            if not node:
                self.results.append(PathResult(
                    path=list(path),
                    choices=list(choices),
                    status=PathStatus.BROKEN_NODE,
                    end_node_id=node_id,
                    error_message=f"节点 {node_id} 不存在",
                    variables=dict(variables),
                ))
                return

            new_path = path + [node_id]
            new_visited = visited | {node_id}

            if node.conditions:
                for cond in node.conditions:
                    if not self._eval_condition(cond, variables):
                        unmet = [c.to_expression() for c in node.conditions if not self._eval_condition(c, variables)]
                        self.results.append(PathResult(
                            path=list(new_path),
                            choices=list(choices),
                            status=PathStatus.CONDITION_BLOCKED,
                            end_node_id=node_id,
                            error_message=f"条件不满足: {', '.join(unmet)}",
                            variables=dict(variables),
                        ))
                        return

            new_variables = dict(variables)
            if node.set_variables:
                new_variables.update(node.set_variables)

            if node.node_type == NodeType.ENDING:
                self.results.append(PathResult(
                    path=list(new_path),
                    choices=list(choices),
                    status=PathStatus.COMPLETED,
                    end_node_id=node_id,
                    ending_text=node.text,
                    variables=dict(new_variables),
                ))
                return

            if node.choices:
                available_choices = [c for c in node.choices if self._check_conditions(c.conditions, new_variables)]
                if not available_choices:
                    self.results.append(PathResult(
                        path=list(new_path),
                        choices=list(choices),
                        status=PathStatus.BROKEN_CHOICE,
                        end_node_id=node_id,
                        error_message="所有选项的条件都不满足",
                        variables=dict(new_variables),
                    ))
                    return

                for choice in available_choices:
                    new_choices = choices + [(node_id, choice.text)]
                    dfs(choice.next_node, new_path, new_choices, new_variables, new_visited)
            elif node.next_node:
                dfs(node.next_node, new_path, choices, new_variables, new_visited)
            else:
                self.results.append(PathResult(
                    path=list(new_path),
                    choices=list(choices),
                    status=PathStatus.BROKEN_NO_NEXT,
                    end_node_id=node_id,
                    error_message="节点缺少后续（既无choices也无next_node）",
                    variables=dict(new_variables),
                ))

        dfs(self.tree.start_node, [], [], {}, set())

        successful = [r for r in self.results if r.is_successful]
        broken = [r for r in self.results if not r.is_successful]

        return PathExplorerReport(
            tree_id=self.tree.tree_id,
            tree_title=self.tree.title,
            total_paths=len(self.results),
            successful_paths=successful,
            broken_paths=broken,
            all_paths=self.results,
        )

    def _check_conditions(self, conditions: Optional[List[Condition]], variables: Dict[str, Any]) -> bool:
        """检查条件是否满足"""
        if not conditions:
            return True
        return all(self._eval_condition(c, variables) for c in conditions)

    def _eval_condition(self, condition: Condition, variables: Dict[str, Any]) -> bool:
        """评估单个条件"""
        value = variables.get(condition.variable)

        if condition.operator == "==":
            result = value == condition.value
        elif condition.operator == "!=":
            result = value != condition.value
        elif condition.operator == ">":
            result = value > condition.value if value is not None else False
        elif condition.operator == "<":
            result = value < condition.value if value is not None else False
        elif condition.operator == ">=":
            result = value >= condition.value if value is not None else False
        elif condition.operator == "<=":
            result = value <= condition.value if value is not None else False
        elif condition.operator == "in":
            result = value in condition.value if isinstance(condition.value, (list, set)) else False
        else:
            result = False

        return not result if condition.negation else result


class DialoguePreviewer:
    """交互式对白预览器

    功能：
    1. 从起始节点开始，逐行显示对白
    2. 遇到选择时让用户输入选项
    3. 显示当前路径历史
    4. 检测并提示路径断裂
    """

    def __init__(self, tree: DialogueTree, console: Optional[Console] = None):
        self.tree = tree
        self.console = console or Console()
        self.current_node_id: str = tree.start_node
        self.path_history: List[str] = [tree.start_node]
        self.variables: Dict[str, Any] = {}
        self.choice_history: List[tuple[str, str]] = []  # (node_id, choice_text)

    def start(self):
        """开始交互式预览"""
        self.console.print(Panel.fit(
            f"[bold cyan]🎬 对白树预览[/bold cyan]\n"
            f"[dim]场景: {self.tree.title}[/dim]\n"
            f"[dim]输入 q 退出，输入 h 查看历史路径[/dim]",
            border_style="cyan",
        ))
        self.console.print()

        while True:
            node = self.tree.get_node(self.current_node_id)
            if not node:
                self._print_error(f"❌ 路径断裂！节点 {self.current_node_id} 不存在")
                self._print_path_summary()
                return

            if not self._check_conditions(node.conditions):
                self._print_error(f"⚠️  条件不满足，无法进入节点 {node.node_id}")
                unmet = [c.to_expression() for c in (node.conditions or []) if not self._eval_condition(c)]
                self.console.print(f"   未满足条件: {', '.join(unmet)}")
                self._print_path_summary()
                return

            if node.set_variables:
                for var, val in node.set_variables.items():
                    self.variables[var] = val
                    self.console.print(f"[dim]  [设置变量] {var} = {val!r}[/dim]")
                self.console.print()

            self._display_node(node)

            if node.node_type == NodeType.ENDING:
                self.console.print()
                self.console.print(Panel.fit(
                    "[bold green]🏁 到达结局[/bold green]",
                    border_style="green",
                ))
                self._print_path_summary()
                return

            if node.choices:
                available_choices = [c for c in node.choices if self._check_conditions(c.conditions)]
                if not available_choices:
                    self._print_error("❌ 没有可用选项，路径断裂！")
                    self.console.print("   所有选项的条件都不满足")
                    self._print_path_summary()
                    return

                choice = self._prompt_choice(available_choices)
                if choice is None:
                    continue

                self.choice_history.append((node.node_id, choice.text))
                self.current_node_id = choice.next_node
                self.path_history.append(choice.next_node)
                self.console.print()
            elif node.next_node:
                self.current_node_id = node.next_node
                self.path_history.append(node.next_node)
            else:
                self._print_error("❌ 节点缺少后续，路径断裂！")
                self.console.print("   此节点既无选项也无next_node")
                self._print_path_summary()
                return

    def _display_node(self, node: DialogueNode):
        """显示节点内容"""
        style_map = {
            NodeType.DIALOGUE: "bold white",
            NodeType.NARRATION: "italic dim",
            NodeType.CHOICE: "bold yellow",
            NodeType.ENDING: "bold green",
        }
        style = style_map.get(node.node_type, "white")

        if node.node_type == NodeType.DIALOGUE and node.speaker:
            self.console.print(f"[bold magenta]{node.speaker}[/bold magenta]: ", end="")
            self.console.print(Text(node.text, style=style))
        elif node.node_type == NodeType.NARRATION:
            self.console.print(Text(f"({node.text})", style=style))
        elif node.node_type == NodeType.ENDING:
            self.console.print(Text(node.text, style=style))
        else:
            self.console.print(Text(node.text, style=style))

        if node.fear_intensity:
            intensity_emoji = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢",
            }
            emoji = intensity_emoji.get(node.fear_intensity.value, "")
            self.console.print(f"[dim]  恐惧强度: {emoji} {node.fear_intensity.value}[/dim]")

        if node.dialogue_type:
            type_label = {
                "tension": "紧张情节",
                "exposition": "解释说明",
                "buffer": "缓冲过渡",
            }
            label = type_label.get(node.dialogue_type.value, node.dialogue_type.value)
            self.console.print(f"[dim]  节点类型: {label}[/dim]")

        if node.conditions:
            cond_texts = [c.to_expression() for c in node.conditions]
            self.console.print(f"[dim]  进入条件: {', '.join(cond_texts)}[/dim]")

    def _prompt_choice(self, choices: List[ChoiceOption]) -> Optional[ChoiceOption]:
        """提示用户选择"""
        self.console.print()
        self.console.print("[bold yellow]请选择:[/bold yellow]")
        for idx, choice in enumerate(choices, 1):
            if choice.conditions:
                cond_text = f" [dim](需要: {', '.join(c.to_expression() for c in choice.conditions)})[/dim]"
            else:
                cond_text = ""
            self.console.print(f"  {idx}. {choice.text}{cond_text}")

        while True:
            user_input = Prompt.ask(
                "\n[cyan]输入选项序号[/cyan]",
                console=self.console,
                show_default=False,
            )

            if user_input.lower() == "q":
                self.console.print("\n[yellow]已退出预览[/yellow]")
                self._print_path_summary()
                sys.exit(0)
            elif user_input.lower() == "h":
                self._print_history()
                continue
            elif user_input.lower() == "v":
                self._print_variables()
                continue

            try:
                idx = int(user_input) - 1
                if 0 <= idx < len(choices):
                    return choices[idx]
                else:
                    self.console.print(f"[red]请输入 1-{len(choices)} 之间的数字[/red]")
            except ValueError:
                self.console.print("[red]请输入有效的数字[/red]")

    def _check_conditions(self, conditions: Optional[List[Condition]]) -> bool:
        """检查条件是否满足"""
        if not conditions:
            return True
        return all(self._eval_condition(c) for c in conditions)

    def _eval_condition(self, condition: Condition) -> bool:
        """评估单个条件"""
        value = self.variables.get(condition.variable)

        if condition.operator == "==":
            result = value == condition.value
        elif condition.operator == "!=":
            result = value != condition.value
        elif condition.operator == ">":
            result = value > condition.value if value is not None else False
        elif condition.operator == "<":
            result = value < condition.value if value is not None else False
        elif condition.operator == ">=":
            result = value >= condition.value if value is not None else False
        elif condition.operator == "<=":
            result = value <= condition.value if value is not None else False
        elif condition.operator == "in":
            result = value in condition.value if isinstance(condition.value, (list, set)) else False
        else:
            result = False

        return not result if condition.negation else result

    def _print_error(self, message: str):
        """打印错误信息"""
        self.console.print()
        self.console.print(Panel.fit(
            f"[bold red]{message}[/bold red]",
            border_style="red",
        ))

    def _print_history(self):
        """打印路径历史"""
        self.console.print()
        table = Table(title="路径历史", show_lines=False, border_style="dim")
        table.add_column("#", style="dim", width=4)
        table.add_column("节点ID", style="cyan")
        table.add_column("内容", style="white")
        table.add_column("选择", style="yellow")

        for idx, node_id in enumerate(self.path_history, 1):
            node = self.tree.get_node(node_id)
            text = node.text[:40] + "..." if node and len(node.text) > 40 else (node.text if node else "")
            choice_text = ""
            for c_node_id, c_text in self.choice_history:
                if c_node_id == self.path_history[idx - 2] if idx > 1 else None:
                    choice_text = c_text[:30] + "..." if len(c_text) > 30 else c_text
                    break
            table.add_row(str(idx), node_id, text, choice_text)

        self.console.print(table)

    def _print_variables(self):
        """打印当前变量状态"""
        self.console.print()
        if self.variables:
            table = Table(title="当前变量", show_lines=False, border_style="dim")
            table.add_column("变量", style="cyan")
            table.add_column("值", style="white")
            for var, val in sorted(self.variables.items()):
                table.add_row(var, str(val))
            self.console.print(table)
        else:
            self.console.print("[dim]  暂无变量[/dim]")

    def _print_path_summary(self):
        """打印路径摘要"""
        self.console.print()
        self.console.print(f"[dim]路径摘要: {' → '.join(self.path_history)}[/dim]")
        self.console.print(f"[dim]共 {len(self.path_history)} 个节点，{len(self.choice_history)} 次选择[/dim]")
