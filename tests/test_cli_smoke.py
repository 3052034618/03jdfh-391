"""CLI冒烟测试 - 用 subprocess 模拟真实 python -m 启动

这些测试用于确保 CLI 命令在真实启动时不会因为导入错误等问题直接崩溃。
单元测试可能因为直接 import 模块而跳过某些启动时才会触发的问题。
"""
import subprocess
import sys
import json
import os
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
DIALOGUES_DIR = PROJECT_ROOT / "dialogues"


def _run_cli(args, env=None):
    """运行 CLI 命令并返回 CompletedProcess"""
    if env is None:
        env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    cmd = [sys.executable, "-m", "dialogue_checker.cli"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        env=env,
        cwd=str(PROJECT_ROOT),
        timeout=30,
    )


class TestCheckCommand:
    """check 命令冒烟测试"""

    def test_check_command_starts_successfully(self):
        """check 命令应该能正常启动，不会因为导入错误崩溃"""
        result = _run_cli(["check", str(DIALOGUES_DIR / "example_scene.json")])

        assert "Traceback" not in result.stderr.decode("utf-8", errors="replace"), \
            f"命令启动出错: {result.stderr.decode('utf-8', errors='replace')[:500]}"
        assert "对白树自检" in result.stdout.decode("utf-8", errors="replace") or \
               result.returncode in (0, 1, 2), \
            "命令应该正常输出或返回合理退出码"

    def test_check_print_json_output_is_valid_json(self):
        """check --print-json 输出应该是合法的 JSON，且没有混入其他内容"""
        result = _run_cli([
            "check",
            str(DIALOGUES_DIR / "writer_export_example.json"),
            "--print-json",
        ])

        stderr = result.stderr.decode("utf-8", errors="replace")
        assert "Traceback" not in stderr, \
            f"命令启动出错: {stderr[:500]}"

        stdout = result.stdout.decode("utf-8", errors="replace")
        assert len(stdout) > 0, "stdout 不应该为空"
        assert stdout.strip().startswith("{"), \
            f"JSON输出应该以{{开头，实际开头: {stdout[:50]!r}"
        assert stdout.strip().endswith("}"), \
            f"JSON输出应该以}}结尾，实际结尾: {stdout[-50:]!r}"

        data = json.loads(stdout)
        assert "summary" in data
        assert "results" in data
        assert "total_errors" in data["summary"]
        assert "total_warnings" in data["summary"]

    def test_check_print_json_no_stderr_output(self):
        """check --print-json 时 stderr 应该为空，不混入进度或说明"""
        result = _run_cli([
            "check",
            str(DIALOGUES_DIR / "writer_export_example.json"),
            "--print-json",
        ])

        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        assert len(stderr) == 0, \
            f"--print-json 时 stderr 应该为空，实际: {stderr[:200]}"

    def test_check_print_json_file_path_correct(self):
        """JSON 报告中每个 issue 的 file_path 应该是真实文件路径"""
        result = _run_cli([
            "check",
            str(DIALOGUES_DIR / "writer_export_example.json"),
            "--print-json",
        ])

        stdout = result.stdout.decode("utf-8", errors="replace")
        data = json.loads(stdout)

        for file_result in data["results"]:
            expected_path = file_result["file_path"]
            for issue in file_result["issues"]:
                assert issue["file_path"] == expected_path, \
                    f"issue {issue['node_id']} 的 file_path 不正确: " \
                    f"{issue['file_path']!r} != {expected_path!r}"

    def test_check_writer_export_detects_condition_conflicts(self):
        """writer_export_example.json 应该能检测到条件冲突"""
        result = _run_cli([
            "check",
            str(DIALOGUES_DIR / "writer_export_example.json"),
            "--print-json",
        ])

        stdout = result.stdout.decode("utf-8", errors="replace")
        data = json.loads(stdout)
        conflict_count = data["summary"]["total_condition_conflicts"]
        assert conflict_count > 0, \
            f"writer_export_example.json 应该检测到条件冲突，实际: {conflict_count}"

    def test_check_example_scene_no_errors(self):
        """example_scene.json 应该是正常的，没有错误"""
        result = _run_cli([
            "check",
            str(DIALOGUES_DIR / "example_scene.json"),
            "--print-json",
        ])

        stdout = result.stdout.decode("utf-8", errors="replace")
        data = json.loads(stdout)
        assert data["summary"]["total_errors"] == 0, \
            f"example_scene.json 应该没有错误，实际: {data['summary']['total_errors']}"


