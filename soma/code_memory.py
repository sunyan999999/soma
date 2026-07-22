"""代码结构化记忆 — AST 感知的代码记忆分析器

将代码片段解析为结构化表示（函数/类/调用关系），
自动生成语义三元组，存入 MemoryUnit.structured_data。

支持语言: Python（ast 模块，零外部依赖）

用法::

    from soma.code_memory import CodeAnalyzer

    analyzer = CodeAnalyzer()
    structure = analyzer.analyze(code)
    # → 提取函数签名、类定义、调用图
    triples = analyzer.to_semantic_triples(structure)
    # → [("func_a", "CALLS", "func_b"), ("class_x", "INHERITS", "base_y")]
"""

import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FunctionInfo:
    """函数/方法信息"""
    name: str
    args: List[str]
    decorators: List[str]
    docstring: Optional[str] = None
    line_start: int = 0
    line_end: int = 0
    is_async: bool = False
    returns: Optional[str] = None


@dataclass
class ClassInfo:
    """类定义信息"""
    name: str
    base_classes: List[str]
    methods: List[FunctionInfo] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    line_start: int = 0
    line_end: int = 0


@dataclass
class CallRelation:
    """函数调用关系"""
    caller: str
    callee: str
    line: int


@dataclass
class ImportInfo:
    """导入信息"""
    module: str
    names: List[str] = field(default_factory=list)
    is_from_import: bool = False
    alias: Optional[str] = None


@dataclass
class CodeStructure:
    """代码结构化分析结果"""
    language: str = "python"
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    imports: List[ImportInfo] = field(default_factory=list)
    call_graph: List[CallRelation] = field(default_factory=list)
    summary: str = ""
    total_lines: int = 0


