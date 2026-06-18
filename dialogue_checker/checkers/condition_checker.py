"""条件冲突检测器 - 检查同一段对白是否有互斥的条件要求"""
from typing import List, Set, Dict, Tuple, Optional, Any
from itertools import combinations
from dataclasses import dataclass
from ..models import DialogueTree, DialogueNode, Condition, ChoiceOption
from .base import CheckIssue, IssueType, Severity, CheckResult


@dataclass
class PathState:
    """路径状态 - 跟踪路径上的变量赋值和选择历史"""
    path: List[str]
    choices: List[Tuple[str, str]]  # (choice_node_id, choice_text)
    variable_assignments: Dict[str, Tuple[Any, str]]  # var_name -> (value, assigned_at_node)
    conditions: List[Condition]

    def copy(self) -> "PathState":
        return PathState(
            path=list(self.path),
            choices=list(self.choices),
            variable_assignments=dict(self.variable_assignments),
            conditions=list(self.conditions),
        )


class ConflictType(str):
    """冲突类型常量"""
    SAME_NODE_DIRECT = "same_node_direct"           # 同一节点内直接冲突（A和NOT A）
    SAME_NODE_VALUE = "same_node_value"             # 同一节点内值冲突（A==1和A==2）
    SAME_NODE_MUTEX = "same_node_mutex"             # 同一节点内互斥变量对
    PATH_VALUE_CONFLICT = "path_value_conflict"     # 路径上赋值与后续条件值冲突
    PATH_NEGATION_CONFLICT = "path_negation_conflict"  # 路径上赋值与后续条件否定冲突
    PATH_SET_CONFLICT = "path_set_conflict"         # 路径上同一变量多次赋值冲突
    PATH_MUTEX_CONFLICT = "path_mutex_conflict"     # 路径上互斥变量对冲突


