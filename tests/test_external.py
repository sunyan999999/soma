"""外部知识集成测试"""
import json
import time
import pytest
from pathlib import Path
from soma.memory.external import (
    KnowledgeSource,
    FileSource,
    URLSource,
    ExternalKnowledgeImporter,
)


class TestFileSource:
    def test_md_file_extracts_paragraphs(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# 标题\n\n第一段内容。\n\n第二段内容，更多文字。", encoding="utf-8")

        source = FileSource(str(md_file))
        assert "test.md" in source.name()

        items = source.extract()
        assert len(items) >= 1
        content = " ".join(i["content"] for i in items)
        assert "第一段内容" in content
        assert "第二段内容" in content

    def test_txt_file_extracts_content(self, tmp_path):
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("系统思维是整体论的核心方法。\n\n它强调关系而非元素。", encoding="utf-8")

        source = FileSource(str(txt_file))
        items = source.extract()
        assert len(items) >= 1
        full = " ".join(i["content"] for i in items)
        assert "系统思维" in full
        assert "整体论" in full

    def test_json_file_extracts_items(self, tmp_path):
        json_file = tmp_path / "data.json"
        data = {
            "rule1": "第一性原理回归本质",
            "rule2": "系统思维看整体",
        }
        json_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        source = FileSource(str(json_file))
        items = source.extract()
        assert len(items) == 2
        contents = [i["content"] for i in items]
        assert any("第一性原理" in c for c in contents)
        assert any("系统思维" in c for c in contents)

    def test_json_array_extracts_elements(self, tmp_path):
        json_file = tmp_path / "list.json"
        data = [
            {"text": "知识条目A"},
            {"text": "知识条目B"},
        ]
        json_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        source = FileSource(str(json_file))
        items = source.extract()
        assert len(items) == 2

    def test_jsonl_file_extracts_lines(self, tmp_path):
        jsonl_file = tmp_path / "data.jsonl"
        jsonl_file.write_text(
            '{"text": "第一行知识"}\n{"text": "第二行知识"}\n',
            encoding="utf-8",
        )

        source = FileSource(str(jsonl_file))
        items = source.extract()
        assert len(items) == 2

    def test_chunking_large_content(self, tmp_path):
        md_file = tmp_path / "large.md"
        # 生成超过chunk_size的内容
        paragraphs = [f"段落{i}: " + "知识" * 100 for i in range(10)]
        md_file.write_text("\n\n".join(paragraphs), encoding="utf-8")

        source = FileSource(str(md_file), chunk_size=200)
        items = source.extract()
        # 小chunk_size应该产生多个块
        assert len(items) >= 2

    def test_context_includes_source_and_index(self, tmp_path):
        md_file = tmp_path / "ctx.md"
        md_file.write_text("测试内容。", encoding="utf-8")

        source = FileSource(str(md_file))
        items = source.extract()
        assert len(items) == 1
        ctx = items[0]["context"]
        assert "source" in ctx
        assert "chunk_index" in ctx
        assert ctx["chunk_index"] == 0

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            FileSource(str(tmp_path / "nonexistent.md"))

    def test_unsupported_suffix_raises(self, tmp_path):
        bad = tmp_path / "image.png"
        bad.write_text("fake", encoding="utf-8")
        with pytest.raises(ValueError, match="不支持的文件类型"):
            FileSource(str(bad))

    def test_default_importance(self, tmp_path):
        md_file = tmp_path / "imp.md"
        md_file.write_text("内容", encoding="utf-8")
        source = FileSource(str(md_file))
        assert source.default_importance == 0.6
        assert source.default_expiry_days == 30

    def test_empty_file_returns_empty(self, tmp_path):
        md_file = tmp_path / "empty.md"
        md_file.write_text("", encoding="utf-8")
        source = FileSource(str(md_file))
        items = source.extract()
        assert items == []

    def test_whitespace_only_paragraphs_skipped(self, tmp_path):
        md_file = tmp_path / "spaces.md"
        md_file.write_text("   \n\n  \n\n有效内容。", encoding="utf-8")
        source = FileSource(str(md_file))
        items = source.extract()
        assert len(items) == 1
        assert "有效内容" in items[0]["content"]


class TestURLSource:
    def test_name_uses_hostname(self):
        source = URLSource("https://example.com/article")
        assert "example.com" in source.name()

    def test_invalid_protocol_raises(self):
        with pytest.raises(ValueError, match="不支持的URL协议"):
            URLSource("ftp://files.example.com/data")

    def test_url_construction(self):
        source = URLSource("https://zhuanlan.zhihu.com/p/12345", max_length=1000)
        assert source._url == "https://zhuanlan.zhihu.com/p/12345"
        assert source._max_length == 1000


class TestExternalKnowledgeImporter:
    @pytest.fixture
    def store(self, tmp_path):
        from soma.memory.episodic import EpisodicStore
        s = EpisodicStore(tmp_path)
        yield s
        s.close()

    def test_import_markdown_file(self, store, tmp_path):
        md_file = tmp_path / "knowledge.md"
        md_file.write_text("# 外部知识\n\n第一性原理是回归事物本质的思考方式。", encoding="utf-8")

        source = FileSource(str(md_file))
        importer = ExternalKnowledgeImporter(store)
        ids = importer.import_source(source)

        assert len(ids) >= 1
        # 验证记忆已存储
        mem = store.get(ids[0])
        assert mem is not None
        assert "第一性原理" in mem.content
        assert mem.context.get("_external") is True
        assert mem.context.get("_source_name") == source.name()

    def test_imported_memory_type_is_external(self, store, tmp_path):
        md_file = tmp_path / "ext.md"
        md_file.write_text("外部知识内容。", encoding="utf-8")

        source = FileSource(str(md_file))
        importer = ExternalKnowledgeImporter(store)
        ids = importer.import_source(source)

        assert len(ids) >= 1
        row = store._conn.execute(
            "SELECT memory_type FROM episodic_memories WHERE id = ?", (ids[0],)
        ).fetchone()
        assert row["memory_type"] == "external"

    def test_import_with_user_id(self, store, tmp_path):
        md_file = tmp_path / "user_knowledge.md"
        md_file.write_text("用户专属知识。", encoding="utf-8")

        source = FileSource(str(md_file))
        importer = ExternalKnowledgeImporter(store)
        ids = importer.import_source(source, user_id="user_x", session_id="sess_1")

        assert len(ids) >= 1
        mem = store.get(ids[0])
        assert mem.user_id == "user_x"
        assert mem.session_id == "sess_1"

    def test_check_expired_marks_zero_importance(self, store, tmp_path):
        md_file = tmp_path / "expire.md"
        md_file.write_text("即将过期的知识。", encoding="utf-8")

        source = FileSource(str(md_file))
        importer = ExternalKnowledgeImporter(store)
        ids = importer.import_source(source)

        # 手动修改时间戳为31天前（超过默认30天过期）
        old_ts = time.time() - 31 * 86400
        store._conn.execute(
            "UPDATE episodic_memories SET timestamp = ? WHERE id = ?",
            (old_ts, ids[0]),
        )
        store._conn.commit()

        expired = importer.check_expired()
        assert expired >= 1

        mem = store.get(ids[0])
        assert mem.importance == 0.0

    def test_check_expired_respects_custom_expiry(self, store, tmp_path):
        """自定义过期天数被遵守"""
        md_file = tmp_path / "custom_exp.md"
        md_file.write_text("自定义过期知识。", encoding="utf-8")

        source = FileSource(str(md_file))
        importer = ExternalKnowledgeImporter(store)
        ids = importer.import_source(source)

        # 手动设置 _expires_in_days=7 且时间戳为8天前
        old_ts = time.time() - 8 * 86400
        store._conn.execute(
            "UPDATE episodic_memories SET timestamp = ?, context_json = ? WHERE id = ?",
            (old_ts, '{"_external": true, "_expires_in_days": 7, "_source_name": "test"}', ids[0]),
        )
        store._conn.commit()

        expired = importer.check_expired()
        assert expired >= 1

    def test_check_expired_skips_unexpired(self, store, tmp_path):
        md_file = tmp_path / "fresh.md"
        md_file.write_text("未过期的知识。", encoding="utf-8")

        source = FileSource(str(md_file))
        importer = ExternalKnowledgeImporter(store)
        ids = importer.import_source(source)

        # 仅1天前——未过期
        recent_ts = time.time() - 1 * 86400
        store._conn.execute(
            "UPDATE episodic_memories SET timestamp = ? WHERE id = ?",
            (recent_ts, ids[0]),
        )
        store._conn.commit()

        expired = importer.check_expired()
        assert expired == 0

        mem = store.get(ids[0])
        assert mem.importance > 0

    def test_episodic_store_import_knowledge_integration(self, store, tmp_path):
        """EpisodicStore.import_knowledge() 集成调用"""
        md_file = tmp_path / "integrate.md"
        md_file.write_text("# 集成测试\n\n外部知识导入集成测试。", encoding="utf-8")

        ids = store.import_knowledge(str(md_file))
        assert len(ids) >= 1

        mem = store.get(ids[0])
        assert mem is not None
        assert mem.context.get("_external") is True

    def test_empty_import_returns_empty_list(self, store, tmp_path):
        md_file = tmp_path / "empty_import.md"
        md_file.write_text("   \n\n   \n", encoding="utf-8")

        source = FileSource(str(md_file))
        importer = ExternalKnowledgeImporter(store)
        ids = importer.import_source(source)
        assert ids == []
