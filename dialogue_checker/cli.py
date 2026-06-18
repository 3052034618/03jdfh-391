"""命令行入口 - 提供检查、预览等命令"""
import sys
import os
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from . import __version__
from .checker import DialogueTreeChecker
from .checkers.base import CheckReport, CheckResult, CheckIssue, IssueType, Severity
from .preview import DialoguePreviewer
from .parser import DialogueParser, ParseError

console = Console()


def _print_banner():
    """打印工具横幅"""
    banner = Text()
    banner.append("🎭 对白树自检工具 ", style="bold cyan")
    banner.append(f"v{__version__}", style="dim")
    banner.append("\n心理恐怖叙事分支检查器", style="dim")
    console.print(banner)
    console.print()


def _format_issue(issue: CheckIssue) -> Text:
    """格式化单个问题"""
    severity_colors = {
        Severity.ERROR: "bold red",
        Severity.WARNING: "bold yellow",
        Severity.INFO: "bold blue",
    }
    type_icons = {
        IssueType.DEAD_END: "🚫",
        IssueType.CONDITION_CONFLICT: "⚔️ ",
        IssueType.PACE_ABNORMAL: "🎵",
    }

    color = severity_colors.get(issue.severity, "white")
    icon = type_icons.get(issue.type, "•")

    text = Text()
    text.append(f"{icon} [{issue.severity.value.upper()}] ", style=color)
    text.append(issue.message, style="white")
    text.append("\n")

    if issue.node_id:
        text.append(f"     节点: ", style="dim")
        text.append(issue.node_id, style="cyan")
        text.append("\n")

    if issue.node_text:
        preview = issue.node_text[:60] + "..." if len(issue.node_text) > 60 else issue.node_text
        text.append(f"     文本: ", style="dim")
        text.append(f'"{preview}"', style="italic")
        text.append("\n")

    if issue.path:
        text.append(f"     路径: ", style="dim")
        text.append(" → ".join(issue.path), style="magenta")
        text.append("\n")

    if issue.details:
        for detail in issue.details:
            if detail.strip():
                text.append(f"     - {detail}\n", style="dim")

    return text


def _print_result(result: CheckResult, show_all: bool = False):
    """打印单个文件的检查结果"""
    if not result.has_issues and not show_all:
        return

    title_style = "bold green" if not result.has_issues else "bold white"
    panel_title = Text()
    panel_title.append(f"📄 {result.tree_title}", style=title_style)
    if result.has_issues:
        panel_title.append(f"  ({len(result.issues)} 个问题)", style="dim")
    else:
        panel_title.append("  ✅ 通过", style="green")

    content = Text()
    content.append(f"文件: {result.file_path}\n", style="dim")

    if result.has_issues:
        issues_by_type = {
            IssueType.DEAD_END: [],
            IssueType.CONDITION_CONFLICT: [],
            IssueType.PACE_ABNORMAL: [],
        }
        for issue in result.issues:
            issues_by_type[issue.type].append(issue)

        type_titles = {
            IssueType.DEAD_END: ("🚫 死路分支", "bold red"),
            IssueType.CONDITION_CONFLICT: ("⚔️  条件冲突", "bold yellow"),
            IssueType.PACE_ABNORMAL: ("🎵 节奏异常", "bold blue"),
        }

        for issue_type, issues in issues_by_type.items():
            if issues:
                title, style = type_titles[issue_type]
                content.append(f"\n  {title}\n", style=style)
                content.append(f"  {'─' * 40}\n", style="dim")
                for issue in issues:
                    content.append(_format_issue(issue))
                    content.append("\n")
    else:
        content.append("\n  ✅ 所有检查通过\n", style="green")

    console.print(Panel(content, title=panel_title, border_style="cyan" if not result.has_issues else "red"))
    console.print()


def _print_summary(report: CheckReport):
    """打印检查汇总"""
    console.print()
    table = Table(title="检查汇总", show_lines=False, border_style="dim")
    table.add_column("指标", style="cyan", justify="right")
    table.add_column("数量", style="white", justify="center")

    table.add_row("检查文件数", str(report.total_files))
    table.add_row("❌ 死路分支", str(report.total_dead_ends))
    table.add_row("⚔️  条件冲突", str(report.total_condition_conflicts))
    table.add_row("🎵 节奏异常", str(report.total_pace_abnormal))
    table.add_row("总计错误", str(sum(1 for r in report.results for i in r.issues if i.severity == Severity.ERROR)), style="bold red")
    table.add_row("总计警告", str(sum(1 for r in report.results for i in r.issues if i.severity == Severity.WARNING)), style="bold yellow")

    console.print(table)

    if report.has_errors:
        console.print("\n❌ [bold red]发现严重错误，请修复后再提交版本[/bold red]")
    elif report.total_warnings > 0:
        console.print("\n⚠️  [bold yellow]发现警告，建议检查[/bold yellow]")
    else:
        console.print("\n✅ [bold green]所有检查通过！可以安全提交版本[/bold green]")


