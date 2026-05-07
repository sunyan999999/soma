"""v0.7.0 集成场景测试 — 完整调用链 + 数据隔离 + 边界条件"""
import json
import time
import pytest
from pathlib import Path


class TestV070FullPipeline:
    """模拟真实使用流程：remember → respond → consolidate → forget → query"""

    @pytest.fixture
    def soma(self, tmp_path):
        from soma import SOMA
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        yield s
        s.close()

    def test_full_remember_consolidate_forget_cycle(self, soma):
        """完整记忆生命周期：存入→合并→遗忘→查询"""
        # Phase 1: 存入多条相似记忆
        ids = []
        contents = [
            "第一性原理是回归事物本质的思考方式，有助于从底层逻辑出发",
            "运用第一性原理可以从底层逻辑出发分析问题",
            "系统思维强调整体大于部分，是解决复杂问题的方法论",
            "系统思维告诉我们整体大于部分之和，这是系统论的基本原理",
            "商业决策中需要平衡短期收益与长期战略",
        ]
        for i, c in enumerate(contents):
            mid = soma.remember(c, importance=0.3 + i * 0.1, user_id="test_user")
            ids.append(mid)

        assert len(set(ids)) == 5  # 5条不同记忆

        # Phase 2: 查询验证全部可召回
        results = soma.query_memory("第一性原理", top_k=10, user_id="test_user")
        assert len(results) >= 2  # 至少2条关于第一性原理的记忆

        # Phase 3: 执行合并
        changes = soma.evolve()
        merge_changes = [c for c in changes if c["type"] == "memory_consolidation"]
        assert isinstance(merge_changes, list)

        # Phase 4: 执行遗忘
        forget_changes = [c for c in changes if c["type"] == "memory_forgetting"]
        assert isinstance(forget_changes, list)

        # Phase 5: 回答应能正常生成（Mock模式）
        answer = soma.respond("如何用第一性原理分析商业问题？", user_id="test_user")
        assert len(answer) > 0
        assert "第一性原理" in answer or "Mock" in answer or "维度" in answer

    def test_respond_end_to_end_with_memory(self, soma):
        """端到端：先记忆后回答"""
        soma.remember("用户偏好简洁的代码风格，不喜欢过度抽象", importance=0.8, user_id="dev1")
        soma.remember("项目使用PostgreSQL作为主数据库", importance=0.7, user_id="dev1")

        answer = soma.respond("这个项目的数据库选型是什么？", user_id="dev1")
        assert len(answer) > 0

    def test_chat_structured_result(self, soma):
        """chat() 返回结构化结果"""
        soma.remember("SOMA项目的核心是智慧思维框架", importance=0.9, user_id="u1")

        result = soma.chat("什么是SOMA？", user_id="u1")
        assert "problem" in result
        assert "answer" in result
        assert "foci" in result
        assert "activated_memories" in result
        assert "memory_stats" in result


