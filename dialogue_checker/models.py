"""对白树数据模型 - 定义对白文件格式规范"""
from enum import Enum
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator


class NodeType(str, Enum):
    """节点类型"""
    DIALOGUE = "dialogue"      # 角色台词
    CHOICE = "choice"          # 玩家选择
    NARRATION = "narration"    # 旁白/心理描写
    ENDING = "ending"          # 结局节点


class FearIntensity(str, Enum):
    """恐惧强度 - 用于节奏分析"""
    HIGH = "high"       # 高压恐怖场景（jump scare、血腥、直面怪物）
    MEDIUM = "medium"   # 中等紧张（悬念、暗示、诡异氛围）
    LOW = "low"         # 缓冲/放松（日常对话、解释剧情、安全屋）


class DialogueType(str, Enum):
    """对白类型 - 用于节奏分析"""
    TENSION = "tension"     # 高压情节
    EXPOSITION = "exposition"  # 解释说明
    BUFFER = "buffer"       # 缓冲过渡


class Condition(BaseModel):
    """条件表达式 - 用于分支条件判断"""
    variable: str = Field(..., description="变量名，如 'has_memory'、'found_photo'")
    operator: str = Field(default="==", description="比较运算符: ==, !=, >, <, >=, <=, in")
    value: Any = Field(..., description="比较值")
    negation: bool = Field(default=False, description="是否取反")

    def to_expression(self) -> str:
        """转换为可读的表达式字符串"""
        prefix = "NOT " if self.negation else ""
        if self.operator == "==":
            return f"{prefix}{self.variable} == {self.value!r}"
        elif self.operator == "!=":
            return f"{prefix}{self.variable} != {self.value!r}"
        else:
            return f"{prefix}{self.variable} {self.operator} {self.value!r}"

    def conflicts_with(self, other: "Condition") -> bool:
        """判断两个条件是否存在逻辑冲突"""
        if self.variable != other.variable:
            return False
        if self.operator != other.operator:
            return False
        if self.negation == other.negation:
            return False
        if self.value == other.value:
            return True
        return False


class DialogueNode(BaseModel):
    """对白节点 - 构成对白树的基本单元"""
    node_id: str = Field(..., description="节点唯一标识")
    node_type: NodeType = Field(..., description="节点类型")
    speaker: Optional[str] = Field(None, description="说话者，仅对DIALOGUE类型有效")
    text: str = Field(..., description="台词/描述文本")

    choices: Optional[List["ChoiceOption"]] = Field(None, description="玩家选项列表，仅CHOICE节点有效")
    next_node: Optional[str] = Field(None, description="下一个节点ID（无选择时的线性跳转）")

    conditions: Optional[List[Condition]] = Field(None, description="进入此节点需要满足的条件")

    fear_intensity: Optional[FearIntensity] = Field(None, description="恐惧强度等级（用于节奏分析）")
    dialogue_type: Optional[DialogueType] = Field(None, description="对白类型（用于节奏分析）")

    set_variables: Optional[Dict[str, Any]] = Field(None, description="进入此节点时设置的变量")

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("文本内容不能为空")
        return v.strip()


class ChoiceOption(BaseModel):
    """玩家选择项"""
    choice_id: str = Field(..., description="选项唯一标识")
    text: str = Field(..., description="选项显示文本")
    next_node: str = Field(..., description="选择后跳转到的节点ID")
    conditions: Optional[List[Condition]] = Field(None, description="此选项显示需要满足的条件")

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("选项文本不能为空")
        return v.strip()


class DialogueTree(BaseModel):
    """完整的对白树 - 对应一个对白文件"""
    tree_id: str = Field(..., description="对白树唯一标识")
    title: str = Field(..., description="场景/章节标题")
    start_node: str = Field(..., description="起始节点ID")
    description: Optional[str] = Field(None, description="场景描述")
    nodes: Dict[str, DialogueNode] = Field(..., description="所有节点，以node_id为键")

    @field_validator("nodes")
    @classmethod
    def validate_nodes(cls, v: Dict[str, DialogueNode]) -> Dict[str, DialogueNode]:
        for node_id, node in v.items():
            if node.node_id != node_id:
                raise ValueError(f"节点ID不一致: dict键={node_id}, node.node_id={node.node_id}")
        return v

    def get_node(self, node_id: str) -> Optional[DialogueNode]:
        """根据ID获取节点"""
        return self.nodes.get(node_id)

    def has_node(self, node_id: str) -> bool:
        """检查节点是否存在"""
        return node_id in self.nodes

    def get_all_paths(self) -> List[List[str]]:
        """获取所有可能的路径（用于遍历检查）"""
        paths: List[List[str]] = []

        def dfs(current_id: str, current_path: List[str], visited: set):
            if current_id in visited:
                return
            node = self.get_node(current_id)
            if not node:
                return

            new_path = current_path + [current_id]
            new_visited = visited | {current_id}

            if node.node_type == NodeType.ENDING:
                paths.append(new_path)
                return

            if node.choices:
                for choice in node.choices:
                    dfs(choice.next_node, new_path, new_visited)
            elif node.next_node:
                dfs(node.next_node, new_path, new_visited)
            else:
                paths.append(new_path)

        dfs(self.start_node, [], set())
        return paths

    def get_all_edges(self) -> List[tuple[str, str, Optional[str]]]:
        """获取所有边 (from_node, to_node, choice_id)"""
        edges: List[tuple[str, str, Optional[str]]] = []
        for node_id, node in self.nodes.items():
            if node.choices:
                for choice in node.choices:
                    edges.append((node_id, choice.next_node, choice.choice_id))
            elif node.next_node:
                edges.append((node_id, node.next_node, None))
        return edges


DialogueNode.model_rebuild()