class ConditionConflictChecker:
    """条件冲突检测器 - 增强版

    检测以下问题：
    1. 同一节点/选项的conditions中存在直接冲突（如同时要求A和NOT A）
    2. 同一节点/选项的conditions中同一变量被要求不同值（如A==1和A==2）
    3. 同一节点/选项的conditions中使用了互斥变量对
    4. 沿路径累积的条件冲突：
       - 前面节点设置的变量值与后续节点的进入条件冲突
       - 前面节点设置的变量与后续节点条件要求否定
       - 同一路径上同一变量被多次赋不同的值
       - 路径上出现互斥变量对同时为真
    """

    def __init__(self):
        base_pairs: List[Tuple[str, str]] = [
            ("has_memory", "no_memory"),
            ("found_photo", "not_found_photo"),
            ("knows_truth", "doesnt_know_truth"),
            ("is_alive", "is_dead"),
            ("has_seen_monster", "hasnt_seen_monster"),
            ("has_access_card", "no_access_card"),
            ("door_open", "door_locked"),
            ("light_on", "light_off"),
        ]
        self.mutex_variable_pairs: Set[Tuple[str, str]] = set()
        for v1, v2 in base_pairs:
            self.mutex_variable_pairs.add((v1, v2))
            self.mutex_variable_pairs.add((v2, v1))

    def add_mutex_pair(self, var1: str, var2: str):
        self.mutex_variable_pairs.add((var1, var2))
        self.mutex_variable_pairs.add((var2, var1))

    def check(self, file_path: str, tree: DialogueTree) -> CheckResult:
        result = CheckResult(file_path=file_path, tree_title=tree.title)

        for node_id, node in tree.nodes.items():
            if node.conditions:
                conflicts = self._find_conflicts_in_conditions(node.conditions)
                if conflicts:
                    for conflict_type, c1, c2 in conflicts:
                        result.issues.append(self._create_conflict_issue(
                            file_path, node_id, node.text, conflict_type,
                            c1, c2, is_node=True,
                        ))

            if node.choices:
                for choice_idx, choice in enumerate(node.choices):
                    if choice.conditions:
                        conflicts = self._find_conflicts_in_conditions(choice.conditions)
                        if conflicts:
                            for conflict_type, c1, c2 in conflicts:
                                result.issues.append(self._create_conflict_issue(
                                    file_path, node_id, node.text, conflict_type,
                                    c1, c2, is_node=False,
                                    choice_idx=choice_idx, choice_text=choice.text,
                                ))

        path_conflicts = self._find_path_condition_conflicts(file_path, tree)
        result.issues.extend(path_conflicts)

        return self._deduplicate_issues(result)

    def _find_conflicts_in_conditions(
        self,
        conditions: List[Condition],
    ) -> List[Tuple[str, Condition, Condition]]:
        """在一组条件中查找冲突，返回(冲突类型, 条件1, 条件2)"""
        conflicts: List[Tuple[str, Condition, Condition]] = []

        for i, cond1 in enumerate(conditions):
            for cond2 in conditions[i + 1:]:
                if self._is_direct_negation(cond1, cond2):
                    conflicts.append((ConflictType.SAME_NODE_DIRECT, cond1, cond2))
                elif self._is_same_variable_different_value(cond1, cond2):
                    conflicts.append((ConflictType.SAME_NODE_VALUE, cond1, cond2))
                elif self._are_mutex_variables(cond1, cond2):
                    conflicts.append((ConflictType.SAME_NODE_MUTEX, cond1, cond2))

        return conflicts

    def _is_direct_negation(self, c1: Condition, c2: Condition) -> bool:
        """检查是否为直接否定（A和NOT A）"""
        if c1.variable != c2.variable:
            return False
        if c1.operator != c2.operator:
            return False
        if c1.value != c2.value:
            return False
        return c1.negation != c2.negation

    def _is_same_variable_different_value(self, c1: Condition, c2: Condition) -> bool:
        """检查同一变量被要求不同的值（A==1和A==2）"""
        if c1.variable != c2.variable:
            return False
        if c1.operator != c2.operator:
            return False
        if c1.operator != "==":
            return False
        if c1.negation or c2.negation:
            return False
        return c1.value != c2.value

    def _are_mutex_variables(self, c1: Condition, c2: Condition) -> bool:
        """检查是否使用了预定义的互斥变量对"""
        if (c1.variable, c2.variable) in self.mutex_variable_pairs:
            if (c1.operator == "==" and c2.operator == "=="
                    and c1.value == True and c2.value == True
                    and not c1.negation and not c2.negation):
                return True
        return False

    def _find_path_condition_conflicts(self, file_path: str, tree: DialogueTree) -> List[CheckIssue]:
        """深度优先遍历所有路径，检查路径上的条件冲突"""
        issues: List[CheckIssue] = []

        def dfs(node_id: str, state: PathState):
            node = tree.get_node(node_id)
            if not node:
                return

            if node_id in state.path:
                return

            new_state = state.copy()
            new_state.path.append(node_id)

            if node.set_variables:
                for var, val in node.set_variables.items():
                    if var in new_state.variable_assignments:
                        old_val, assigned_at = new_state.variable_assignments[var]
                        if old_val != val:
                            issues.append(self._create_path_conflict_issue(
                                file_path, node_id, node.text,
                                ConflictType.PATH_SET_CONFLICT,
                                var, old_val, assigned_at, val, node_id,
                                new_state.path, new_state.choices,
                            ))
                    new_state.variable_assignments[var] = (val, node_id)

            if node.conditions:
                for cond in node.conditions:
                    for existing_var, (existing_val, assigned_at) in new_state.variable_assignments.items():
                        if self._check_assignment_vs_condition(
                            file_path, existing_var, existing_val, assigned_at,
                            cond, node_id, node.text,
                            new_state.path, new_state.choices,
                            issues,
                        ):
                            return

                    for existing_cond in new_state.conditions:
                        if self._is_direct_negation(existing_cond, cond):
                            issues.append(self._create_path_cond_conflict_issue(
                                file_path, node_id, node.text,
                                ConflictType.PATH_NEGATION_CONFLICT,
                                existing_cond, cond,
                                new_state.path, new_state.choices,
                            ))
                            return
                        elif self._is_same_variable_different_value(existing_cond, cond):
                            issues.append(self._create_path_cond_conflict_issue(
                                file_path, node_id, node.text,
                                ConflictType.PATH_VALUE_CONFLICT,
                                existing_cond, cond,
                                new_state.path, new_state.choices,
                            ))
                            return
                        elif self._are_mutex_variables(existing_cond, cond):
                            issues.append(self._create_path_cond_conflict_issue(
                                file_path, node_id, node.text,
                                ConflictType.PATH_MUTEX_CONFLICT,
                                existing_cond, cond,
                                new_state.path, new_state.choices,
                            ))
                            return

                    new_state.conditions.append(cond)

            if node.choices:
                for choice in node.choices:
                    choice_state = new_state.copy()
                    choice_state.choices.append((node_id, choice.text))
                    dfs(choice.next_node, choice_state)
            elif node.next_node:
                dfs(node.next_node, new_state)

        initial_state = PathState(
            path=[],
            choices=[],
            variable_assignments={},
            conditions=[],
        )
        dfs(tree.start_node, initial_state)

        return issues

    def _check_assignment_vs_condition(
        self,
        file_path: str,
        var: str,
        assigned_val: Any,
        assigned_at: str,
        cond: Condition,
        node_id: str,
        node_text: str,
        path: List[str],
        choices: List[Tuple[str, str]],
        issues: List[CheckIssue],
    ) -> bool:
        """检查已赋值变量与条件是否冲突"""
        if cond.variable != var:
            return False

        cond_satisfied = self._evaluate_condition(cond, assigned_val)

        if not cond_satisfied:
            conflict_type = ConflictType.PATH_VALUE_CONFLICT
            issues.append(CheckIssue(
                type=IssueType.CONDITION_CONFLICT,
                severity=Severity.ERROR,
                message="路径上变量赋值与后续条件冲突",
                file_path=file_path,
                node_id=node_id,
                node_text=node_text,
                path=list(path),
                details=[
                    f"变量 {var} 在节点 {assigned_at} 被赋值为 {assigned_val!r}",
                    f"但节点 {node_id} 要求: {cond.to_expression()}",
                    f"冲突选择路径: {' → '.join([c[1] for c in choices]) if choices else '无选择'}",
                    f"问题: 此路径的选择把状态带坏了，后续节点永远无法进入",
                ],
            ))
            return True
        return False

    def _evaluate_condition(self, cond: Condition, value: Any) -> bool:
        """评估条件在给定值下是否满足"""
        if cond.operator == "==":
            result = value == cond.value
        elif cond.operator == "!=":
            result = value != cond.value
        elif cond.operator == ">":
            result = value > cond.value if value is not None else False
        elif cond.operator == "<":
            result = value < cond.value if value is not None else False
        elif cond.operator == ">=":
            result = value >= cond.value if value is not None else False
        elif cond.operator == "<=":
            result = value <= cond.value if value is not None else False
        elif cond.operator == "in":
            result = value in cond.value if isinstance(cond.value, (list, set)) else False
        else:
            result = False

        return not result if cond.negation else result

    def _create_conflict_issue(
        self,
        file_path: str,
        node_id: str,
        node_text: str,
        conflict_type: str,
        c1: Condition,
        c2: Condition,
        is_node: bool,
        choice_idx: Optional[int] = None,
        choice_text: Optional[str] = None,
    ) -> CheckIssue:
        """创建冲突问题"""
        type_messages = {
            ConflictType.SAME_NODE_DIRECT: ("直接否定冲突", "同一条件被同时要求和否定，此节点/选项永远无法进入"),
            ConflictType.SAME_NODE_VALUE: ("值冲突", "同一变量被要求不同的值，此节点/选项永远无法进入"),
            ConflictType.SAME_NODE_MUTEX: ("互斥变量冲突", "使用了语义上互斥的变量对，此节点/选项永远无法进入"),
        }
        type_name, problem = type_messages.get(conflict_type, ("条件冲突", "条件存在逻辑冲突"))

        if is_node:
            message = f"节点条件存在{type_name}"
            details = [
                f"冲突的条件表达式:",
                f"  {c1.to_expression()}  与  {c2.to_expression()}",
                f"问题: {problem}",
            ]
        else:
            message = f"选项 {choice_idx + 1} 的条件存在{type_name}"
            details = [
                f"选项文本: \"{choice_text}\"",
                f"冲突的条件表达式:",
                f"  {c1.to_expression()}  与  {c2.to_expression()}",
                f"问题: {problem}",
            ]

        return CheckIssue(
            type=IssueType.CONDITION_CONFLICT,
            severity=Severity.ERROR,
            message=message,
            file_path=file_path,
            node_id=node_id,
            node_text=node_text,
            details=details,
        )

    def _create_path_conflict_issue(
        self,
        file_path: str,
        node_id: str,
        node_text: str,
        conflict_type: str,
        var: str,
        old_val: Any,
        old_node: str,
        new_val: Any,
        new_node: str,
        path: List[str],
        choices: List[Tuple[str, str]],
    ) -> CheckIssue:
        """创建路径赋值冲突问题"""
        choice_path = " → ".join([c[1] for c in choices]) if choices else "无选择"

        return CheckIssue(
            type=IssueType.CONDITION_CONFLICT,
            severity=Severity.ERROR,
            message="路径上同一变量被多次赋不同值",
            file_path=file_path,
            node_id=node_id,
            node_text=node_text,
            path=list(path),
            details=[
                f"变量 {var} 在节点 {old_node} 被赋值为 {old_val!r}",
                f"但在节点 {new_node} 又被赋值为 {new_val!r}",
                f"冲突选择路径: {choice_path}",
                f"问题: 前后赋值矛盾，剧情逻辑打架",
            ],
        )

    def _create_path_cond_conflict_issue(
        self,
        file_path: str,
        node_id: str,
        node_text: str,
        conflict_type: str,
        existing_cond: Condition,
        new_cond: Condition,
        path: List[str],
        choices: List[Tuple[str, str]],
    ) -> CheckIssue:
        """创建路径条件冲突问题"""
        type_messages = {
            ConflictType.PATH_NEGATION_CONFLICT: "路径累积条件与当前条件直接否定",
            ConflictType.PATH_VALUE_CONFLICT: "路径累积条件与当前条件值冲突",
            ConflictType.PATH_MUTEX_CONFLICT: "路径上出现互斥变量对同时为真",
        }
        problem = type_messages.get(conflict_type, "路径条件冲突")
        choice_path = " → ".join([c[1] for c in choices]) if choices else "无选择"

        return CheckIssue(
            type=IssueType.CONDITION_CONFLICT,
            severity=Severity.ERROR,
            message=f"路径上存在累积的条件冲突 - {problem}",
            file_path=file_path,
            node_id=node_id,
            node_text=node_text,
            path=list(path),
            details=[
                f"路径累积条件: {existing_cond.to_expression()}",
                f"当前节点条件: {new_cond.to_expression()}",
                f"冲突选择路径: {choice_path}",
                f"问题: 走到此节点时条件已矛盾，剧情逻辑打架",
            ],
        )

    def _deduplicate_issues(self, result: CheckResult) -> CheckResult:
        """去重重复的问题报告"""
        seen = set()
        unique = []
        for issue in result.issues:
            key = (issue.node_id, issue.message, tuple(issue.details))
            if key not in seen:
                seen.add(key)
                unique.append(issue)
        result.issues = unique
        return result
