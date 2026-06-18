"""条件冲突检测器测试"""
import pytest
from pathlib import Path
from dialogue_checker.checker import DialogueTreeChecker
from dialogue_checker.checkers.base import IssueType, Severity
from dialogue_checker.models import Condition


def test_direct_condition_conflict():
    """测试检测同一节点内的直接条件冲突"""
    test_file = Path(__file__).parent.parent / "dialogues" / "problematic_scene.json"

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    condition_issues = [i for i in result.issues if i.type == IssueType.CONDITION_CONFLICT]

    found_conflict = any(
        i.node_id == "n_conflict" and "has_memory" in str(i.details)
        for i in condition_issues
    )
    assert found_conflict, "应该检测到n_conflict节点的条件冲突"


def test_conflict_severity():
    """测试条件冲突的严重程度"""
    test_file = Path(__file__).parent.parent / "dialogues" / "problematic_scene.json"

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    condition_errors = [
        i for i in result.issues
        if i.type == IssueType.CONDITION_CONFLICT and i.severity == Severity.ERROR
    ]

    assert len(condition_errors) >= 1, "条件冲突应该是ERROR级别"


def test_condition_conflict_detection_logic():
    """测试条件冲突检测逻辑"""
    from dialogue_checker.checkers.condition_checker import ConditionConflictChecker

    checker = ConditionConflictChecker()

    cond1 = Condition(variable="has_memory", operator="==", value=True, negation=False)
    cond2 = Condition(variable="has_memory", operator="==", value=True, negation=True)

    assert checker._conditions_conflict(cond1, cond2), "A和NOT A应该冲突"

    cond3 = Condition(variable="has_memory", operator="==", value=True, negation=False)
    cond4 = Condition(variable="has_memory", operator="==", value=True, negation=False)

    assert not checker._conditions_conflict(cond3, cond4), "相同条件不应该冲突"

    cond5 = Condition(variable="found_photo", operator="==", value=True, negation=False)
    assert not checker._conditions_conflict(cond1, cond5), "不同变量不应该冲突"


def test_mutex_variable_detection():
    """测试互斥变量对检测"""
    from dialogue_checker.checkers.condition_checker import ConditionConflictChecker

    checker = ConditionConflictChecker()

    cond1 = Condition(variable="has_memory", operator="==", value=True, negation=False)
    cond2 = Condition(variable="no_memory", operator="==", value=True, negation=False)

    assert checker._are_mutex_variables(cond1, cond2), "has_memory和no_memory应该是互斥对"


def test_example_scene_no_condition_conflicts():
    """测试示例场景不应该有条件冲突"""
    test_file = Path(__file__).parent.parent / "dialogues" / "example_scene.json"

    if not test_file.exists():
        pytest.skip("example_scene.json not found")

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    condition_errors = [
        i for i in result.issues
        if i.type == IssueType.CONDITION_CONFLICT and i.severity == Severity.ERROR
    ]

    assert len(condition_errors) == 0, "示例场景不应该有条件冲突错误"
