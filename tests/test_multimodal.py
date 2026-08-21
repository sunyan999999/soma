# -*- coding: utf-8 -*-
"""多模态记忆测试 — v2.0.10 图片/表格"""
import pytest

from soma import SOMA
from soma.multimodal import ImageMemory, TableMemory


@pytest.fixture
def soma(tmp_path):
    s = SOMA(persist_dir=str(tmp_path), llm="mock")
    yield s
    s.close()


class TestTableMemory:
    def test_analyze_rows_and_columns(self):
        table = TableMemory(title="营收", data=[{"季度": "Q1", "营收": "100万"}])
        meta = table.analyze()
        assert meta["row_count"] == 1
        assert meta["columns"] == ["季度", "营收"]
        assert meta["content_type"] == "table"

    def test_parse_markdown(self):
        table = TableMemory(markdown_table="|名称|数量|\n|---|--:|\n|苹果|3|\n|香蕉|5|")
        assert len(table.data) == 2
        meta = table.analyze()
        assert meta["row_count"] == 2
        assert "名称" in meta["columns"]

    def test_parse_csv(self):
        table = TableMemory(csv_text="a,b\n1,2\n3,4")
        assert len(table.data) == 2
        assert table.data[0] == {"a": "1", "b": "2"}

    def test_empty_table(self):
        meta = TableMemory(title="空").analyze()
        assert meta["row_count"] == 0
        assert meta["summary"] == "空表格"

    def test_to_memory_content(self):
        table = TableMemory(title="营收", data=[{"季度": "Q1", "营收": "100万"}])
        content = table.to_memory_content(table.analyze())
        assert "[表格]" in content
        assert "营收" in content


class TestImageMemory:
    def test_no_image_path(self):
        img = ImageMemory(description="架构图")
        meta = img.analyze()
        assert meta["content_type"] == "image"
        assert meta["description"] == "架构图"
        assert "image_path" not in meta or not meta.get("image_path")

    def test_image_path_meta(self, tmp_path):
        p = tmp_path / "test.png"
        p.write_bytes(b"\x89PNG fake")
        img = ImageMemory(image_path=str(p), description="测试图", use_ocr=False)
        meta = img.analyze()
        assert meta["file_size_bytes"] == 9
        assert meta["extension"] == ".png"

    def test_ocr_fallback_when_no_library(self):
        # 未安装 pytesseract 时 OCR 静默返回空
        img = ImageMemory(description="无图")
        assert img._try_ocr("x.png") == ""

    def test_to_memory_content(self):
        img = ImageMemory(image_path="a.png", description="图表")
        content = img.to_memory_content({"description": "图表", "image_path": "a.png"})
        assert "[图片]" in content
        assert "a.png" in content


class TestSOMAMultimodal:
    def test_remember_table(self, soma):
        r = soma.remember_table(data=[{"k": "v"}], title="测试表")
        assert r["memory_id"]
        assert r["meta"]["row_count"] == 1
        # 记忆可检索
        results = soma.query_memory("测试表", top_k=3)
        assert len(results) >= 1

    def test_remember_image(self, soma):
        r = soma.remember_image(description="一张架构图", use_ocr=False)
        assert r["memory_id"]
        assert r["meta"]["content_type"] == "image"
