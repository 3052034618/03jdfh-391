"""恐惧节奏异常检测器 - 分析分支节奏，检测连续高压、连续解释、缺少缓冲"""
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from ..models import DialogueTree, DialogueNode, FearIntensity, DialogueType, NodeType
from .base import CheckIssue, IssueType, Severity, CheckResult


class PaceAbnormality:
    """节奏异常类型"""
    CONTINUOUS_HIGH_TENSION = "continuous_high_tension"    # 连续高压
    CONTINUOUS_EXPOSITION = "continuous_exposition"        # 连续解释
    LACK_OF_BUFFER = "lack_of_buffer"                      # 缺少缓冲


class PaceChecker:
    """恐惧节奏异常检测器

    检测以下问题：
    1. 连续高压：连续N个节点都是高恐怖强度，导致玩家疲劳
    2. 连续解释：连续N个节点都是解释说明，导致节奏拖沓
    3. 缺少缓冲：高压场景后没有缓冲直接进入下一个高压

    可配置的阈值：
    - max_continuous_high: 最大连续高压节点数（默认3）
    - max_continuous_exposition: 最大连续解释节点数（默认3）
    - require_buffer_after_high: 高压后是否需要缓冲（默认True）
    """

    def __init__(
        self,
        max_continuous_high: int = 3,
        max_continuous_exposition: int = 3,
        require_buffer_after_high: bool = True,
    ):
        self.max_continuous_high = max_continuous_high
        self.max_continuous_exposition = max_continuous_exposition
        self.require_buffer_after_high = require_buffer_after_high

    def check(self, file_path: str, tree: DialogueTree) -> CheckResult:
        """执行节奏异常检测"""
        result = CheckResult(file_path=file_path, tree_title=tree.title)
        all_paths = tree.get_all_paths()

        if not all_paths:
            result.issues.append(CheckIssue(
                type=IssueType.PACE_ABNORMAL,
                severity=Severity.WARNING,
                message="无法获取有效路径，节奏分析跳过",
                file_path=file_path,
                details=["请检查对白树是否有完整的分支结构"],
            ))
            return result

        branch_issues: Dict[str, List[CheckIssue]] = defaultdict(list)

        for path in all_paths:
            path_key = " → ".join(path)
            path_issues = self._analyze_path(file_path, tree, path)
            branch_issues[path_key].extend(path_issues)

        for path_key, issues in branch_issues.items():
            unique_issues = self._deduplicate_path_issues(issues)
            result.issues.extend(unique_issues)

        return result

    def _analyze_path(
        self,
        file_path: str,
        tree: DialogueTree,
        path: List[str],
    ) -> List[CheckIssue]:
        """分析单条路径的节奏"""
        issues: List[CheckIssue] = []

        intensity_sequence: List[Tuple[str, Optional[FearIntensity]]] = []
        type_sequence: List[Tuple[str, Optional[DialogueType]]] = []

        for node_id in path:
            node = tree.get_node(node_id)
            if not node:
                continue
            intensity_sequence.append((node_id, node.fear_intensity))
            type_sequence.append((node_id, node.dialogue_type))

        issues.extend(self._check_continuous_high(file_path, tree, path, intensity_sequence))
        issues.extend(self._check_continuous_exposition(file_path, tree, path, type_sequence))
        issues.extend(self._check_lack_of_buffer(file_path, tree, path, intensity_sequence, type_sequence))

        return issues

    def _check_continuous_high(
        self,
        file_path: str,
        tree: DialogueTree,
        path: List[str],
        intensity_sequence: List[Tuple[str, Optional[FearIntensity]]],
    ) -> List[CheckIssue]:
        """检查连续高压"""
        issues: List[CheckIssue] = []
        high_run: List[str] = []

        for node_id, intensity in intensity_sequence:
            if intensity == FearIntensity.HIGH:
                high_run.append(node_id)
            else:
                if len(high_run) > self.max_continuous_high:
                    issues.append(self._create_pace_issue(
                        file_path,
                        tree,
                        path,
                        high_run,
                        PaceAbnormality.CONTINUOUS_HIGH_TENSION,
                        f"连续 {len(high_run)} 个高压节点，超过阈值 {self.max_continuous_high}",
                        [
                            "问题: 玩家可能产生恐怖疲劳，恐惧感反而下降",
                            "建议: 在中间插入1-2个中低强度的过渡节点",
                        ],
                    ))
                high_run = []

        if len(high_run) > self.max_continuous_high:
            issues.append(self._create_pace_issue(
                file_path,
                tree,
                path,
                high_run,
                PaceAbnormality.CONTINUOUS_HIGH_TENSION,
                f"连续 {len(high_run)} 个高压节点，超过阈值 {self.max_continuous_high}",
                [
                    "问题: 玩家可能产生恐怖疲劳，恐惧感反而下降",
                    "建议: 在中间插入1-2个中低强度的过渡节点",
                ],
            ))

        return issues

    def _check_continuous_exposition(
        self,
        file_path: str,
        tree: DialogueTree,
        path: List[str],
        type_sequence: List[Tuple[str, Optional[DialogueType]]],
    ) -> List[CheckIssue]:
        """检查连续解释"""
        issues: List[CheckIssue] = []
        exposition_run: List[str] = []

        for node_id, dtype in type_sequence:
            if dtype == DialogueType.EXPOSITION:
                exposition_run.append(node_id)
            else:
                if len(exposition_run) > self.max_continuous_exposition:
                    issues.append(self._create_pace_issue(
                        file_path,
                        tree,
                        path,
                        exposition_run,
                        PaceAbnormality.CONTINUOUS_EXPOSITION,
                        f"连续 {len(exposition_run)} 个解释节点，超过阈值 {self.max_continuous_exposition}",
                        [
                            "问题: 连续解释剧情会让玩家感到拖沓无聊",
                            "建议: 将部分解释穿插在互动或探索中，或者插入小悬念",
                        ],
                    ))
                exposition_run = []

        if len(exposition_run) > self.max_continuous_exposition:
            issues.append(self._create_pace_issue(
                file_path,
                tree,
                path,
                exposition_run,
                PaceAbnormality.CONTINUOUS_EXPOSITION,
                f"连续 {len(exposition_run)} 个解释节点，超过阈值 {self.max_continuous_exposition}",
                [
                    "问题: 连续解释剧情会让玩家感到拖沓无聊",
                    "建议: 将部分解释穿插在互动或探索中，或者插入小悬念",
                ],
            ))

        return issues

    def _check_lack_of_buffer(
        self,
        file_path: str,
        tree: DialogueTree,
        path: List[str],
        intensity_sequence: List[Tuple[str, Optional[FearIntensity]]],
        type_sequence: List[Tuple[str, Optional[DialogueType]]],
    ) -> List[CheckIssue]:
        """检查缺少缓冲"""
        if not self.require_buffer_after_high:
            return []

        issues: List[CheckIssue] = []
        type_map = {node_id: dtype for node_id, dtype in type_sequence}

        for i in range(len(intensity_sequence) - 1):
            current_id, current_intensity = intensity_sequence[i]
            next_id, next_intensity = intensity_sequence[i + 1]

            if current_intensity == FearIntensity.HIGH:
                next_type = type_map.get(next_id)
                next_intensity = next_intensity

                if next_intensity == FearIntensity.HIGH and next_type != DialogueType.BUFFER:
                    next_node = tree.get_node(next_id)
                    issues.append(CheckIssue(
                        type=IssueType.PACE_ABNORMAL,
                        severity=Severity.WARNING,
                        message="高压场景后缺少缓冲",
                        file_path=file_path,
                        node_id=next_id,
                        node_text=next_node.text if next_node else None,
                        path=path,
                        details=[
                            f"前序高压节点: {current_id}",
                            f"当前节点强度: {next_intensity.value if next_intensity else '未设置'}",
                            f"当前节点类型: {next_type.value if next_type else '未设置'}",
                            "问题: 两个高压场景连在一起，缺少让玩家喘口气的缓冲",
                            "建议: 在中间插入一个低强度的缓冲节点（如安全屋、日常对话）",
                        ],
                    ))
                    break

        return issues

    def _create_pace_issue(
        self,
        file_path: str,
        tree: DialogueTree,
        path: List[str],
        node_ids: List[str],
        abnormality: str,
        message: str,
        details: List[str],
    ) -> CheckIssue:
        """创建节奏异常问题"""
        first_node = tree.get_node(node_ids[0])
        last_node = tree.get_node(node_ids[-1])

        node_details = []
        for nid in node_ids:
            node = tree.get_node(nid)
            if node:
                text_preview = node.text[:30] + "..." if len(node.text) > 30 else node.text
                node_details.append(f"  {nid}: \"{text_preview}\"")

        full_details = [
            f"涉及节点 ({len(node_ids)}个):",
            *node_details,
            *details,
        ]

        return CheckIssue(
            type=IssueType.PACE_ABNORMAL,
            severity=Severity.WARNING,
            message=message,
            file_path=file_path,
            node_id=node_ids[0],
            node_text=first_node.text if first_node else None,
            path=path,
            details=full_details,
        )

    def _deduplicate_path_issues(self, issues: List[CheckIssue]) -> List[CheckIssue]:
        """去重同一路径的重复问题"""
        seen = set()
        unique = []
        for issue in issues:
            path_key = " → ".join(issue.path or [])
            detail_key = "|".join(issue.details or [])
            key = (issue.node_id, path_key, detail_key)
            if key not in seen:
                seen.add(key)
                unique.append(issue)
        return unique
