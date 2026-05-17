import pytest

from soma.memory.profile import ProfileStore


@pytest.fixture
def store(tmp_path):
    s = ProfileStore(tmp_path)
    yield s
    s.close()


class TestProfileStore:
    def test_upsert_and_get(self, store):
        pid = store.upsert_entry("preference", "language", "Python", confidence=0.8)
        assert pid
        entries = store.get_entries()
        assert len(entries) >= 1
        assert entries[0]["trait_type"] == "preference"
        assert entries[0]["trait_key"] == "language"
        assert entries[0]["trait_value"] == "Python"
        assert entries[0]["confidence"] == 0.8

    def test_get_by_id(self, store):
        pid = store.upsert_entry("skill", "coding", "advanced", confidence=0.9)
        entry = store.get_entry(pid)
        assert entry is not None
        assert entry["trait_type"] == "skill"
        assert entry["trait_key"] == "coding"

    def test_get_nonexistent(self, store):
        assert store.get_entry("nonexistent") is None

    def test_count(self, store):
        assert store.count() == 0
        store.upsert_entry("preference", "editor", "vscode")
        store.upsert_entry("skill", "python", "expert")
        assert store.count() == 2

    def test_delete(self, store):
        pid = store.upsert_entry("habit", "morning_routine", "check_email")
        assert store.count() == 1
        assert store.delete_entry(pid) is True
        assert store.count() == 0
        assert store.get_entry(pid) is None
        assert store.delete_entry("nonexistent") is False

    def test_upsert_merge_same_key(self, store):
        pid1 = store.upsert_entry("preference", "language", "Python", confidence=0.7)
        pid2 = store.upsert_entry("preference", "language", "Rust", confidence=0.8)
        assert pid1 == pid2  # 同key合并
        assert store.count() == 1
        entry = store.get_entry(pid1)
        assert entry["confidence"] == pytest.approx(0.85, 0.001)  # max(0.7, 0.8) + 0.05

    def test_no_merge_different_type(self, store):
        pid1 = store.upsert_entry("preference", "tool", "git")
        pid2 = store.upsert_entry("skill", "tool", "git")
        assert pid1 != pid2
        assert store.count() == 2

    def test_no_merge_different_user(self, store):
        pid1 = store.upsert_entry("preference", "food", "pizza", user_id="u1")
        pid2 = store.upsert_entry("preference", "food", "sushi", user_id="u2")
        assert pid1 != pid2
        assert store.count("u1") == 1
        assert store.count("u2") == 1

    def test_user_isolation(self, store):
        store.upsert_entry("preference", "color", "blue", user_id="u1")
        store.upsert_entry("preference", "color", "red", user_id="u2")
        u1_entries = store.get_entries(user_id="u1")
        assert len(u1_entries) == 1
        assert u1_entries[0]["trait_value"] == "blue"

    def test_confidence_capped_at_1(self, store):
        pid = store.upsert_entry("preference", "x", "a", confidence=0.99)
        store.upsert_entry("preference", "x", "b", confidence=0.99)
        entry = store.get_entry(pid)
        assert entry["confidence"] <= 1.0

    def test_invalid_trait_type(self, store):
        with pytest.raises(ValueError):
            store.upsert_entry("invalid_type", "key", "value")

    def test_all_valid_trait_types(self, store):
        for tt in ["preference", "skill", "habit", "knowledge_gap", "goal"]:
            pid = store.upsert_entry(tt, f"{tt}_key", f"{tt}_value")
            entry = store.get_entry(pid)
            assert entry["trait_type"] == tt

    def test_get_entries_by_type(self, store):
        store.upsert_entry("preference", "p1", "v1")
        store.upsert_entry("skill", "s1", "v1")
        store.upsert_entry("skill", "s2", "v2")
        skills = store.get_entries(trait_type="skill")
        assert len(skills) == 2
        prefs = store.get_entries(trait_type="preference")
        assert len(prefs) == 1

    def test_get_entries_min_confidence(self, store):
        store.upsert_entry("preference", "high", "v", confidence=0.9)
        store.upsert_entry("preference", "low", "v", confidence=0.2)
        store.upsert_entry("skill", "mid", "v", confidence=0.5)
        results = store.get_entries(min_confidence=0.5)
        assert len(results) == 2

    def test_sorted_by_confidence(self, store):
        store.upsert_entry("preference", "low", "v", confidence=0.3)
        store.upsert_entry("preference", "high", "v", confidence=0.9)
        store.upsert_entry("skill", "mid", "v", confidence=0.6)
        entries = store.get_entries()
        confidences = [e["confidence"] for e in entries]
        assert confidences == sorted(confidences, reverse=True)

    def test_evidence_ids_merge(self, store):
        pid = store.upsert_entry("preference", "lang", "Python", evidence_ids=["e1"])
        store.upsert_entry("preference", "lang", "TypeScript", evidence_ids=["e2", "e3"])
        entry = store.get_entry(pid)
        assert len(entry["evidence_ids"]) == 3
        assert "e1" in entry["evidence_ids"]
        assert "e2" in entry["evidence_ids"]

    def test_source_scene_ids_merge(self, store):
        pid = store.upsert_entry("skill", "coding", "good", source_scene_ids=["s1"])
        store.upsert_entry("skill", "coding", "great", source_scene_ids=["s2"])
        entry = store.get_entry(pid)
        assert len(entry["source_scene_ids"]) == 2

    def test_generate_markdown(self, store):
        store.upsert_entry("preference", "language", "Python", 0.9, user_id="u1")
        store.upsert_entry("skill", "data_science", "advanced", 0.85, user_id="u1")
        md = store.generate_markdown("u1")
        assert "Python" in md
        assert "data_science" in md
        assert "advanced" in md
        assert "u1" in md

    def test_generate_markdown_empty(self, store):
        md = store.generate_markdown("nonexistent")
        assert "无画像条目" in md

    def test_base_store_interface(self, store):
        # 兼容 BaseMemoryStore 接口
        mid = store.store(
            "Python",
            context={"trait_type": "skill", "trait_key": "programming"},
            importance=0.7,
        )
        assert mid
        results = store.query("Python", top_k=5)
        assert len(results) >= 1

    def test_query_by_text(self, store):
        store.upsert_entry("preference", "editor", "VS Code")
        store.upsert_entry("skill", "language", "Python")
        results = store.query("Python")
        assert len(results) == 1
        assert results[0]["trait_key"] == "language"
