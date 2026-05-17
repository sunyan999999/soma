"""向后兼容性专项测试 — 确保 v1.0.0 新功能不影响现有行为"""
import os
import pytest


class TestBackwardCompatibleInit:
    def test_default_init_no_new_params(self):
        from soma import SOMA
        soma = SOMA()
        assert soma.stats is not None
        assert "episodic" in soma.stats
        soma.close()

    def test_init_with_all_original_params(self):
        from soma import SOMA
        soma = SOMA(
            llm="mock",
            top_k=5,
            recall_threshold=0.01,
            use_vector_search=False,
        )
        stats = soma.stats
        assert "episodic" in stats
        soma.close()

    def test_new_params_are_optional(self):
        from soma import SOMA
        soma = SOMA()  # 不带任何新参数
        assert soma._scene_store is None
        assert soma._profile_store is None
        assert soma._capture_pipeline is None
        soma.close()

    def test_layered_components_not_created_by_default(self):
        from soma import SOMA
        soma = SOMA()
        # 默认不创建分层组件
        assert soma._scene_store is None
        # stats 不含新字段（默认模式）
        stats = soma.stats
        assert "scenes" not in stats or stats.get("scenes") is None
        soma.close()


class TestBackwardCompatibleRemember:
    def test_remember_original_signature(self):
        from soma import SOMA
        soma = SOMA()
        mid = soma.remember("测试记忆内容")
        assert mid
        soma.close()

    def test_remember_with_context_and_importance(self):
        from soma import SOMA
        soma = SOMA()
        mid = soma.remember(
            "设计决策: 使用Redis缓存",
            context={"domain": "架构"},
            importance=0.9,
        )
        assert mid
        soma.close()

    def test_remember_with_user_and_session(self):
        from soma import SOMA
        soma = SOMA()
        mid = soma.remember(
            "约束: API不能改动",
            user_id="dev1",
            session_id="session_001",
        )
        assert mid
        soma.close()

    def test_remember_auto_capture_default_none(self):
        from soma import SOMA
        soma = SOMA()
        # auto_capture 默认为 None，不触发分层逻辑
        mid = soma.remember("普通记忆")
        assert mid
        soma.close()


class TestBackwardCompatibleMethods:
    def test_all_original_public_methods_exist(self):
        from soma import SOMA
        soma = SOMA()
        original_methods = [
            "respond", "chat", "remember", "remember_semantic",
            "query_memory", "decompose", "reflect", "evolve",
            "get_weights", "adjust_weight", "discover_laws",
            "approve_law", "get_thought_templates",
            "close", "stats",
        ]
        for method in original_methods:
            assert hasattr(soma, method), f"缺少方法: {method}"
        soma.close()

    def test_respond_works(self):
        from soma import SOMA
        soma = SOMA()
        answer = soma.respond("什么是设计模式？", user_id="test_user")
        assert isinstance(answer, str)
        assert len(answer) > 0
        soma.close()

    def test_query_memory_works(self):
        from soma import SOMA
        soma = SOMA()
        soma.remember("Python是一种编程语言", importance=0.8)
        results = soma.query_memory("Python", top_k=3)
        assert isinstance(results, list)
        assert len(results) >= 1
        soma.close()

    def test_stats_keys(self):
        from soma import SOMA
        soma = SOMA()
        stats = soma.stats
        assert "episodic" in stats
        assert "semantic" in stats
        assert "skill" in stats
        assert "indexed_vectors" in stats
        soma.close()

    def test_decompose_works(self):
        from soma import SOMA
        soma = SOMA()
        foci = soma.decompose("如何提升系统性能？")
        assert isinstance(foci, list)
        assert len(foci) > 0
        soma.close()


class TestBackwardCompatibleLayeredMemory:
    def test_enable_disable_cycle(self):
        from soma import SOMA
        soma = SOMA()
        soma.enable_layered_memory(scene_warmup=3, profile_interval=5)
        # 验证分层组件已创建
        assert soma._scene_store is not None
        assert soma._profile_store is not None
        assert soma._capture_pipeline is not None

        soma.disable_layered_memory()
        # 禁用不影响基础功能
        mid = soma.remember("测试禁用后的记忆")
        assert mid

        soma.close()

    def test_layered_stats_when_enabled(self):
        from soma import SOMA
        soma = SOMA()
        soma.enable_layered_memory()
        stats = soma.get_layered_stats()
        assert "scenes" in stats
        assert "profile_entries" in stats
        soma.close()

    def test_get_scenes_empty(self):
        from soma import SOMA
        soma = SOMA()
        soma.enable_layered_memory()
        scenes = soma.get_scenes()
        assert isinstance(scenes, list)
        assert len(scenes) == 0
        soma.close()

    def test_get_profile_empty(self):
        from soma import SOMA
        soma = SOMA()
        soma.enable_layered_memory()
        entries = soma.get_profile()
        assert isinstance(entries, list)
        assert len(entries) == 0
        soma.close()


class TestBackwardCompatibleClose:
    def test_close_without_layered_memory(self):
        from soma import SOMA
        soma = SOMA()
        soma.remember("测试")
        soma.close()  # 不抛异常

    def test_close_with_layered_memory(self):
        from soma import SOMA
        soma = SOMA()
        soma.enable_layered_memory()
        soma.remember("测试")
        soma.close()  # 不抛异常

    def test_context_manager(self):
        from soma import SOMA
        with SOMA() as soma:
            soma.remember("with语句测试")
        # 离开上下文后 close 被调用

    def test_context_manager_with_layered(self):
        from soma import SOMA
        with SOMA(scene_extraction_enabled=True, profile_extraction_enabled=True) as soma:
            soma.remember("分层记忆with语句测试")
        # 离开上下文后 close 被调用
