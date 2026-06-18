"""检查结果基础模型"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any
from enum import Enum
import json
from datetime import datetime


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

    def to_dict(self) -> dict:
        """转换为可序列化的字典"""
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "message": self.message,
            "file_path": self.file_path,
            "node_id": self.node_id,
            "node_text": self.node_text,
            "details": self.details,
            "path": self.path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CheckIssue":
        """从字典创建"""
        return cls(
            type=IssueType(data["type"]),
            severity=Severity(data["severity"]),
            message=data["message"],
            file_path=data["file_path"],
            node_id=data.get("node_id"),
            node_text=data.get("node_text"),
            details=data.get("details", []),
            path=data.get("path", []),
        )


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

    def to_dict(self) -> dict:
        """转换为可序列化的字典"""
        return {
            "file_path": self.file_path,
            "tree_title": self.tree_title,
            "has_errors": self.has_errors,
            "total_issues": len(self.issues),
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues_by_type": {
                IssueType.DEAD_END.value: self.count_by_type(IssueType.DEAD_END),
                IssueType.CONDITION_CONFLICT.value: self.count_by_type(IssueType.CONDITION_CONFLICT),
                IssueType.PACE_ABNORMAL.value: self.count_by_type(IssueType.PACE_ABNORMAL),
            },
            "issues": [issue.to_dict() for issue in self.issues],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CheckResult":
        """从字典创建"""
        return cls(
            file_path=data["file_path"],
            tree_title=data["tree_title"],
            issues=[CheckIssue.from_dict(i) for i in data.get("issues", [])],
        )


@dataclass
class CheckReport:
    """完整的检查报告"""
    results: List[CheckResult] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def total_files(self) -> int:
        return len(self.results)

    @property
    def total_errors(self) -> int:
        return sum(len(r.errors) for r in self.results)

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

    @property
    def exit_code(self) -> int:
        """返回适合脚本使用的退出码"""
        return 1 if self.has_errors else 0

    def to_dict(self) -> dict:
        """转换为可序列化的字典"""
        return {
            "generated_at": self.generated_at,
            "summary": {
                "total_files": self.total_files,
                "total_errors": self.total_errors,
                "total_warnings": self.total_warnings,
                "total_dead_ends": self.total_dead_ends,
                "total_condition_conflicts": self.total_condition_conflicts,
                "total_pace_abnormal": self.total_pace_abnormal,
                "has_errors": self.has_errors,
                "exit_code": self.exit_code,
            },
            "files_with_errors": [
                {"file_path": r.file_path, "tree_title": r.tree_title}
                for r in self.results if r.has_errors
            ],
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        """导出为JSON格式"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def to_markdown(self) -> str:
        """导出为Markdown格式"""
        lines = []
        lines.append("# 对白树检查报告")
        lines.append("")
        lines.append(f"**生成时间**: {self.generated_at}")
        lines.append("")

        lines.append("## 检查汇总")
        lines.append("")
        lines.append("| 指标 | 数量 |")
        lines.append("|------|------|")
        lines.append(f"| 检查文件数 | {self.total_files} |")
        lines.append(f"| 🚫 死路分支 | {self.total_dead_ends} |")
        lines.append(f"| ⚔️  条件冲突 | {self.total_condition_conflicts} |")
        lines.append(f"| 🎵 节奏异常 | {self.total_pace_abnormal} |")
        lines.append(f"| **总计错误** | **{self.total_errors}** |")
        lines.append(f"| **总计警告** | **{self.total_warnings}** |")
        lines.append("")

        if self.has_errors:
            lines.append("❌ **发现严重错误，请修复后再提交版本**")
        elif self.total_warnings > 0:
            lines.append("⚠️  **发现警告，建议检查**")
        else:
            lines.append("✅ **所有检查通过！可以安全提交版本**")
        lines.append("")

        if self.has_errors:
            lines.append("## 有错误的文件")
            lines.append("")
            for r in self.results:
                if r.has_errors:
                    lines.append(f"- `{r.file_path}` - {r.tree_title}")
            lines.append("")

        lines.append("---")
        lines.append("")

        for result in self.results:
            status_icon = "❌" if result.has_errors else ("⚠️ " if result.warnings else "✅")
            lines.append(f"## {status_icon} {result.tree_title}")
            lines.append("")
            lines.append(f"**文件**: `{result.file_path}`")
            lines.append("")

            if result.has_issues:
                lines.append("### 问题详情")
                lines.append("")

                issues_by_type = {
                    IssueType.DEAD_END: [],
                    IssueType.CONDITION_CONFLICT: [],
                    IssueType.PACE_ABNORMAL: [],
                }
                for issue in result.issues:
                    issues_by_type[issue.type].append(issue)

                type_headers = {
                    IssueType.DEAD_END: "### 🚫 死路分支",
                    IssueType.CONDITION_CONFLICT: "### ⚔️  条件冲突",
                    IssueType.PACE_ABNORMAL: "### 🎵 节奏异常",
                }

                for issue_type, issues in issues_by_type.items():
                    if issues:
                        lines.append(type_headers[issue_type])
                        lines.append("")
                        for idx, issue in enumerate(issues, 1):
                            severity_icon = "🔴" if issue.severity == Severity.ERROR else "🟡"
                            lines.append(f"#### {severity_icon} {idx}. {issue.message}")
                            lines.append("")
                            if issue.node_id:
                                lines.append(f"- **节点**: `{issue.node_id}`")
                            if issue.node_text:
                                lines.append(f"- **文本**: \"{issue.node_text}\"")
                            if issue.path:
                                lines.append(f"- **路径**: {' → '.join(issue.path)}")
                            if issue.details:
                                lines.append("- **详情**:")
                                for detail in issue.details:
                                    lines.append(f"  - {detail}")
                            lines.append("")
            else:
                lines.append("✅ 所有检查通过")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def save_to_file(self, file_path: str, format: str = "json") -> None:
        """保存报告到文件"""
        format = format.lower()
        if format == "json":
            content = self.to_json()
        elif format in ["md", "markdown"]:
            content = self.to_markdown()
        else:
            raise ValueError(f"不支持的格式: {format}，请使用 json 或 markdown")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    @classmethod
    def from_dict(cls, data: dict) -> "CheckReport":
        """从字典创建"""
        return cls(
            results=[CheckResult.from_dict(r) for r in data.get("results", [])],
            generated_at=data.get("generated_at", datetime.now().isoformat()),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "CheckReport":
        """从JSON字符串创建"""
        data = json.loads(json_str)
        return cls.from_dict(data)
