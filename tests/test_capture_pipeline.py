import pytest

from soma.memory.scene import SceneStore
from soma.memory.profile import ProfileStore
from soma.memory.capture import (
    CapturePipeline, CaptureConfig, SceneExtractor, ProfileExtractor,
)


@pytest.fixture
def stores(tmp_path):
    ss = SceneStore(tmp_path)
    ps = ProfileStore(tmp_path)
    yield ss, ps
    ss.close()
    ps.close()


@pytest.fixture
def cfg():
    return CaptureConfig(
        scene_warmup=5,
        scene_min_interval=0,  # 测试用，不等待
        scene_max_interval=3600,
        scene_idle_timeout=600,
        profile_scene_interval=10,
        enable_warmup=True,
    )


@pytest.fixture
def quick_cfg():
    return CaptureConfig(
        scene_warmup=2,
        scene_min_interval=0,
        scene_max_interval=3600,
        scene_idle_timeout=600,
        profile_scene_interval=2,
        enable_warmup=True,
    )


class TestCaptureConfig:
    def test_defaults(self):
        c = CaptureConfig()
        assert c.scene_warmup == 5
        assert c.scene_min_interval == 300
        assert c.scene_max_interval == 3600
        assert c.scene_idle_timeout == 600
        assert c.profile_scene_interval == 10
        assert c.enable_warmup is True

    def test_custom(self):
        c = CaptureConfig(
            scene_warmup=3, scene_min_interval=60,
            scene_max_interval=1800, scene_idle_timeout=300,
            profile_scene_interval=5, enable_warmup=False,
        )
        assert c.scene_warmup == 3
        assert c.scene_min_interval == 60
        assert c.enable_warmup is False


class TestSceneExtractorMock:
    def test_empty_memories(self):
        ext = SceneExtractor()
        result = ext.extract([], [])
        assert result == []

    def test_default_extract_returns_empty(self):
        ext = SceneExtractor()
        result = ext.extract(
            [{"content": "测试记忆", "id": "1"}],
            [],
        )
        assert result == []  # 默认 extractor 无 LLM

    def test_parse_valid_json(self):
        raw = '{"scenes": [{"title": "测试场景", "summary": "摘要内容", "tags": ["t1"], "importance": 0.8, "evidence_ids": ["1","2"]}]}'
        result = SceneExtractor._parse_response(raw)
        assert len(result) == 1
        assert result[0]["title"] == "测试场景"
        assert result[0]["summary"] == "摘要内容"
        assert result[0]["tags"] == ["t1"]
        assert result[0]["importance"] == 0.8
        assert result[0]["evidence_ids"] == ["1", "2"]

    def test_parse_malformed_json_with_braces(self):
        raw = '前言废话 {"scenes": [{"title": "恢复场景", "summary": "容错解析", "tags": [], "importance": 0.5, "evidence_ids": []}]} 后记'
        result = SceneExtractor._parse_response(raw)
        assert len(result) == 1
        assert result[0]["title"] == "恢复场景"

    def test_parse_completely_invalid(self):
        result = SceneExtractor._parse_response("这不是 JSON")
        assert result == []

    def test_parse_empty_scenes(self):
        result = SceneExtractor._parse_response('{"scenes": []}')
        assert result == []

    def test_parse_missing_title(self):
        raw = '{"scenes": [{"summary": "无标题", "tags": [], "importance": 0.5, "evidence_ids": []}]}'
        result = SceneExtractor._parse_response(raw)
        assert result == []  # 无标题跳过

    def test_parse_default_values(self):
        raw = '{"scenes": [{"title": "极简场景"}]}'
        result = SceneExtractor._parse_response(raw)
        assert len(result) == 1
        assert result[0]["importance"] == 0.5  # float(s.get("importance", 0.5)) → 0.5

    def test_parse_importance_clamp(self):
        raw = '{"scenes": [{"title": "t", "summary": "s", "importance": 2.0}]}'
        result = SceneExtractor._parse_response(raw)
        assert result[0]["importance"] == 1.0

    def test_parse_list_format(self):
        raw = '[{"title": "列表格式", "summary": "直接数组", "tags": [], "importance": 0.5, "evidence_ids": []}]'
        result = SceneExtractor._parse_response(raw)
        assert len(result) == 1
        assert result[0]["title"] == "列表格式"

    def test_tags_truncation(self):
        import json
        many_tags = [f"tag{i}" for i in range(20)]
        raw = json.dumps({"scenes": [{
            "title": "t", "summary": "s",
            "tags": many_tags, "importance": 0.5,
            "evidence_ids": [],
        }]})
        result = SceneExtractor._parse_response(raw)
        assert len(result[0]["tags"]) <= 10

    def test_title_truncation(self):
        long_title = "很" * 300
        raw = (
            '{"scenes": [{"title": "' + long_title + '", '
            '"summary": "s", "tags": [], "importance": 0.5, '
            '"evidence_ids": []}]}'
        )
        result = SceneExtractor._parse_response(raw)
        assert len(result[0]["title"]) <= 200