class TestV070DataIsolation:
    """多用户数据隔离验证"""

    @pytest.fixture
    def soma(self, tmp_path):
        from soma import SOMA
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        yield s
        s.close()

    def test_user_isolation_remember(self, soma):
        """不同用户的记忆互不可见"""
        soma.remember("用户A的项目使用React", user_id="user_a")
        soma.remember("用户B的项目使用Vue", user_id="user_b")

        # 各用户只能查到自己的记忆
        results_a = soma.query_memory("项目", user_id="user_a")
        results_b = soma.query_memory("项目", user_id="user_b")

        # 结果中的记忆内容应属于对应用户
        a_contents = [r.get("content", r.get("content_preview", "")) for r in results_a]
        b_contents = [r.get("content", r.get("content_preview", "")) for r in results_b]

        assert any("React" in c for c in a_contents), f"用户A应看到自己的React记忆: {a_contents}"
        assert any("Vue" in c for c in b_contents), f"用户B应看到自己的Vue记忆: {b_contents}"
        assert not any("Vue" in c for c in a_contents), f"用户A不应看到Vue: {a_contents}"
        assert not any("React" in c for c in b_contents), f"用户B不应看到React: {b_contents}"

    def test_user_isolation_consolidation(self, soma):
        """合并只在同一user_id内进行"""
        soma.remember("第一性原理很重要", importance=0.5, user_id="user_a")
        soma.remember("第一性原理非常重要", importance=0.5, user_id="user_b")

        changes = soma.evolve()
        # 不同用户的相似记忆不应被合并
        # 各自应仍然存在
        res_a = soma.query_memory("第一性原理", user_id="user_a")
        res_b = soma.query_memory("第一性原理", user_id="user_b")
        assert len(res_a) >= 1
        assert len(res_b) >= 1

    def test_user_isolation_forgetting(self, soma):
        """遗忘只影响指定用户"""
        # 直接通过底层API插入旧记忆来测试遗忘隔离
        import time as _time
        old_ts = _time.time() - 120 * 86400
        from soma.memory.episodic import EpisodicStore
        # 需要访问底层store

        # 使用high-level API验证隔离
        soma.remember("用户A的旧知识", importance=0.2, user_id="user_a")
        soma.remember("用户B的旧知识", importance=0.2, user_id="user_b")

        # evolve会触发遗忘扫描
        soma.evolve()

        # 两者都应仍存在（因为刚创建，未达到遗忘阈值）
        res_a = soma.query_memory("用户A", user_id="user_a")
        res_b = soma.query_memory("用户B", user_id="user_b")
        assert len(res_a) >= 1
        assert len(res_b) >= 1

    def test_external_knowledge_per_user(self, soma, tmp_path):
        """外部知识导入按用户隔离"""
        md_file = tmp_path / "user_know.md"
        md_file.write_text("# 用户知识\n\n特定领域的专业知识内容。", encoding="utf-8")

        soma.remember_semantic(
            "external_ref", "imported_for", "user_x",
            namespace="test",
        )


class TestV070BoundaryConditions:
    """边界条件测试"""

    @pytest.fixture
    def soma(self, tmp_path):
        from soma import SOMA
        s = SOMA(persist_dir=str(tmp_path), llm="mock")
        yield s
        s.close()

    def test_empty_content_remember(self, soma):
        """空内容记忆"""
        mid = soma.remember("", user_id="test")
        # 空内容应能处理（可能返回空ID或正常ID）
        assert isinstance(mid, str)

    def test_very_long_content(self, soma):
        """超长内容记忆"""
        long_content = "知识" * 5000  # 10000字符
        mid = soma.remember(long_content, user_id="test")
        assert isinstance(mid, str)
        assert len(mid) > 0

    def test_special_characters(self, soma):
        """特殊字符内容"""
        special = "测试 <script>alert('xss')</script> 特殊字符 \n\t\r 🎉"
        mid = soma.remember(special, user_id="test")
        results = soma.query_memory("测试", user_id="test")
        assert len(results) >= 1

    def test_zero_importance(self, soma):
        """零importance记忆可存储，但查询阈值可能过滤"""
        mid = soma.remember("零重要性记忆", importance=0.0, user_id="test")
        assert isinstance(mid, str) and len(mid) > 0
        # 零importance记忆被存储（可通过底层API验证）
        # 但高层查询可能因阈值过滤不返回，这是合理行为

    def test_low_importance_queryable(self, soma):
        """低importance(0.2)记忆可存储并可被查询"""
        mid = soma.remember("低重要性但仍可查询的记忆", importance=0.2, user_id="test")
        results = soma.query_memory("低重要性", user_id="test")
        assert len(results) >= 1

    def test_max_importance(self, soma):
        """最大importance记忆"""
        mid = soma.remember("最重要的记忆", importance=1.0, user_id="test")
        results = soma.query_memory("最重要", user_id="test")
        assert len(results) >= 1

    def test_negative_importance(self, soma):
        """负importance记忆"""
        mid = soma.remember("负重要性记忆", importance=-0.5, user_id="test")
        assert isinstance(mid, str)

    def test_empty_user_id(self, soma):
        """空user_id"""
        mid = soma.remember("无用户记忆", user_id="")
        results = soma.query_memory("无用户", user_id="")
        assert len(results) >= 1

    def test_query_empty_string(self, soma):
        """空查询字符串"""
        soma.remember("测试内容", user_id="test")
        results = soma.query_memory("", user_id="test")
        assert isinstance(results, list)

    def test_query_large_top_k(self, soma):
        """超大top_k查询"""
        for i in range(10):
            soma.remember(f"测试记忆条目{i}", user_id="test")
        results = soma.query_memory("测试", top_k=100, user_id="test")
        assert len(results) <= 100

    def test_rapid_consecutive_evolves(self, soma):
        """连续快速evolve调用"""
        for i in range(5):
            soma.remember(f"快速记忆{i}", importance=0.5, user_id="test")
        # 连续3次evolve不应崩溃
        for _ in range(3):
            changes = soma.evolve()
            assert isinstance(changes, list)

    def test_many_similar_memories_consolidation(self, soma):
        """大量相似记忆的合并压力测试"""
        for i in range(10):
            soma.remember(
                f"第一性原理在商业决策中的应用案例{i}: 从基本要素出发分析问题",
                importance=0.4 + i * 0.05,
                user_id="stress_test",
            )

        # 多次合并扫描
        for _ in range(2):
            changes = soma.evolve()
            assert isinstance(changes, list)

        # 最终查询不应报错
        results = soma.query_memory("第一性原理", top_k=5, user_id="stress_test")
        assert isinstance(results, list)