@click.group()
@click.version_option(version=__version__, prog_name="dt-check")
def cli():
    """🎭 对白树自检工具 - 心理恐怖叙事分支检查器

    在版本提交前检查对白树是否有死路分支、条件冲突和恐惧节奏异常。
    """
    pass


@cli.command()
@click.argument("path", type=click.Path(exists=True), default="dialogues")
@click.option("--show-all", is_flag=True, help="显示所有文件的结果，包括通过的")
@click.option("--no-summary", is_flag=True, help="不显示汇总表格")
@click.option("--max-continuous-high", type=int, default=3, help="最大连续高压节点数")
@click.option("--max-continuous-exposition", type=int, default=3, help="最大连续解释节点数")
@click.option("--no-buffer-required", is_flag=True, help="不要求高压后必须有缓冲")
@click.option("--fail-on-warning", is_flag=True, help="遇到警告也返回非零退出码")
def check(
    path: str,
    show_all: bool,
    no_summary: bool,
    max_continuous_high: int,
    max_continuous_exposition: int,
    no_buffer_required: bool,
    fail_on_warning: bool,
):
    """检查对白树的死路分支、条件冲突和恐惧节奏异常

    PATH 可以是单个对白文件或包含对白文件的目录，默认为 ./dialogues
    """
    _print_banner()

    pace_config = {
        "max_continuous_high": max_continuous_high,
        "max_continuous_exposition": max_continuous_exposition,
        "require_buffer_after_high": not no_buffer_required,
    }

    console.print(f"[dim]检查路径: {path}[/dim]")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("正在分析对白树...", total=None)
        checker = DialogueTreeChecker(pace_config=pace_config)
        report = checker.check_path(path)
        progress.update(task, completed=True)

    for result in report.results:
        _print_result(result, show_all)

    if not no_summary:
        _print_summary(report)

    if report.has_errors:
        sys.exit(1)
    elif fail_on_warning and report.total_warnings > 0:
        sys.exit(1)
    else:
        sys.exit(0)


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
def preview(file: str):
    """交互式预览对白树，模拟玩家选择路径

    FILE 是要预览的对白文件路径
    """
    _print_banner()

    try:
        parser = DialogueParser()
        tree = parser.load_file(file)
    except ParseError as e:
        console.print(f"[bold red]解析错误:[/bold red] {e}")
        sys.exit(1)

    previewer = DialoguePreviewer(tree, console=console)
    try:
        previewer.start()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]已中断预览[/yellow]")
        sys.exit(0)