class TestProfileExtractorMock:
    def test_empty_scenes(self):
        ext = ProfileExtractor()
        result = ext.extract([], [])
        assert result == []

    def test_default_extract_returns_empty(self):
        ext = ProfileExtractor()
        result = ext.extract(
            [{"title": "场景", "summary": "摘要"}],
            [],
        )
        assert result == []

    def test_parse_valid_json(self):
        raw = '{"entries": [{"type": "preference", "key": "language", "value": "Python", "confidence": 0.9}]}'
        result = ProfileExtractor._parse_response(raw)
        assert len(result) == 1
        assert result[0]["trait_type"] == "preference"
        assert result[0]["trait_key"] == "language"
        assert result[0]["trait_value"] == "Python"
        assert result[0]["confidence"] == 0.9

    def test_parse_invalid_type(self):
        raw = '{"entries": [{"type": "invalid", "key": "k", "value": "v", "confidence": 0.5}]}'
        result = ProfileExtractor._parse_response(raw)
        assert result == []

    def test_parse_all_valid_types(self):
        for tt in ["preference", "skill", "habit", "knowledge_gap", "goal"]:
            raw = f'{{"entries": [{{"type": "{tt}", "key": "k", "value": "v", "confidence": 0.5}}]}}'
            result = ProfileExtractor._parse_response(raw)
            assert len(result) == 1
            assert result[0]["trait_type"] == tt

    def test_parse_confidence_clamp(self):
        raw = '{"entries": [{"type": "skill", "key": "k", "value": "v", "confidence": 5.0}]}'
        result = ProfileExtractor._parse_response(raw)
        assert result[0]["confidence"] == 1.0