class TestAutoPreviewCommand:
    """auto-preview 命令冒烟测试"""

    def test_auto_preview_command_starts_successfully(self):
        """auto-preview 命令应该能正常启动，不会因为导入错误崩溃"""
        result = _run_cli([
            "auto-preview",
            str(DIALOGUES_DIR / "example_scene.json"),
        ])

        stderr = result.stderr.decode("utf-8", errors="replace")
        assert "Traceback" not in stderr, \
            f"命令启动出错: {stderr[:500]}"

        stdout = result.stdout.decode("utf-8", errors="replace")
        assert "路径" in stdout or "自动路径" in stdout or result.returncode in (0, 1), \
            "命令应该输出路径相关信息"

    def test_auto_preview_print_json_output_is_valid_json(self):
        """auto-preview --print-json 输出应该是合法的 JSON"""
        result = _run_cli([
            "auto-preview",
            str(DIALOGUES_DIR / "example_scene.json"),
            "--print-json",
        ])

        stderr = result.stderr.decode("utf-8", errors="replace")
        assert "Traceback" not in stderr, \
            f"命令启动出错: {stderr[:500]}"

        stdout = result.stdout.decode("utf-8", errors="replace")
        assert len(stdout) > 0, "stdout 不应该为空"
        assert stdout.strip().startswith("{"), \
            f"JSON输出应该以{{开头，实际开头: {stdout[:50]!r}"

        data = json.loads(stdout)
        assert "summary" in data
        assert "successful_paths" in data["summary"]
        assert "broken_paths" in data["summary"]
        assert "total_paths" in data["summary"]

    def test_auto_preview_print_json_no_stderr(self):
        """auto-preview --print-json 时 stderr 应该为空"""
        result = _run_cli([
            "auto-preview",
            str(DIALOGUES_DIR / "example_scene.json"),
            "--print-json",
        ])

        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        assert len(stderr) == 0, \
            f"--print-json 时 stderr 应该为空，实际: {stderr[:200]}"

    def test_auto_preview_example_scene_counts(self):
        """example_scene.json 路径数量应该符合预期"""
        result = _run_cli([
            "auto-preview",
            str(DIALOGUES_DIR / "example_scene.json"),
            "--print-json",
        ])

        stdout = result.stdout.decode("utf-8", errors="replace")
        data = json.loads(stdout)
        summary = data["summary"]

        assert summary["total_paths"] >= 4, \
            f"总路径数应该 >= 4，实际: {summary['total_paths']}"
        assert summary["successful_paths"] >= 1, \
            f"成功路径数应该 >= 1，实际: {summary['successful_paths']}"

    def test_auto_preview_show_broken_works(self):
        """--show-broken 参数应该正常工作"""
        result = _run_cli([
            "auto-preview",
            str(DIALOGUES_DIR / "example_scene.json"),
            "--show-broken",
        ])

        stderr = result.stderr.decode("utf-8", errors="replace")
        assert "Traceback" not in stderr, \
            f"命令启动出错: {stderr[:500]}"

        stdout = result.stdout.decode("utf-8", errors="replace")
        assert "断裂" in stdout, \
            "--show-broken 应该显示断裂路径"


class TestMutexBidirectional:
    """互斥条件双向检测测试"""

    def test_mutex_detection_both_directions(self):
        """互斥变量对的两种顺序都应该能检测到"""
        result = _run_cli([
            "check",
            str(DIALOGUES_DIR / "writer_export_example.json"),
            "--print-json",
        ])

        stdout = result.stdout.decode("utf-8", errors="replace")
        data = json.loads(stdout)

        mutex_conflicts = []
        for file_result in data["results"]:
            for issue in file_result["issues"]:
                if issue["type"] == "condition_conflict" and "互斥" in issue["message"]:
                    mutex_conflicts.append(issue)

        assert len(mutex_conflicts) >= 2, \
            f"应该至少有 2 个互斥变量冲突（正反方向各至少一个），实际: {len(mutex_conflicts)}"

        conflict_details = []
        for issue in mutex_conflicts:
            for detail in issue["details"]:
                if "与" in detail and "==" in detail:
                    conflict_details.append(detail.strip())

        has_forward = any("knows_truth" in d and "doesnt_know_truth" in d for d in conflict_details)
        has_backward = any("no_memory" in d and "has_memory" in d for d in conflict_details)

        assert has_forward, "应该检测到 knows_truth / doesnt_know_truth 互斥"
        assert has_backward, "应该检测到 no_memory / has_memory 反向互斥"