@cli.command("list")
@click.argument("path", type=click.Path(exists=True), default="dialogues")
@click.option("--verbose", is_flag=True, help="显示详细信息")
def list_files(path: str, verbose: bool):
    """列出所有对白文件及其基本信息

    PATH 可以是单个文件或目录，默认为 ./dialogues
    """
    _print_banner()

    parser = DialogueParser()
    try:
        loaded = parser.load_single_or_directory(path)
    except ParseError as e:
        console.print(f"[bold red]错误:[/bold red] {e}")
        sys.exit(1)

    if not loaded:
        console.print("[yellow]未找到对白文件[/yellow]")
        return

    table = Table(title="对白文件列表", show_lines=False, border_style="dim")
    table.add_column("#", style="dim", width=4)
    table.add_column("文件", style="cyan")
    table.add_column("标题", style="white")
    table.add_column("节点数", justify="right")
    if verbose:
        table.add_column("起始节点", style="magenta")
        table.add_column("路径数", justify="right")

    for idx, (file_path, item) in enumerate(loaded, 1):
        if isinstance(item, ParseError):
            table.add_row(
                str(idx),
                file_path,
                Text("解析错误", style="red"),
                "-",
            )
        else:
            tree = item
            row = [
                str(idx),
                file_path,
                tree.title,
                str(len(tree.nodes)),
            ]
            if verbose:
                row.extend([
                    tree.start_node,
                    str(len(tree.get_all_paths())),
                ])
            table.add_row(*row)

    console.print(table)


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
def stats(file: str):
    """显示对白树的详细统计信息

    FILE 是对白文件路径
    """
    _print_banner()

    try:
        parser = DialogueParser()
        tree = parser.load_file(file)
    except ParseError as e:
        console.print(f"[bold red]解析错误:[/bold red] {e}")
        sys.exit(1)

    paths = tree.get_all_paths()
    edges = tree.get_all_edges()

    node_type_counts = {}
    intensity_counts = {}
    dialogue_type_counts = {}
    for node in tree.nodes.values():
        node_type_counts[node.node_type.value] = node_type_counts.get(node.node_type.value, 0) + 1
        if node.fear_intensity:
            intensity_counts[node.fear_intensity.value] = intensity_counts.get(node.fear_intensity.value, 0) + 1
        if node.dialogue_type:
            dialogue_type_counts[node.dialogue_type.value] = dialogue_type_counts.get(node.dialogue_type.value, 0) + 1

    panel_content = Text()
    panel_content.append(f"场景: {tree.title}\n", style="bold cyan")
    if tree.description:
        panel_content.append(f"描述: {tree.description}\n\n", style="dim")

    panel_content.append("📊 基本统计\n", style="bold white")
    panel_content.append(f"  总节点数: {len(tree.nodes)}\n", style="white")
    panel_content.append(f"  总边数: {len(edges)}\n", style="white")
    panel_content.append(f"  总路径数: {len(paths)}\n", style="white")
    if paths:
        avg_len = sum(len(p) for p in paths) / len(paths)
        max_len = max(len(p) for p in paths)
        min_len = min(len(p) for p in paths)
        panel_content.append(f"  平均路径长度: {avg_len:.1f}\n", style="white")
        panel_content.append(f"  最长路径: {max_len} 节点\n", style="white")
        panel_content.append(f"  最短路径: {min_len} 节点\n", style="white")

    if node_type_counts:
        panel_content.append("\n📋 节点类型分布\n", style="bold white")
        for ntype, count in sorted(node_type_counts.items()):
            panel_content.append(f"  {ntype}: {count}\n", style="white")

    if intensity_counts:
        panel_content.append("\n🔴🟡🟢 恐惧强度分布\n", style="bold white")
        for intensity, count in sorted(intensity_counts.items()):
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(intensity, "⚪")
            panel_content.append(f"  {emoji} {intensity}: {count}\n", style="white")

    if dialogue_type_counts:
        panel_content.append("\n🎭 对白类型分布\n", style="bold white")
        for dtype, count in sorted(dialogue_type_counts.items()):
            label = {"tension": "紧张情节", "exposition": "解释说明", "buffer": "缓冲过渡"}.get(dtype, dtype)
            panel_content.append(f"  {label}: {count}\n", style="white")

    console.print(Panel(panel_content, title="对白树统计", border_style="cyan"))


