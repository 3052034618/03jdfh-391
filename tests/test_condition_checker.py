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

    assert checker._is_direct_negation(cond1, cond2), "A和NOT A应该冲突"

    cond3 = Condition(variable="has_memory", operator="==", value=True, negation=False)
    cond4 = Condition(variable="has_memory", operator="==", value=True, negation=False)

    assert not checker._is_direct_negation(cond3, cond4), "相同条件不应该冲突"

    cond5 = Condition(variable="found_photo", operator="==", value=True, negation=False)
    assert not checker._is_direct_negation(cond1, cond5), "不同变量不应该冲突"


def test_same_variable_different_value():
    """测试检测同一变量被要求不同值"""
    from dialogue_checker.checkers.condition_checker import ConditionConflictChecker

    checker = ConditionConflictChecker()

    cond1 = Condition(variable="has_access_card", operator="==", value=True, negation=False)
    cond2 = Condition(variable="has_access_card", operator="==", value=False, negation=False)

    assert checker._is_same_variable_different_value(cond1, cond2), "同一变量不同值应该冲突"

    cond3 = Condition(variable="found_photo", operator="==", value=True, negation=False)
    cond4 = Condition(variable="found_photo", operator="==", value=False, negation=False)

    assert checker._is_same_variable_different_value(cond3, cond4), "found_photo不同值应该冲突"

    cond5 = Condition(variable="has_access_card", operator="==", value=True, negation=False)
    cond6 = Condition(variable="has_access_card", operator="==", value=True, negation=False)

    assert not checker._is_same_variable_different_value(cond5, cond6), "相同值不应该冲突"


def test_mutex_variable_detection():
    """测试互斥变量对检测"""
    from dialogue_checker.checkers.condition_checker import ConditionConflictChecker

    checker = ConditionConflictChecker()

    cond1 = Condition(variable="has_memory", operator="==", value=True, negation=False)
    cond2 = Condition(variable="no_memory", operator="==", value=True, negation=False)

    assert checker._are_mutex_variables(cond1, cond2), "has_memory和no_memory应该是互斥对"

    cond3 = Condition(variable="knows_truth", operator="==", value=True, negation=False)
    cond4 = Condition(variable="doesnt_know_truth", operator="==", value=True, negation=False)

    assert checker._are_mutex_variables(cond3, cond4), "knows_truth和doesnt_know_truth应该是互斥对"

    cond5 = Condition(variable="is_alive", operator="==", value=True, negation=False)
    cond6 = Condition(variable="is_dead", operator="==", value=True, negation=False)

    assert checker._are_mutex_variables(cond5, cond6), "is_alive和is_dead应该是互斥对"


def test_writer_export_scene_value_conflicts():
    """测试编剧导出示例中的值冲突检测"""
    test_file = Path(__file__).parent.parent / "dialogues" / "writer_export_example.json"

    if not test_file.exists():
        pytest.skip("writer_export_example.json not found")

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    condition_issues = [i for i in result.issues if i.type == IssueType.CONDITION_CONFLICT]

    found_value_conflict = any(
        "值冲突" in i.message and "has_access_card" in str(i.details)
        for i in condition_issues
    )
    assert found_value_conflict, "应该检测到has_access_card的值冲突（同时要求True和False）"

    found_choice_value_conflict = any(
        "选项" in i.message and "found_photo" in str(i.details)
        for i in condition_issues
    )
    assert found_choice_value_conflict, "应该检测到选项中的found_photo值冲突"


def test_writer_export_mutex_conflicts():
    """测试编剧导出示例中的互斥变量对检测"""
    test_file = Path(__file__).parent.parent / "dialogues" / "writer_export_example.json"

    if not test_file.exists():
        pytest.skip("writer_export_example.json not found")

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    condition_issues = [i for i in result.issues if i.type == IssueType.CONDITION_CONFLICT]

    found_mutex_conflict = any(
        "互斥变量冲突" in i.message and "knows_truth" in str(i.details)
        for i in condition_issues
    )
    assert found_mutex_conflict, "应该检测到knows_truth和doesnt_know_truth的互斥冲突"


def test_path_assignment_conflicts():
    """测试路径上的变量赋值冲突检测"""
    test_file = Path(__file__).parent.parent / "dialogues" / "writer_export_example.json"

    if not test_file.exists():
        pytest.skip("writer_export_example.json not found")

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    condition_issues = [i for i in result.issues if i.type == IssueType.CONDITION_CONFLICT]

    found_assignment_conflict = any(
        "被多次赋不同值" in i.message and "has_access_card" in str(i.details)
        for i in condition_issues
    )
    assert found_assignment_conflict, "应该检测到has_access_card在路径上被多次赋不同值"

    found_body_conflict = any(
        "found_body" in str(i.details) and "被多次赋不同值" in i.message
        for i in condition_issues
    )
    assert found_body_conflict, "应该检测到found_body在路径上被多次赋不同值"


def test_path_assignment_vs_condition_conflict():
    """测试路径赋值与后续条件冲突检测"""
    test_file = Path(__file__).parent.parent / "dialogues" / "writer_export_example.json"

    if not test_file.exists():
        pytest.skip("writer_export_example.json not found")

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    condition_issues = [i for i in result.issues if i.type == IssueType.CONDITION_CONFLICT]

    found_assignment_vs_condition = any(
        "变量赋值与后续条件冲突" in i.message and "has_access_card" in str(i.details)
        for i in condition_issues
    )
    assert found_assignment_vs_condition, "应该检测到变量赋值与后续条件冲突"

    found_choice_path_ruined = any(
        "此路径的选择把状态带坏了" in str(i.details)
        for i in condition_issues
    )
    assert found_choice_path_ruined, "应该在报告中标明哪条选择路径把状态带坏了"


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


def test_report_serialization():
    """测试检查报告的JSON和Markdown序列化"""
    test_file = Path(__file__).parent.parent / "dialogues" / "example_scene.json"

    if not test_file.exists():
        pytest.skip("example_scene.json not found")

    checker = DialogueTreeChecker()
    report = checker.check_path(str(test_file))

    json_str = report.to_json()
    assert json_str, "JSON序列化不应该为空"
    assert "summary" in json_str, "JSON应该包含summary"
    assert "total_files" in json_str, "JSON应该包含total_files"

    from dialogue_checker.checkers.base import CheckReport
    parsed_report = CheckReport.from_json(json_str)
    assert parsed_report.total_files == report.total_files, "反序列化后total_files应该一致"
    assert parsed_report.total_errors == report.total_errors, "反序列化后total_errors应该一致"

    md_str = report.to_markdown()
    assert md_str, "Markdown序列化不应该为空"
    assert "# 对白树检查报告" in md_str, "Markdown应该包含标题"
    assert "## 检查汇总" in md_str, "Markdown应该包含检查汇总"

