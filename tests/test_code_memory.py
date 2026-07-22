"""代码结构化记忆测试"""
import pytest
from soma.code_memory import (
    CodeAnalyzer, CodeStructure, FunctionInfo, ClassInfo,
    CallRelation, ImportInfo,
)


class TestCodeAnalyzer:
    """CodeAnalyzer 单元测试"""

    def setup_method(self):
        self.analyzer = CodeAnalyzer()

    def test_empty_code(self):
        s = self.analyzer.analyze("")
        assert s.total_lines == 1  # empty string → 1 line
        assert len(s.functions) == 0
        assert len(s.classes) == 0

    def test_single_function(self):
        code = '''def hello(name: str) -> str:
    """Say hello"""
    return f"Hello, {name}"'''

        s = self.analyzer.analyze(code)
        assert len(s.functions) == 1
        f = s.functions[0]
        assert f.name == "hello"
        assert len(f.args) == 1
        assert "name: str" in f.args[0]
        assert f.docstring == "Say hello"
        assert f.returns == "str"
        assert not f.is_async

    def test_async_function(self):
        code = '''async def fetch_data(url: str):
    return await some_call(url)'''

        s = self.analyzer.analyze(code)
        assert len(s.functions) == 1
        assert s.functions[0].is_async
        assert s.functions[0].name == "fetch_data"

    def test_class_with_methods(self):
        code = '''class Calculator:
    """A simple calculator"""

    def add(self, a: int, b: int) -> int:
        return a + b

    def subtract(self, a: int, b: int) -> int:
        return a - b'''

        s = self.analyzer.analyze(code)
        assert len(s.classes) == 1
        c = s.classes[0]
        assert c.name == "Calculator"
        assert c.docstring == "A simple calculator"
        assert len(c.methods) == 2
        assert c.methods[0].name == "add"
        assert c.methods[1].name == "subtract"

    def test_inheritance(self):
        code = '''class Dog(Animal, Pet):
    def bark(self):
        pass'''

        s = self.analyzer.analyze(code)
        assert len(s.classes) == 1
        c = s.classes[0]
        assert c.base_classes == ["Animal", "Pet"]

    def test_call_graph(self):
        code = '''def compute(x):
    return helper(x)

def helper(x):
    return x * 2

def main():
    result = compute(5)
    return result'''

        s = self.analyzer.analyze(code)
        assert len(s.call_graph) >= 1
        callers = {r.caller for r in s.call_graph}
        assert "compute" in callers or "main" in callers

    def test_decorators(self):
        code = '''@staticmethod
@validate
def process(data):
    pass'''

        s = self.analyzer.analyze(code)
        assert len(s.functions) == 1
        f = s.functions[0]
        assert "staticmethod" in f.decorators
        assert "validate" in f.decorators

    def test_imports(self):
        code = '''import os
from collections import defaultdict, Counter
from soma.base import MemoryUnit'''

        s = self.analyzer.analyze(code)
        assert len(s.imports) >= 2
        modules = {i.module for i in s.imports}
        assert "os" in modules
        assert "collections" in modules

    def test_syntax_error(self):
        code = '''def broken(:\n    pass'''
        s = self.analyzer.analyze(code)
        assert "[语法错误]" in s.summary

    def test_unsupported_language(self):
        with pytest.raises(ValueError, match="不支持的语言"):
            self.analyzer.analyze("int main() {}", language="cpp")

    def test_summary_generation(self):
        code = '''def foo(): pass

class Bar:
    def method(self): pass'''

        s = self.analyzer.analyze(code)
        assert "函数" in s.summary or "function" in s.summary.lower()
        assert "类" in s.summary or "class" in s.summary.lower()


class TestStructuredData:
    """to_structured_data + to_semantic_triples 测试"""

    def setup_method(self):
        self.analyzer = CodeAnalyzer()

    def test_to_structured_data(self):
        code = '''def factorial(n: int) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)
'''

        s = self.analyzer.analyze(code)
        data = self.analyzer.to_structured_data(s)
        assert data["language"] == "python"
        assert len(data["functions"]) == 1
        assert data["functions"][0]["name"] == "factorial"
        assert data["functions"][0]["returns"] == "int"

    def test_to_semantic_triples_with_inheritance(self):
        code = '''class Base:
    pass

class Derived(Base):
    def method(self):
        pass'''

        s = self.analyzer.analyze(code)
        triples = self.analyzer.to_semantic_triples(s)
        # 应该有 INHERITS 和 HAS_METHOD
        predicates = {t[1] for t in triples}
        assert "INHERITS" in predicates
        assert "HAS_METHOD" in predicates

    def test_to_semantic_triples_with_calls(self):
        code = '''def a():
    return b()

def b():
    return 1'''

        s = self.analyzer.analyze(code)
        triples = self.analyzer.to_semantic_triples(s)
        calls = [t for t in triples if t[1] == "CALLS"]
        assert len(calls) >= 1

    def test_analyze_and_enrich(self):
        code = '''class Stack:
    def push(self, item):
        pass
    def pop(self):
        pass'''

        result = self.analyzer.analyze_and_enrich(code)
        assert "structured_data" in result
        assert "semantic_triples" in result
        assert "summary" in result
        assert len(result["semantic_triples"]) >= 2  # HAS_METHOD x2


class TestDataClasses:
    """数据类基本创建测试"""

    def test_function_info_defaults(self):
        f = FunctionInfo(name="test", args=[], decorators=[])
        assert f.name == "test"
        assert f.docstring is None
        assert not f.is_async

    def test_class_info_defaults(self):
        c = ClassInfo(name="MyClass", base_classes=[], decorators=[])
        assert c.name == "MyClass"
        assert c.methods == []

    def test_call_relation(self):
        r = CallRelation(caller="a", callee="b", line=42)
        assert r.caller == "a"
        assert r.callee == "b"
        assert r.line == 42

    def test_import_info(self):
        i = ImportInfo(module="os", alias=None)
        assert i.module == "os"
        assert not i.is_from_import
