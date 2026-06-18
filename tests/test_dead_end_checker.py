"""死路分支检测器测试"""
import pytest
from pathlib import Path
from dialogue_checker.checker import DialogueTreeChecker
from dialogue_checker.checkers.base import IssueType, Severity


def test_dead_end_detection():
    """测试检测缺少后续的节点"""
    test_file = Path(__file__).parent.parent / "dialogues" / "problematic_scene.json"

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    dead_end_issues = [i for i in result.issues if i.type == IssueType.DEAD_END]

    found_dead_end = any(
        i.node_id == "n_dead_end1" and "缺少后续内容" in i.message
        for i in dead_end_issues
    )
    assert found_dead_end, "应该检测到n_dead_end1缺少后续"


def test_nonexistent_node_reference():
    """测试检测指向不存在节点的选项"""
    test_file = Path(__file__).parent.parent / "dialogues" / "problematic_scene.json"

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    dead_end_issues = [i for i in result.issues if i.type == IssueType.DEAD_END]

    found_nonexistent = any(
        "n_nonexistent" in str(i.details)
        for i in dead_end_issues
    )
    assert found_nonexistent, "应该检测到指向n_nonexistent的无效引用"


def test_isolated_node_detection():
    """测试检测孤立节点"""
    test_file = Path(__file__).parent.parent / "dialogues" / "problematic_scene.json"

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    dead_end_issues = [i for i in result.issues if i.type == IssueType.DEAD_END]

    found_isolated = any(
        i.node_id == "n_isolated" and "孤立节点" in i.message
        for i in dead_end_issues
    )
    assert found_isolated, "应该检测到n_isolated是孤立节点"


def test_severity_for_dead_end():
    """测试死路分支的严重程度"""
    test_file = Path(__file__).parent.parent / "dialogues" / "problematic_scene.json"

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    error_dead_ends = [
        i for i in result.issues
        if i.type == IssueType.DEAD_END and i.severity == Severity.ERROR
    ]

    assert len(error_dead_ends) >= 2, "缺少后续和无效引用应该是ERROR级别"


def test_example_scene_no_dead_ends():
    """测试示例场景不应该有严重的死路分支"""
    test_file = Path(__file__).parent.parent / "dialogues" / "example_scene.json"

    if not test_file.exists():
        pytest.skip("example_scene.json not found")

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    error_dead_ends = [
        i for i in result.issues
        if i.type == IssueType.DEAD_END and i.severity == Severity.ERROR
    ]

    assert len(error_dead_ends) == 0, "示例场景不应该有严重的死路分支错误"
