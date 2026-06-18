"""死路分支检测器 - 检查玩家选择后没有后续台词的问题"""
from typing import List, Set, Optional, Dict
from ..models import DialogueTree, DialogueNode, NodeType
from .base import CheckIssue, IssueType, Severity, CheckResult


class DeadEndChecker:
    """死路分支检测器

    检测以下问题：
    1. 非END节点缺少后续（既无choices也无next_node）
    2. 选项指向不存在的节点
    3. next_node指向不存在的节点
    4. 有进无出的死胡同（能走到但无法继续的路径）
    """

    def __init__(self):
        self.visited_nodes: Set[str] = set()

    def check(self, file_path: str, tree: DialogueTree) -> CheckResult:
        """执行死路分支检测"""
        result = CheckResult(file_path=file_path, tree_title=tree.title)
        self.visited_nodes.clear()

        reachable_nodes = self._get_reachable_nodes(tree)

        for node_id, node in tree.nodes.items():
            if node.node_type == NodeType.ENDING:
                continue

            issues_in_node: List[CheckIssue] = []

            if node.choices:
                for idx, choice in enumerate(node.choices):
                    if not tree.has_node(choice.next_node):
                        issues_in_node.append(CheckIssue(
                            type=IssueType.DEAD_END,
                            severity=Severity.ERROR,
                            message=f"选项指向不存在的节点",
                            file_path=file_path,
                            node_id=node_id,
                            node_text=node.text,
                            details=[
                                f"选项 {idx + 1}: \"{choice.text}\"",
                                f"目标节点: {choice.next_node}",
                            ],
                        ))
                if not any(c.next_node in tree.nodes for c in node.choices):
                    issues_in_node.append(CheckIssue(
                        type=IssueType.DEAD_END,
                        severity=Severity.WARNING,
                        message="所有选项均指向不存在的节点",
                        file_path=file_path,
                        node_id=node_id,
                        node_text=node.text,
                    ))
            elif node.next_node:
                if not tree.has_node(node.next_node):
                    issues_in_node.append(CheckIssue(
                        type=IssueType.DEAD_END,
                        severity=Severity.ERROR,
                        message=f"next_node指向不存在的节点",
                        file_path=file_path,
                        node_id=node_id,
                        node_text=node.text,
                        details=[f"目标节点: {node.next_node}"],
                    ))
            else:
                if node_id in reachable_nodes:
                    path = self._find_path_to(tree, node_id)
                    issues_in_node.append(CheckIssue(
                        type=IssueType.DEAD_END,
                        severity=Severity.ERROR,
                        message="节点缺少后续内容（试玩时会突然黑屏或沉默）",
                        file_path=file_path,
                        node_id=node_id,
                        node_text=node.text,
                        path=path,
                        details=[
                            f"节点类型: {node.node_type.value}",
                            "建议: 添加choices或next_node，或将node_type设为ending",
                        ],
                    ))
                else:
                    issues_in_node.append(CheckIssue(
                        type=IssueType.DEAD_END,
                        severity=Severity.WARNING,
                        message="孤立节点（无法从起始节点到达）",
                        file_path=file_path,
                        node_id=node_id,
                        node_text=node.text,
                        details=[
                            "该节点没有任何前置条件或跳转指向它",
                            "可能是未完成的分支或已废弃的内容",
                        ],
                    ))

            result.issues.extend(issues_in_node)

        unreachable = set(tree.nodes.keys()) - reachable_nodes - {tree.start_node}
        for node_id in sorted(unreachable):
            if not any(i.node_id == node_id for i in result.issues):
                node = tree.get_node(node_id)
                result.issues.append(CheckIssue(
                    type=IssueType.DEAD_END,
                    severity=Severity.WARNING,
                    message="孤立节点（无法从起始节点到达）",
                    file_path=file_path,
                    node_id=node_id,
                    node_text=node.text if node else None,
                    details=["该节点没有任何前置条件或跳转指向它"],
                ))

        return result

    def _get_reachable_nodes(self, tree: DialogueTree) -> Set[str]:
        """获取从起始节点可达的所有节点"""
        reachable: Set[str] = set()

        def dfs(node_id: str):
            if node_id in reachable:
                return
            node = tree.get_node(node_id)
            if not node:
                return
            reachable.add(node_id)
            if node.choices:
                for choice in node.choices:
                    dfs(choice.next_node)
            elif node.next_node:
                dfs(node.next_node)

        dfs(tree.start_node)
        return reachable

    def _find_path_to(self, tree: DialogueTree, target_id: str) -> Optional[List[str]]:
        """查找从起始节点到目标节点的一条路径"""
        def dfs(current_id: str, path: List[str]) -> Optional[List[str]]:
            if current_id == target_id:
                return path + [current_id]
            node = tree.get_node(current_id)
            if not node:
                    return None
            new_path = path + [current_id]
            if node.choices:
                for choice in node.choices:
                    result = dfs(choice.next_node, new_path)
                    if result:
                        return result
            elif node.next_node:
                result = dfs(node.next_node, new_path)
                if result:
                    return result
            return None

        return dfs(tree.start_node, [])
