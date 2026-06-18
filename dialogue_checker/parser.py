"""对白文件解析器 - 读取并验证JSON格式的对白文件"""
import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from pydantic import ValidationError

from .models import DialogueTree, DialogueNode, ChoiceOption, Condition


class ParseError(Exception):
    """解析错误异常"""

    def __init__(self, file_path: str, message: str, line_number: Optional[int] = None):
        self.file_path = file_path
        self.message = message
        self.line_number = line_number
        super().__init__(f"{file_path}: {message}")


class DialogueParser:
    """对白文件解析器"""

    def __init__(self, dialogue_dir: str = "dialogues"):
        self.dialogue_dir = Path(dialogue_dir)

    def load_file(self, file_path: str) -> DialogueTree:
        """加载单个对白文件"""
        path = Path(file_path)
        if not path.exists():
            raise ParseError(str(path), "文件不存在")

        if path.suffix.lower() not in [".json"]:
            raise ParseError(str(path), f"不支持的文件格式: {path.suffix}，仅支持.json")

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ParseError(str(path), f"JSON解析错误: {e.msg}", e.lineno)

        try:
            tree = DialogueTree.model_validate(raw_data)
        except ValidationError as e:
            errors = []
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                errors.append(f"字段 [{field}]: {error['msg']}")
            raise ParseError(str(path), "数据验证失败:\n" + "\n".join(errors))

        return tree

    def load_directory(self, dir_path: Optional[str] = None) -> List[Tuple[str, DialogueTree]]:
        """加载目录下所有对白文件"""
        target_dir = Path(dir_path) if dir_path else self.dialogue_dir
        if not target_dir.exists():
            raise ParseError(str(target_dir), "对白目录不存在")

        if not target_dir.is_dir():
            raise ParseError(str(target_dir), "路径不是目录")

        results: List[Tuple[str, DialogueTree]] = []
        for file_path in sorted(target_dir.glob("**/*.json")):
            try:
                tree = self.load_file(str(file_path))
                results.append((str(file_path), tree))
            except ParseError as e:
                results.append((str(file_path), e))

        return results

    def load_single_or_directory(self, path: str) -> List[Tuple[str, DialogueTree]]:
        """加载单个文件或整个目录"""
        p = Path(path)
        if p.is_file():
            tree = self.load_file(str(p))
            return [(str(p), tree)]
        elif p.is_dir():
            return self.load_directory(str(p))
        else:
            raise ParseError(str(p), "路径不存在")
