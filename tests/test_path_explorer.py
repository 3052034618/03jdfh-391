"""路径遍历器测试"""
import pytest
from pathlib import Path
from dialogue_checker.preview import PathExplorer, PathStatus
from dialogue_checker.parser import DialogueParser


def test_path_explorer_example_scene():
    """测试示例场景的路径遍历"""
    test_file = Path(__file__).parent.parent / "dialogues" / "example_scene.json"

    if not test_file.exists():
        pytest.skip("example_scene.json not found")

    parser = DialogueParser()
    tree = parser.load_file(str(test_file))

    explorer = PathExplorer(tree)
    report = explorer.explore()

    assert report.total_paths > 0, "应该检测到至少一条路径"
    assert report.tree_id == tree.tree_id
    assert report.tree_title == tree.title

    for result in report.all_paths:
        assert len(result.path) > 0, "路径不应该为空"
        assert result.status in PathStatus

    success_count = len(report.successful_paths)
    broken_count = len(report.broken_paths)
    assert success_count + broken_count == report.total_paths, "成功和断裂路径数之和应该等于总路径数"


def test_path_explorer_problematic_scene():
    """测试问题场景的路径遍历"""
    test_file = Path(__file__).parent.parent / "dialogues" / "problematic_scene.json"

    if not test_file.exists():
        pytest.skip("problematic_scene.json not found")

    parser = DialogueParser()
    tree = parser.load_file(str(test_file))

    explorer = PathExplorer(tree)
    report = explorer.explore()

    assert report.broken_count > 0, "问题场景应该检测到断裂路径"

    has_broken_node = any(r.status == PathStatus.BROKEN_NODE for r in report.broken_paths)
    has_broken_no_next = any(r.status == PathStatus.BROKEN_NO_NEXT for r in report.broken_paths)

    assert has_broken_node or has_broken_no_next, "应该检测到节点不存在或缺少后续的问题"


def test_path_explorer_writer_scene():
    """测试编剧导出示例的路径遍历"""
    test_file = Path(__file__).parent.parent / "dialogues" / "writer_export_example.json"

    if not test_file.exists():
        pytest.skip("writer_export_example.json not found")

    parser = DialogueParser()
    tree = parser.load_file(str(test_file))

    explorer = PathExplorer(tree)
    report = explorer.explore()

    assert report.total_paths > 0

    has_condition_blocked = any(r.status == PathStatus.CONDITION_BLOCKED for r in report.all_paths)
    if has_condition_blocked:
        for result in report.broken_paths:
            if result.status == PathStatus.CONDITION_BLOCKED:
                assert result.error_message is not None
                assert "条件不满足" in result.error_message


def test_path_result_properties():
    """测试路径结果的属性"""
    test_file = Path(__file__).parent.parent / "dialogues" / "example_scene.json"

    if not test_file.exists():
        pytest.skip("example_scene.json not found")

    parser = DialogueParser()
    tree = parser.load_file(str(test_file))

    explorer = PathExplorer(tree)
    report = explorer.explore()

    for result in report.successful_paths:
        assert result.is_successful == True
        assert result.ending_text is not None
        assert "Bad Ending" in result.ending_text or "True Ending" in result.ending_text

    for result in report.all_paths:
        path_display = result.path_display
        assert " → " in path_display
        assert len(result.path) > 0


def test_path_report_serialization():
    """测试路径报告的JSON和Markdown序列化"""
    test_file = Path(__file__).parent.parent / "dialogues" / "example_scene.json"

    if not test_file.exists():
        pytest.skip("example_scene.json not found")

    parser = DialogueParser()
    tree = parser.load_file(str(test_file))

    explorer = PathExplorer(tree)
    report = explorer.explore()

    json_str = report.to_json()
    assert json_str, "JSON序列化不应该为空"
    assert "summary" in json_str
    assert "total_paths" in json_str
    assert "successful_paths" in json_str
    assert "broken_paths" in json_str

    data = report.to_dict()
    assert data["summary"]["total_paths"] == report.total_paths
    assert data["summary"]["successful_paths"] == report.success_count
    assert data["summary"]["broken_paths"] == report.broken_count

    md_str = report.to_markdown()
    assert md_str, "Markdown序列化不应该为空"
    assert "# 路径遍历报告" in md_str
    assert "## 汇总" in md_str

    if report.successful_paths:
        assert "## ✅ 成功路径" in md_str
    if report.broken_paths:
        assert "## ❌ 断裂路径" in md_str


def test_path_result_to_dict():
    """测试单条路径结果的字典转换"""
    test_file = Path(__file__).parent.parent / "dialogues" / "example_scene.json"

    if not test_file.exists():
        pytest.skip("example_scene.json not found")

    parser = DialogueParser()
    tree = parser.load_file(str(test_file))

    explorer = PathExplorer(tree)
    report = explorer.explore()

    for result in report.all_paths:
        data = result.to_dict()
        assert "path" in data
        assert "choices" in data
        assert "status" in data
        assert "status_text" in data
        assert "path_display" in data
        assert "choices_display" in data
        assert data["status"] == result.status.value


def test_path_explorer_detects_loops():
    """测试路径遍历器检测循环"""
    test_file = Path(__file__).parent.parent / "dialogues" / "example_scene.json"

    if not test_file.exists():
        pytest.skip("example_scene.json not found")

    parser = DialogueParser()
    tree = parser.load_file(str(test_file))

    explorer = PathExplorer(tree)
    report = explorer.explore()

    has_loop = any(r.status == PathStatus.LOOP_DETECTED for r in report.all_paths)
    if has_loop:
        for result in report.all_paths:
            if result.status == PathStatus.LOOP_DETECTED:
                assert "检测到循环" in result.error_message
