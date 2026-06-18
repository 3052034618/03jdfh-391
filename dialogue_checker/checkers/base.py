"""检查结果基础模型"""
from dataclasses import dataclass, field
from typing import List, Optional, Any
from enum import Enum


class Severity(str, Enum):
    """问题严重程度"""
    ERROR = "error"       # 必须修复
    WARNING = "warning"     # 建议检查
    INFO = "info"         # 信息提示


class IssueType(str, Enum):
    """问题类型"""
    DEAD_END = "dead_end"           # 死路分支
    CONDITION_CONFLICT = "condition_conflict"  # 条件冲突
    PACE_ABNORMAL = "pace_abnormal"    # 节奏异常


@dataclass
class CheckIssue:
    """单个检查问题"""
    type: IssueType
    severity: Severity
    message: str
    file_path: str
    node_id: Optional[str] = None
    node_text: Optional[str] = None
    details: Optional[List[str]] = field(default_factory=list)
    path: Optional[List[str]] = field(default_factory=list)

    def format_details(self) -> str:
        """格式化详细信息"""
        lines = [f"[{self.severity.upper()}] {self.message}"]
        if self.node_id:
            lines.append(f"  节点: {self.node_id}")
        if self.node_text:
            text_preview = self.node_text[:50] + "..." if len(self.node_text) > 50 else self.node_text
            lines.append(f"  文本: \"{text_preview}\"")
        if self.path:
            lines.append(f"  路径: {' → '.join(self.path)}")
        if self.details:
            lines.extend(f"  - {d}" for d in self.details)
        return "\n".join(lines)


@dataclass
class CheckResult:
    """检查结果汇总"""
    file_path: str
    tree_title: str
    issues: List[CheckIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[CheckIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> List[CheckIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    def count_by_type(self, issue_type: IssueType) -> int:
        return sum(1 for i in self.issues if i.type == issue_type)


@dataclass
class CheckReport:
    """完整的检查报告"""
    results: List[CheckResult] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.results)

    @property
    def total_errors(self) -> int:
        return sum(r.errors for r in self.results)

    @property
    def total_warnings(self) -> int:
        return sum(len(r.warnings) for r in self.results)

    @property
    def total_dead_ends(self) -> int:
        return sum(r.count_by_type(IssueType.DEAD_END) for r in self.results)

    @property
    def total_condition_conflicts(self) -> int:
        return sum(r.count_by_type(IssueType.CONDITION_CONFLICT) for r in self.results)

    @property
    def total_pace_abnormal(self) -> int:
        return sum(r.count_by_type(IssueType.PACE_ABNORMAL) for r in self.results)

    @property
    def has_errors(self) -> bool:
        return any(r.has_errors for r in self.results)