class CodeAnalyzer:
    """AST 驱动的代码结构分析器

    纯 Python ast 模块，零外部依赖。
    当前支持 Python，接口预留 language 参数用于未来扩展。
    """

    SUPPORTED_LANGUAGES = ["python"]

    def analyze(self, code: str, language: str = "python") -> CodeStructure:
        """解析代码并提取完整结构。

        Args:
            code: 源代码文本
            language: 编程语言（目前仅 python）

        Returns:
            CodeStructure 包含函数/类/导入/调用图/摘要
        """
        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"不支持的语言 {language!r}，目前支持: {self.SUPPORTED_LANGUAGES}"
            )

        lines = code.split("\n")
        structure = CodeStructure(
            language=language,
            total_lines=len(lines),
        )

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            structure.summary = f"[语法错误] {e}"
            return structure

        # 第一遍：收集所有定义
        name_to_node = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                info = self._extract_function(node)
                # 判断是否为顶层函数
                for parent in ast.walk(tree):
                    if isinstance(parent, ast.ClassDef) and node in ast.walk(parent):
                        break
                else:
                    structure.functions.append(info)
                name_to_node[node.name] = node
            elif isinstance(node, ast.AsyncFunctionDef):
                info = self._extract_function(node)
                info.is_async = True
                structure.functions.append(info)
                name_to_node[node.name] = node
            elif isinstance(node, ast.ClassDef):
                info = self._extract_class(node)
                structure.classes.append(info)
                name_to_node[node.name] = node

        # 第二遍：收集调用图
        defined_names = set(name_to_node.keys())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                callee = self._resolve_callee(node)
                if callee and callee in defined_names:
                    caller = self._find_enclosing_function(tree, node)
                    if caller:
                        structure.call_graph.append(
                            CallRelation(
                                caller=caller,
                                callee=callee,
                                line=getattr(node, "lineno", 0),
                            )
                        )

        # 收集导入
        structure.imports = self._extract_imports(tree)

        # 生成摘要
        structure.summary = self._build_summary(structure)

        return structure

    # ── 私有提取方法 ─────────────────────────────────────────────

    def _extract_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> FunctionInfo:
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)
        # *args, **kwargs
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")

        decorators = []
        for dec in node.decorator_list:
            decorators.append(ast.unparse(dec))

        returns_annotation = None
        if node.returns:
            returns_annotation = ast.unparse(node.returns)

        return FunctionInfo(
            name=node.name,
            args=args,
            decorators=decorators,
            docstring=ast.get_docstring(node),
            line_start=node.lineno,
            line_end=getattr(node, "end_lineno", node.lineno),
            is_async=isinstance(node, ast.AsyncFunctionDef),
            returns=returns_annotation,
        )

    def _extract_class(self, node: ast.ClassDef) -> ClassInfo:
        bases = [ast.unparse(b) for b in node.bases]
        decorators = [ast.unparse(d) for d in node.decorator_list]
        methods = []
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                m = self._extract_function(child)
                m.is_async = isinstance(child, ast.AsyncFunctionDef)
                methods.append(m)

        return ClassInfo(
            name=node.name,
            base_classes=bases,
            methods=methods,
            decorators=decorators,
            docstring=ast.get_docstring(node),
            line_start=node.lineno,
            line_end=getattr(node, "end_lineno", node.lineno),
        )

    def _extract_imports(self, tree: ast.AST) -> List[ImportInfo]:
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportInfo(
                        module=alias.name,
                        names=[alias.name],
                        alias=alias.asname,
                    ))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]
                imports.append(ImportInfo(
                    module=module,
                    names=names,
                    is_from_import=True,
                ))
        return imports

    def _resolve_callee(self, node: ast.Call) -> Optional[str]:
        """解析调用表达式中的被调函数名"""
        func = node.func
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return None

    def _find_enclosing_function(self, tree: ast.AST, target: ast.AST) -> Optional[str]:
        """查找包含 target 节点的函数名"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if child is target:
                        return node.name
        return None

    def _build_summary(self, s: CodeStructure) -> str:
        """生成一句代码结构摘要"""
        parts = []
        if s.functions:
            parts.append(f"{len(s.functions)}个函数")
        if s.classes:
            parts.append(f"{len(s.classes)}个类")
        if s.call_graph:
            parts.append(f"{len(s.call_graph)}条调用关系")
        if not parts:
            return f"{s.total_lines}行代码，无函数/类定义"
        return "，".join(parts)

    # ── 语义转换 ─────────────────────────────────────────────────

    def to_structured_data(self, structure: CodeStructure) -> dict:
        """将 CodeStructure 转为 MemoryUnit.structured_data 兼容格式"""
        return {
            "language": structure.language,
            "functions": [
                {
                    "name": f.name,
                    "args": f.args,
                    "decorators": f.decorators,
                    "docstring": f.docstring,
                    "line_start": f.line_start,
                    "line_end": f.line_end,
                    "is_async": f.is_async,
                    "returns": f.returns,
                }
                for f in structure.functions
            ],
            "classes": [
                {
                    "name": c.name,
                    "base_classes": c.base_classes,
                    "methods": [
                        {"name": m.name, "args": m.args}
                        for m in c.methods
                    ],
                    "decorators": c.decorators,
                    "docstring": c.docstring,
                    "line_start": c.line_start,
                    "line_end": c.line_end,
                }
                for c in structure.classes
            ],
            "imports": [
                {"module": i.module, "names": i.names, "from_import": i.is_from_import}
                for i in structure.imports
            ],
            "call_graph": [
                {"caller": r.caller, "callee": r.callee, "line": r.line}
                for r in structure.call_graph
            ],
            "summary": structure.summary,
            "total_lines": structure.total_lines,
        }

    def to_semantic_triples(self, structure: CodeStructure) -> List[tuple]:
        """将代码结构转换为语义三元组列表

        可用于 SOMA SemanticStore 自动填充。
        返回: [(subject, predicate, object), ...]

        示例:
            ("func_a", "CALLS", "func_b")
            ("class_x", "INHERITS", "base_y")
            ("class_x", "HAS_METHOD", "method_z")
        """
        triples = []

        # 调用关系
        for rel in structure.call_graph:
            triples.append((rel.caller, "CALLS", rel.callee))

        # 继承关系
        for cls in structure.classes:
            for base in cls.base_classes:
                triples.append((cls.name, "INHERITS", base))
            for method in cls.methods:
                triples.append((cls.name, "HAS_METHOD", method.name))

        # 导入关系（核心模块级）
        seen_modules = set()
        for imp in structure.imports[:10]:  # 只取前10个避免过多
            for name in imp.names:
                key = f"{imp.module}.{name}"
                if key not in seen_modules:
                    seen_modules.add(key)
                    module_part = imp.module.split(".")[0] if imp.module else name
                    triples.append(("this_module", "IMPORTS", module_part))

        return triples

    def analyze_and_enrich(self, code: str, language: str = "python") -> dict:
        """一行调用：分析代码并返回 structured_data + triples"""
        structure = self.analyze(code, language)
        return {
            "structured_data": self.to_structured_data(structure),
            "semantic_triples": self.to_semantic_triples(structure),
            "summary": structure.summary,
        }
