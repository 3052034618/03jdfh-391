"""恐惧节奏异常检测器测试"""
import pytest
from pathlib import Path
from dialogue_checker.checker import DialogueTreeChecker
from dialogue_checker.checkers.base import IssueType, Severity


def test_continuous_high_tension_detection():
    """测试检测连续高压节点"""
    test_file = Path(__file__).parent.parent / "dialogues" / "problematic_scene.json"

    checker = DialogueTreeChecker(pace_config={"max_continuous_high": 3})
    result = checker.check_file(str(test_file))

    pace_issues = [i for i in result.issues if i.type == IssueType.PACE_ABNORMAL]

    found_continuous_high = any(
        "连续" in i.message and "高压" in i.message
        for i in pace_issues
    )
    assert found_continuous_high, "应该检测到连续高压节点"


def test_continuous_exposition_detection():
    """测试检测连续解释节点"""
    test_file = Path(__file__).parent.parent / "dialogues" / "problematic_scene.json"

    checker = DialogueTreeChecker(pace_config={"max_continuous_exposition": 3})
    result = checker.check_file(str(test_file))

    pace_issues = [i for i in result.issues if i.type == IssueType.PACE_ABNORMAL]

    found_continuous_exposition = any(
        "连续" in i.message and "解释" in i.message
        for i in pace_issues
    )
    assert found_continuous_exposition, "应该检测到连续解释节点"


def test_lack_of_buffer_detection():
    """测试检测缺少缓冲"""
    test_file = Path(__file__).parent.parent / "dialogues" / "problematic_scene.json"

    checker = DialogueTreeChecker(pace_config={"require_buffer_after_high": True})
    result = checker.check_file(str(test_file))

    pace_issues = [i for i in result.issues if i.type == IssueType.PACE_ABNORMAL]

    found_lack_of_buffer = any(
        "缺少缓冲" in i.message
        for i in pace_issues
    )
    assert found_lack_of_buffer, "应该检测到缺少缓冲"


def test_pace_issue_severity():
    """测试节奏异常的严重程度（应该是WARNING）"""
    test_file = Path(__file__).parent.parent / "dialogues" / "problematic_scene.json"

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    pace_warnings = [
        i for i in result.issues
        if i.type == IssueType.PACE_ABNORMAL and i.severity == Severity.WARNING
    ]

    assert len(pace_warnings) >= 2, "节奏异常应该是WARNING级别"


def test_pace_config_threshold():
    """测试节奏阈值配置"""
    test_file = Path(__file__).parent.parent / "dialogues" / "problematic_scene.json"

    checker_strict = DialogueTreeChecker(pace_config={
        "max_continuous_high": 2,
        "max_continuous_exposition": 2,
    })
    result_strict = checker_strict.check_file(str(test_file))
    pace_issues_strict = [i for i in result_strict.issues if i.type == IssueType.PACE_ABNORMAL]

    checker_lenient = DialogueTreeChecker(pace_config={
        "max_continuous_high": 10,
        "max_continuous_exposition": 10,
    })
    result_lenient = checker_lenient.check_file(str(test_file))
    pace_issues_lenient = [i for i in result_lenient.issues if i.type == IssueType.PACE_ABNORMAL]

    assert len(pace_issues_strict) >= len(pace_issues_lenient), "严格阈值应该检测到更多问题"


def test_example_scene_pace():
    """测试示例场景的节奏"""
    test_file = Path(__file__).parent.parent / "dialogues" / "example_scene.json"

    if not test_file.exists():
        pytest.skip("example_scene.json not found")

    checker = DialogueTreeChecker()
    result = checker.check_file(str(test_file))

    pace_issues = [i for i in result.issues if i.type == IssueType.PACE_ABNORMAL]

    for issue in pace_issues:
        print(f"节奏问题: {issue.message}")
