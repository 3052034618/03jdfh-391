"""交互式路径预览 - 在终端模拟选择路径，确认对白树没有断裂"""
import sys
from typing import List, Dict, Optional, Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, IntPrompt
from rich.table import Table

from .models import DialogueTree, DialogueNode, NodeType, ChoiceOption, Condition


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
