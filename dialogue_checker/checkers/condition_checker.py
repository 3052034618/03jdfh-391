"""条件冲突检测器 - 检查同一段对白是否有互斥的条件要求"""
from typing import List, Set, Dict, Tuple, Optional
from itertools import combinations
from ..models import DialogueTree, DialogueNode, Condition
from .base import CheckIssue, IssueType, Severity, CheckResult


class ConditionConflictChecker:
    """条件冲突检测器

    检测以下问题：
    1. 同一节点的conditions中存在互斥条件（如同时要求A和NOT A）
    2. 同一选项的conditions中存在互斥条件
    3. 沿路径累积的条件冲突（路径上多个节点设置的条件互斥）
    """

    def __init__(self):
        # 预定义的互斥变量对，这些变量语义上就是互斥的
        self.mutex_variable_pairs: Set[Tuple[str, str]] = {
            ("has_memory", "no_memory"),
            ("found_photo", "not_found_photo"),
            ("knows_truth", "doesnt_know_truth"),
            ("is_alive", "is_dead"),
            ("has_seen_monster", "hasnt_seen_monster"),
        }

    def add_mutex_pair(self, var1: str, var2: str):
        """添加一对互斥变量"""
        self.mutex_variable_pairs.add((var1, var2))
        self.mutex_variable_pairs.add((var2, var1))

    def check(self, file_path: str, tree: DialogueTree) -> CheckResult:
        """执行条件冲突检测"""
        result = CheckResult(file_path=file_path, tree_title=tree.title)

        for node_id, node in tree.nodes.items():
            if node.conditions:
                conflicts = self._find_conflicts_in_conditions(node.conditions)
                if conflicts:
                    result.issues.append(CheckIssue(
                        type=IssueType.CONDITION_CONFLICT,
                        severity=Severity.ERROR,
                        message="节点条件存在逻辑冲突",
                        file_path=file_path,
                        node_id=node_id,
                        node_text=node.text,
                        details=[
                            "冲突的条件表达式:",
                            *[f"  {c1.to_expression()}  与  {c2.to_expression()}" for c1, c2 in conflicts],
                            "问题: 无法同时满足这些条件，此节点永远无法进入",
                        ],
                    ))

            if node.choices:
                for choice_idx, choice in enumerate(node.choices):
                    if choice.conditions:
                        conflicts = self._find_conflicts_in_conditions(choice.conditions)
                        if conflicts:
                            result.issues.append(CheckIssue(
                                type=IssueType.CONDITION_CONFLICT,
                                severity=Severity.ERROR,
                                message=f"选项 {choice_idx + 1} 的条件存在逻辑冲突",
                                file_path=file_path,
                                node_id=node_id,
                                node_text=node.text,
                                details=[
                                    f"选项文本: \"{choice.text}\"",
                                    "冲突的条件表达式:",
                                    *[f"  {c1.to_expression()}  与  {c2.to_expression()}" for c1, c2 in conflicts],
                                    "问题: 无法同时满足这些条件，此选项永远无法显示",
                                ],
                            ))

        path_conflicts = self._find_path_condition_conflicts(tree)
        result.issues.extend(path_conflicts)

        return result

    def _find_conflicts_in_conditions(self, conditions: List[Condition]) -> List[Tuple[Condition, Condition]]:
        """在一组条件中查找冲突"""
        conflicts: List[Tuple[Condition, Condition]] = []

        for i, cond1 in enumerate(conditions):
            for cond2 in conditions[i + 1:]:
                if self._conditions_conflict(cond1, cond2):
                    conflicts.append((cond1, cond2))

                if self._are_mutex_variables(cond1, cond2):
                    conflicts.append((cond1, cond2))

        return conflicts

    def _conditions_conflict(self, c1: Condition, c2: Condition) -> bool:
        """检查两个条件是否直接冲突"""
        if c1.variable != c2.variable:
            return False
        if c1.operator != c2.operator:
            return False
        if c1.value != c2.value:
            return False
        return c1.negation != c2.negation

    def _are_mutex_variables(self, c1: Condition, c2: Condition) -> bool:
        """检查两个条件涉及的变量是否为预定义的互斥对"""
        if (c1.variable, c2.variable) in self.mutex_variable_pairs:
            if (c1.operator == "==" and c2.operator == "=="
                    and c1.value == True and c2.value == True
                    and not c1.negation and not c2.negation):
                return True
        return False

    def _find_path_condition_conflicts(self, tree: DialogueTree) -> List[CheckIssue]:
        """检查沿路径累积的条件冲突"""
        issues: List[CheckIssue] = []
        all_paths = tree.get_all_paths()

        for path in all_paths:
            accumulated_conditions: List[Condition] = []
            conflict_found = False

            for node_id in path:
                node = tree.get_node(node_id)
                if not node:
                    continue

                if node.set_variables:
                    for var, val in node.set_variables.items():
                        accumulated_conditions.append(Condition(
                            variable=var,
                            operator="==",
                            value=val,
                            negation=False,
                        ))

                if node.conditions:
                    for cond in node.conditions:
                        for existing_cond in accumulated_conditions:
                            if self._conditions_conflict(existing_cond, cond):
                                issues.append(CheckIssue(
                                    type=IssueType.CONDITION_CONFLICT,
                                    severity=Severity.ERROR,
                                    message="路径上存在累积的条件冲突",
                                    file_path=tree.title,
                                    node_id=node_id,
                                    node_text=node.text,
                                    path=path[:path.index(node_id) + 1],
                                    details=[
                                        f"路径累积条件: {existing_cond.to_expression()}",
                                        f"当前节点条件: {cond.to_expression()}",
                                        "问题: 走到此节点时条件已矛盾，剧情逻辑打架",
                                    ],
                                ))
                                conflict_found = True
                                break
                        if conflict_found:
                            break

                    if conflict_found:
                        break

                    accumulated_conditions.extend(node.conditions)

                if conflict_found:
                    break

        return self._deduplicate_issues(issues)

    def _deduplicate_issues(self, issues: List[CheckIssue]) -> List[CheckIssue]:
        """去重重复的问题报告"""
        seen = set()
        unique = []
        for issue in issues:
            key = (issue.node_id, tuple(issue.details))
            if key not in seen:
                seen.add(key)
                unique.append(issue)
        return unique
