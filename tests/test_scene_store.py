import pytest

from soma.memory.scene import SceneStore


@pytest.fixture
def store(tmp_path):
    s = SceneStore(tmp_path)
    yield s
    s.close()


class TestSceneStore:
    def test_add_and_list(self, store):
        sid = store.add_scene("数据分析", "用户频繁使用Python进行数据分析")
        assert sid
        scenes = store.get_scenes()
        assert len(scenes) >= 1
        titles = [s["title"] for s in scenes]
        assert "数据分析" in titles

    def test_get_by_id(self, store):
        sid = store.add_scene("测试场景", "摘要内容", tags=["tag1", "tag2"])
        scene = store.get_scene(sid)
        assert scene is not None
        assert scene["title"] == "测试场景"
        assert scene["summary"] == "摘要内容"
        assert "tag1" in scene["tags"]
        assert "tag2" in scene["tags"]

    def test_get_nonexistent(self, store):
        assert store.get_scene("nonexistent") is None

    def test_count(self, store):
        assert store.count() == 0
        store.add_scene("场景1", "摘要1")
        store.add_scene("场景2", "摘要2")
        assert store.count() == 2

    def test_delete(self, store):
        sid = store.add_scene("待删除", "摘要")
        assert store.count() == 1
        assert store.delete_scene(sid) is True
        assert store.count() == 0
        assert store.get_scene(sid) is None
        assert store.delete_scene("nonexistent") is False

    def test_dedup_same_user_same_title(self, store):
        sid1 = store.add_scene("重复标题", "第一次摘要", user_id="u1")
        sid2 = store.add_scene("重复标题", "第二次摘要", user_id="u1")
        assert sid1 == sid2  # 同用户同标题去重
        assert store.count("u1") == 1
        scene = store.get_scene(sid1)
        assert "第一次摘要" in scene["summary"]  # 先入为主，不更新

    def test_no_dedup_different_user(self, store):
        sid1 = store.add_scene("相同标题", "用户1的摘要", user_id="u1")
        sid2 = store.add_scene("相同标题", "用户2的摘要", user_id="u2")
        assert sid1 != sid2
        assert store.count("u1") == 1
        assert store.count("u2") == 1
        assert store.count() == 2

    def test_user_isolation(self, store):
        store.add_scene("U1场景", "摘要", user_id="u1")
        store.add_scene("U2场景", "摘要", user_id="u2")
        u1_scenes = store.get_scenes(user_id="u1")
        titles = [s["title"] for s in u1_scenes]
        assert "U1场景" in titles
        assert "U2场景" not in titles

    def test_get_scenes_with_top_k(self, store):
        for i in range(10):
            store.add_scene(f"场景{i}", f"摘要{i}")
        scenes = store.get_scenes(top_k=5)
        assert len(scenes) == 5

    def test_get_scenes_min_importance(self, store):
        store.add_scene("重要场景", "摘要", importance=0.9)
        store.add_scene("普通场景", "摘要", importance=0.3)
        scenes = store.get_scenes(min_importance=0.7)
        assert len(scenes) == 1
        assert scenes[0]["title"] == "重要场景"

    def test_tags_stored_as_list(self, store):
        sid = store.add_scene("标签测试", "摘要", tags=["python", "data", "ml"])
        scene = store.get_scene(sid)
        assert isinstance(scene["tags"], list)
        assert set(scene["tags"]) == {"python", "data", "ml"}

    def test_evidence_ids(self, store):
        sid = store.add_scene(
            "证据测试", "摘要",
            evidence_ids=["mem1", "mem2", "mem3"],
        )
        scene = store.get_scene(sid)
        assert len(scene["evidence_ids"]) == 3
        assert "mem1" in scene["evidence_ids"]

    def test_importance_range(self, store):
        sid = store.add_scene("重要性范围", "摘要", importance=0.75)
        scene = store.get_scene(sid)
        assert 0.0 <= scene["importance"] <= 1.0

    def test_generate_markdown(self, store):
        sid = store.add_scene(
            "Markdown测试", "这是一个测试场景的摘要内容",
            tags=["测试", "markdown"],
            evidence_ids=["e1"],
            importance=0.8,
            user_id="test_user",
        )
        md = store.generate_markdown(sid)
        assert "Markdown测试" in md
        assert "测试场景的摘要内容" in md
        assert "test_user" in md

    def test_generate_markdown_nonexistent(self, store):
        assert store.generate_markdown("nonexistent") == ""

    def test_empty_tags(self, store):
        sid = store.add_scene("无标签", "摘要")
        scene = store.get_scene(sid)
        assert scene["tags"] == []

    def test_content_stored_as_given(self, store):
        # 存储不做截断，截断由 extractor 的 _parse_response 负责
        long_title = "长标题" * 20
        long_summary = "长摘要" * 100
        sid = store.add_scene(long_title, long_summary)
        scene = store.get_scene(sid)
        assert scene["title"] == long_title
        assert scene["summary"] == long_summary

    def test_default_user_id(self, store):
        sid = store.add_scene("默认用户", "摘要")
        scene = store.get_scene(sid)
        assert scene["user_id"] == ""

    def test_multiple_operations(self, store):
        # 综合操作序列
        sid1 = store.add_scene("场景A", "摘要A", tags=["tag1"])
        sid2 = store.add_scene("场景B", "摘要B", tags=["tag2"])
        assert store.count() == 2
        store.delete_scene(sid1)
        assert store.count() == 1
        assert store.get_scene(sid1) is None
        assert store.get_scene(sid2) is not None