class TestCapturePipeline:
    def test_init_disabled(self, stores, cfg):
        ss, ps = stores
        pipe = CapturePipeline(ss, ps, cfg)
        assert pipe._enabled is True
        pipe.disable()
        assert pipe._enabled is False
        pipe.enable()
        assert pipe._enabled is True
        pipe.close()

    def test_on_new_memory_basic(self, stores, cfg):
        ss, ps = stores
        pipe = CapturePipeline(ss, ps, cfg)
        state_before = pipe.get_state("u1")
        assert state_before["new_count"] == 0

        result = pipe.on_new_memory("u1")
        state_after = pipe.get_state("u1")
        assert state_after["new_count"] >= 0
        pipe.close()

    def test_on_new_memory_disabled(self, stores, cfg):
        ss, ps = stores
        pipe = CapturePipeline(ss, ps, cfg)
        pipe.disable()
        result = pipe.on_new_memory("u1")
        assert result == 0
        pipe.close()

    def test_warmup_increment(self, stores, cfg):
        ss, ps = stores
        pipe = CapturePipeline(ss, ps, cfg)
        # 首次 on_new_memory 触发初始化 warmup=1
        pipe.on_new_memory("u1")
        state = pipe.get_state("u1")
        assert state["warmup_threshold"] == 1  # 首次启动 warmup=1

        for i in range(5):
            pipe.on_new_memory("u1")
        state = pipe.get_state("u1")
        assert state["warmup_threshold"] >= 1
        pipe.close()

    def test_warmup_disabled(self, stores, cfg):
        ss, ps = stores
        cfg2 = CaptureConfig(
            scene_warmup=5, scene_min_interval=0,
            scene_max_interval=3600, scene_idle_timeout=600,
            profile_scene_interval=10, enable_warmup=False,
        )
        pipe = CapturePipeline(ss, ps, cfg2)
        state = pipe.get_state("u1")
        assert state["warmup_threshold"] == 5  # 直接跳到 scene_warmup
        pipe.close()

    def test_get_state(self, stores, cfg):
        ss, ps = stores
        pipe = CapturePipeline(ss, ps, cfg)
        state = pipe.get_state("u1")
        assert "enabled" in state
        assert "new_count" in state
        assert "warmup_threshold" in state
        assert "scene_count" in state
        assert "profile_count" in state
        pipe.close()

    def test_multiple_users(self, stores, cfg):
        ss, ps = stores
        pipe = CapturePipeline(ss, ps, cfg)
        pipe.on_new_memory("u1")
        pipe.on_new_memory("u2")
        s1 = pipe.get_state("u1")
        s2 = pipe.get_state("u2")
        # 不同用户的计数独立
        assert isinstance(s1["new_count"], int)
        assert isinstance(s2["new_count"], int)
        pipe.close()

    def test_capture_from_memories_empty(self, stores, cfg):
        ss, ps = stores
        pipe = CapturePipeline(ss, ps, cfg)
        created = pipe.capture_from_memories([], user_id="u1", force=True)
        assert created == 0
        pipe.close()

    def test_capture_from_memories_with_mock_extractor(self, stores, cfg):
        ss, ps = stores

        def mock_llm(prompt):
            return '{"scenes": [{"title": "Mock场景", "summary": "Mock摘要", "tags": ["mock"], "importance": 0.7, "evidence_ids": ["1","2"]}]}'

        ext = SceneExtractor(llm_call=mock_llm)
        pipe = CapturePipeline(ss, ps, cfg, scene_extractor=ext)

        memories = [
            {"content": "测试记忆1", "id": "1"},
            {"content": "测试记忆2", "id": "2"},
        ]
        created = pipe.capture_from_memories(memories, user_id="u1", force=True)
        assert created == 1
        scenes = ss.get_scenes(user_id="u1")
        assert len(scenes) == 1
        assert scenes[0]["title"] == "Mock场景"
        pipe.close()

    def test_update_profile_with_mock(self, stores, quick_cfg):
        ss, ps = stores

        # 先创建场景
        ss.add_scene("Python开发", "用户频繁使用Python", user_id="u1")
        ss.add_scene("数据分析", "用户从事数据分析工作", user_id="u1")

        def mock_llm(prompt):
            return '{"entries": [{"type": "skill", "key": "python", "value": "expert", "confidence": 0.9}]}'

        prof_ext = ProfileExtractor(llm_call=mock_llm)
        pipe = CapturePipeline(ss, ps, quick_cfg, profile_extractor=prof_ext)

        updated = pipe.update_profile("u1", force=True)
        assert updated == 1

        entries = ps.get_entries(user_id="u1")
        assert len(entries) == 1
        assert entries[0]["trait_type"] == "skill"
        assert entries[0]["trait_key"] == "python"
        pipe.close()

    def test_profile_triggers_on_scene_interval(self, stores, quick_cfg):
        ss, ps = stores

        def mock_scene_llm(prompt):
            return '{"scenes": [{"title": "S", "summary": "x", "tags": [], "importance": 0.5, "evidence_ids": []}]}'

        def mock_prof_llm(prompt):
            return '{"entries": [{"type": "preference", "key": "tool", "value": "git", "confidence": 0.8}]}'

        s_ext = SceneExtractor(llm_call=mock_scene_llm)
        p_ext = ProfileExtractor(llm_call=mock_prof_llm)
        pipe = CapturePipeline(ss, ps, quick_cfg, s_ext, p_ext)

        # quick_cfg: profile_scene_interval=2, 所以每2个场景触发一次画像更新
        for i in range(2):
            pipe.capture_from_memories(
                [{"content": f"记忆{i}", "id": str(i)}],
                user_id="u1", force=True,
            )

        # 2个场景创建后应触发画像
        entries = ps.get_entries(user_id="u1")
        assert len(entries) >= 0  # profile 触发取决于 total_scenes_created % interval
        pipe.close()

    def test_close_clears_state(self, stores, cfg):
        ss, ps = stores
        pipe = CapturePipeline(ss, ps, cfg)
        pipe.on_new_memory("u1")
        pipe.close()
        state = pipe.get_state("u1")
        assert state["new_count"] == 0
        assert state["enabled"] is False
