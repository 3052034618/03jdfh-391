"""检查器管理器 - 统一调度所有检测器并生成报告"""
from typing import List, Optional
from .models import DialogueTree
from .parser import DialogueParser, ParseError
from .checkers.base import CheckReport, CheckResult, CheckIssue, IssueType, Severity
from .checkers.dead_end_checker import DeadEndChecker
from .checkers.condition_checker import ConditionConflictChecker
from .checkers.pace_checker import PaceChecker


class DialogueTreeChecker:
    """对白树检查器主类"""

    def __init__(
        self,
        dialogue_dir: str = "dialogues",
        pace_config: Optional[dict] = None,
    ):
        self.parser = DialogueParser(dialogue_dir)
        self.dead_end_checker = DeadEndChecker()
        self.condition_checker = ConditionConflictChecker()
        self.pace_checker = PaceChecker(**(pace_config or {}))

    def check_path(self, path: str) -> CheckReport:
        """检查单个文件或整个目录"""
        report = CheckReport()

        try:
            loaded = self.parser.load_single_or_directory(path)
        except ParseError as e:
            result = CheckResult(
                file_path=e.file_path,
                tree_title="解析错误",
                issues=[CheckIssue(
                    type=IssueType.DEAD_END,
                    severity=Severity.ERROR,
                    message=str(e),
                    file_path=e.file_path,
                    details=[f"行号: {e.line_number}" if e.line_number else ""],
                )],
            )
            report.results.append(result)
            return report

        for file_path, item in loaded:
            if isinstance(item, ParseError):
                result = CheckResult(
                    file_path=file_path,
                    tree_title="解析错误",
                    issues=[CheckIssue(
                        type=IssueType.DEAD_END,
                        severity=Severity.ERROR,
                        message=item.message,
                        file_path=file_path,
                        details=[f"行号: {item.line_number}" if item.line_number else ""],
                    )],
                )
                report.results.append(result)
            else:
                result = self._check_tree(file_path, item)
                report.results.append(result)

        return report

    def _check_tree(self, file_path: str, tree: DialogueTree) -> CheckResult:
        """对单个对白树执行所有检查"""
        merged_result = CheckResult(file_path=file_path, tree_title=tree.title)

        dead_end_result = self.dead_end_checker.check(file_path, tree)
        condition_result = self.condition_checker.check(file_path, tree)
        pace_result = self.pace_checker.check(file_path, tree)

        merged_result.issues.extend(dead_end_result.issues)
        merged_result.issues.extend(condition_result.issues)
        merged_result.issues.extend(pace_result.issues)

        return merged_result

    def check_file(self, file_path: str) -> CheckResult:
        """检查单个文件"""
        report = self.check_path(file_path)
        return report.results[0] if report.results else CheckResult(
            file_path=file_path,
            tree_title="未知",
        )

    def check_directory(self, dir_path: Optional[str] = None) -> CheckReport:
        """检查整个目录"""
        return self.check_path(dir_path or self.parser.dialogue_dir)