@cli.command()
@click.option("--output", "-o", type=click.Path(), help="输出示例文件到指定目录")
def init(output: Optional[str]):
    """创建示例对白文件目录结构"""
    _print_banner()

    target_dir = Path(output) if output else Path("dialogues")
    target_dir.mkdir(parents=True, exist_ok=True)

    example_file = target_dir / "example_scene.json"

    example_content = '''{
  "tree_id": "example_scene_001",
  "title": "废弃公寓 - 发现照片",
  "description": "主角在废弃公寓中发现一张旧照片的场景，包含多种分支和节奏变化",
  "start_node": "n_001",
  "nodes": {
    "n_001": {
      "node_id": "n_001",
      "node_type": "narration",
      "text": "你推开积满灰尘的门，腐朽的气息扑面而来。昏暗的走廊尽头，有什么东西在反光。",
      "next_node": "n_002",
      "fear_intensity": "medium",
      "dialogue_type": "tension"
    },
    "n_002": {
      "node_id": "n_002",
      "node_type": "choice",
      "text": "你决定：",
      "choices": [
        {
          "choice_id": "c_001",
          "text": "小心地走过去查看",
          "next_node": "n_003"
        },
        {
          "choice_id": "c_002",
          "text": "大声喊：有人吗？",
          "next_node": "n_006"
        },
        {
          "choice_id": "c_003",
          "text": "转身离开",
          "next_node": "n_008"
        }
      ],
      "fear_intensity": "medium",
      "dialogue_type": "tension"
    },
    "n_003": {
      "node_id": "n_003",
      "node_type": "narration",
      "text": "地板在你脚下吱呀作响。你走近一看，那是一张泛黄的老照片。",
      "next_node": "n_004",
      "fear_intensity": "medium",
      "dialogue_type": "tension",
      "set_variables": {
        "approached_item": true
      }
    },
    "n_004": {
      "node_id": "n_004",
      "node_type": "narration",
      "text": "照片上是一个小女孩，她的眼睛被人用红笔划掉了。照片背面写着：还记得我吗？",
      "next_node": "n_005",
      "fear_intensity": "high",
      "dialogue_type": "tension",
      "set_variables": {
        "found_photo": true,
        "has_memory": false
      }
    },
    "n_005": {
      "node_id": "n_005",
      "node_type": "choice",
      "text": "看到照片背面的字，你感到一阵寒意。你：",
      "choices": [
        {
          "choice_id": "c_004",
          "text": "仔细回忆照片上的女孩是谁",
          "next_node": "n_009"
        },
        {
          "choice_id": "c_005",
          "text": "把照片放进口袋，继续探索",
          "next_node": "n_010",
          "conditions": [
            {
              "variable": "has_memory",
              "operator": "==",
              "value": false,
              "negation": false
            }
          ]
        },
        {
          "choice_id": "c_006",
          "text": "这不可能...你明明已经死了！",
          "next_node": "n_011",
          "conditions": [
            {
              "variable": "has_memory",
              "operator": "==",
              "value": true,
              "negation": false
            }
          ]
        }
      ],
      "fear_intensity": "high",
      "dialogue_type": "tension"
    },
    "n_006": {
      "node_id": "n_006",
      "node_type": "narration",
      "text": "你的声音在空旷的走廊里回荡。没有人回应。但是...你好像听到了什么声音。",
      "next_node": "n_007",
      "fear_intensity": "high",
      "dialogue_type": "tension"
    },
    "n_007": {
      "node_id": "n_007",
      "node_type": "dialogue",
      "speaker": "???",
      "text": "你...不记得我了吗？",
      "next_node": "n_005",
      "fear_intensity": "high",
      "dialogue_type": "tension",
      "set_variables": {
        "found_photo": false,
        "has_memory": true
      }
    },
    "n_008": {
      "node_id": "n_008",
      "node_type": "narration",
      "text": "你转身想走，但门不知何时已经关上了。不管你怎么用力，门都纹丝不动。",
      "next_node": "n_002",
      "fear_intensity": "medium",
      "dialogue_type": "tension"
    },
    "n_009": {
      "node_id": "n_009",
      "node_type": "narration",
      "text": "你头痛欲裂，记忆的碎片在脑海中闪现。那是你小时候最好的朋友，但她在十年前就失踪了...",
      "next_node": "n_012",
      "fear_intensity": "medium",
      "dialogue_type": "exposition",
      "set_variables": {
        "has_memory": true
      }
    },
    "n_010": {
      "node_id": "n_010",
      "node_type": "narration",
      "text": "你把照片塞进口袋，决定先离开这里。但走廊尽头的黑暗中，有什么东西在移动。",
      "next_node": "n_013",
      "fear_intensity": "high",
      "dialogue_type": "tension"
    },
    "n_011": {
      "node_id": "n_011",
      "node_type": "narration",
      "text": "照片上的女孩似乎笑了一下。背后传来冰冷的触感，一个声音在你耳边低语：你终于想起来了。",
      "next_node": "n_014",
      "fear_intensity": "high",
      "dialogue_type": "tension",
      "conditions": [
        {
          "variable": "has_memory",
          "operator": "==",
          "value": true,
          "negation": false
        },
        {
          "variable": "found_photo",
          "operator": "==",
          "value": true,
          "negation": false
        }
      ]
    },
    "n_012": {
      "node_id": "n_012",
      "node_type": "narration",
      "text": "你终于想起来了。照片上的女孩叫小雨，你们十岁那年一起在这栋楼里玩捉迷藏，然后她就消失了。",
      "next_node": "n_011",
      "fear_intensity": "low",
      "dialogue_type": "buffer",
      "set_variables": {
        "knows_truth": true
      }
    },
    "n_013": {
      "node_id": "n_013",
      "node_type": "narration",
      "text": "那个东西越来越近了。你看不清它的脸，但你能听到它的呼吸声。",
      "next_node": "n_015",
      "fear_intensity": "high",
      "dialogue_type": "tension"
    },
    "n_014": {
      "node_id": "n_014",
      "node_type": "ending",
      "text": "Bad Ending - 永伴旧友。你感到意识逐渐模糊，最后看到的是小雨那张被划掉眼睛的照片。",
      "fear_intensity": "high",
      "dialogue_type": "tension"
    },
    "n_015": {
      "node_id": "n_015",
      "node_type": "ending",
      "text": "Bad Ending - 一无所知。你到死都不知道那个追你的东西是谁。也许不知道更好。",
      "fear_intensity": "high",
      "dialogue_type": "tension"
    }
  }
}
'''

    with open(example_file, "w", encoding="utf-8") as f:
        f.write(example_content)

    console.print(f"✅ 已创建示例对白文件: [cyan]{example_file}[/cyan]")
    console.print()
    console.print("接下来你可以：")
    console.print(f"  [cyan]dt-check check[/cyan]              检查所有对白文件")
    console.print(f"  [cyan]dt-check preview {example_file}[/cyan]  预览示例对白树")
    console.print(f"  [cyan]dt-check list[/cyan]               列出所有对白文件")
    console.print(f"  [cyan]dt-check stats {example_file}[/cyan]  查看对白树统计")


if __name__ == "__main__":
    cli()