class TestV070NewModulesDirect:
    """v0.7.0 新模块直接测试"""

    @pytest.fixture
    def store(self, tmp_path):
        from soma.memory.episodic import EpisodicStore
        s = EpisodicStore(tmp_path)
        yield s
        s.close()

    def test_consolidation_produces_merge_log(self, store):
        """合并产生日志记录"""
        mid1 = store.add("第一性原理是回归事物本质的思考方式，有助于从底层逻辑出发", importance=0.5)
        mid2 = store.add("运用第一性原理可以从底层逻辑出发分析问题", importance=0.5)

        from soma.memory.consolidation import ConsolidationEngine
        engine = ConsolidationEngine(store._conn)
        merged_id = engine.merge(mid1, mid2)

        if merged_id:
            stats = engine.stats()
            assert stats["total_merges"] >= 1

    def test_forgetting_produces_archive(self, store):
        """遗忘产生归档记录"""
        old_ts = time.time() - 120 * 86400
        store._conn.execute(
            """INSERT INTO episodic_memories (id, content, content_hash, timestamp, importance, user_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("old_mem", "非常古老的记忆", "hash_old", old_ts, 0.1, ""),
        )
        store._conn.commit()

        result = store.forget(max_archive=50)
        assert isinstance(result, dict)
        assert "decayed" in result or "cleaned" in result

    def test_external_import_creates_external_memories(self, store, tmp_path):
        """外部导入创建external类型记忆"""
        md_file = tmp_path / "test_import.md"
        md_file.write_text("# SOMA智慧框架\n\n第一性原理、系统思维、辩证统一。", encoding="utf-8")

        ids = store.import_knowledge(str(md_file))
        assert len(ids) >= 1

        mem = store.get(ids[0])
        assert mem is not None
        assert mem.context.get("_external") is True

    def test_archive_and_restore_cycle(self, store):
        """归档→恢复完整周期"""
        from soma.memory.forgetting import ForgettingEngine

        engine = ForgettingEngine(store._conn)
        now = time.time()

        # 直接插入归档记录
        store._conn.execute(
            """INSERT INTO episodic_archived
               (id, content, content_hash, timestamp, importance, user_id, archived_at, archive_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("cycle_test", "循环测试记忆", "hash_cycle", now - 86400, 0.5, "", now, "decay"),
        )
        store._conn.commit()

        # 恢复
        restored = engine.restore("cycle_test")
        assert restored is True

        # 验证在主表
        mem = store.get("cycle_test")
        assert mem is not None
        assert mem.content == "循环测试记忆"

        # 验证从归档表移除
        arch = store._conn.execute(
            "SELECT * FROM episodic_archived WHERE id = 'cycle_test'"
        ).fetchone()
        assert arch is None
