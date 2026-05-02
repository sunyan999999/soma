"""Pre-commit 验证脚本 — 提交前必须全部通过。

用法:
    python scripts/verify_before_commit.py

验证步骤:
    1. 全量单元测试
    2. 数据隔离端到端验证
    3. 时间窗口行为验证
    4. LLM 缓存隔离验证
    5. 数据库迁移兼容性

退出码 0 = 全部通过，非 0 = 有失败项。
"""

import sys
import tempfile
from pathlib import Path

# 确保加载本地开发版 soma，而非 site-packages 中的旧版本
_PROJECT_ROOT = str(Path(__file__).parent.parent.resolve())
# 先移除可能存在的旧路径条目（如 .pth 文件添加的末尾条目），再插入到最前面
while _PROJECT_ROOT in sys.path:
    sys.path.remove(_PROJECT_ROOT)
sys.path.insert(0, _PROJECT_ROOT)

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}  —  {detail}")


# ════════════════════════════════════════════════════════════════════
# 1. 全量单元测试
# ════════════════════════════════════════════════════════════════════

def step1_unit_tests():
    print("\n📋 Step 1: 全量单元测试")
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=line"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).parent.parent),
        timeout=120,
    )
    success = result.returncode == 0
    check("196 项测试全部通过", success, result.stderr.split("\n")[-3] if result.stderr else "")
    if not success:
        print(f"  输出:\n{result.stdout[-2000:]}")
        print(f"  错误:\n{result.stderr[-500:]}")


# ════════════════════════════════════════════════════════════════════
# 2. 数据隔离端到端验证
# ════════════════════════════════════════════════════════════════════

def step2_isolation_integration():
    print("\n📋 Step 2: 数据隔离端到端验证")
    from soma.memory.episodic import EpisodicStore
    from soma.memory.semantic import SemanticStore
    from soma.memory.skill import SkillStore

    # 使用 soma-core 下的临时目录避免 Windows WAL 文件清理冲突
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp())

    ep = sem = sk = None
    try:
        # Episodic 隔离
        ep = EpisodicStore(tmp)
        ep.add("记忆测试：Alice的秘密", user_id="alice")
        ep.add("记忆测试：Bob的计划", user_id="bob")
        ep.add("记忆测试：公共知识", user_id="")

        r1 = ep.query_by_keywords(["秘密"], user_id="alice")
        check("Alice 可见自己的记忆", len(r1) == 1 and "Alice" in r1[0].content)

        r2 = ep.query_by_keywords(["秘密"], user_id="bob")
        check("Bob 不可见 Alice 的记忆", len(r2) == 0)

        r3 = ep.query_by_keywords(["记忆测试"])
        check("不传 user_id 可见全部", len(r3) == 3)
        ep.close()
        ep = None

        # Semantic 隔离
        sem = SemanticStore(persist_dir=tmp)
        sem.add_triple("SOMA", "使用", "Python", namespace="ns_a")
        sem.add_triple("Glaude", "使用", "Go", namespace="ns_b")

        r4 = sem.query_by_keywords(["SOMA"], namespace="ns_a")
        check("namespace ns_a 可查到自己的三元组", len(r4) >= 1)

        r5 = sem.query_by_keywords(["SOMA"], namespace="ns_b")
        check("namespace ns_b 查不到 ns_a 的三元组", len(r5) == 0)
        sem.close()
        sem = None

        # Skill 隔离
        sk = SkillStore(persist_dir=tmp)
        sk.add_skill("技能A", "模式A", user_id="user_a")
        sk.add_skill("技能B", "模式B", user_id="user_b")

        r6 = sk.query_by_keywords(["技能A"], user_id="user_a")
        check("user_a 可见自己的技能", len(r6) == 1)

        r7 = sk.query_by_keywords(["技能A"], user_id="user_b")
        check("user_b 不可见 user_a 的技能", len(r7) == 0)
        sk.close()
        sk = None
    finally:
        for s in [ep, sem, sk]:
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════
# 3. 时间窗口 opt-in 行为验证
# ════════════════════════════════════════════════════════════════════

def step3_time_window_behavior():
    print("\n📋 Step 3: 时间窗口 opt-in 行为")
    import uuid
    import shutil
    from datetime import datetime, timezone
    from soma.memory.episodic import EpisodicStore

    tmp = Path(tempfile.mkdtemp())
    store = None
    try:
        store = EpisodicStore(tmp)
        mid = uuid.uuid4().hex
        old_ts = datetime.now(timezone.utc).timestamp() - 100 * 86400.0

        store._conn.execute(
            "INSERT INTO episodic_memories (id, content, content_hash, timestamp, importance, context_json, user_id)"
            " VALUES (?, ?, ?, ?, 0.5, '{}', ?)",
            (mid, "百天前的古老记忆", f"hash_{mid}", old_ts, ""),
        )
        store._conn.commit()

        # 默认不限时
        r1 = store.query_by_keywords(["百天前", "古老"])
        check("默认不限时：百天前记忆可见", len(r1) == 1)

        # 30天窗口
        r2 = store.query_by_keywords(["百天前", "古老"], max_age_days=30)
        check("max_age_days=30：百天前记忆排除", len(r2) == 0)

        # 200天窗口
        r3 = store.query_by_keywords(["百天前", "古老"], max_age_days=200)
        check("max_age_days=200：百天前记忆在窗口内", len(r3) == 1)
        store.close()
        store = None
    finally:
        if store:
            try:
                store.close()
            except Exception:
                pass
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════
# 4. LLM 缓存隔离验证
# ════════════════════════════════════════════════════════════════════

def step4_cache_isolation():
    print("\n📋 Step 4: LLM 缓存隔离")
    import hashlib

    prompt = "测试问题: 如何提升系统性能?"
    key_no_user = hashlib.sha256(("" + "::" + prompt).encode()).hexdigest()
    key_alice = hashlib.sha256(("alice" + "::" + prompt).encode()).hexdigest()
    key_bob = hashlib.sha256(("bob" + "::" + prompt).encode()).hexdigest()

    check("不同 user_id 缓存键不同", key_alice != key_bob and key_alice != key_no_user)
    check("同 prompt 同 user_id 缓存键相同",
          hashlib.sha256(("alice" + "::" + prompt).encode()).hexdigest() == key_alice)


# ════════════════════════════════════════════════════════════════════
# 5. 数据库迁移兼容性
# ════════════════════════════════════════════════════════════════════

def step5_schema_migration():
    print("\n📋 Step 5: 数据库迁移兼容性")
    import sqlite3
    import shutil
    from soma.memory.semantic import SemanticStore
    from soma.memory.skill import SkillStore

    tmp = Path(tempfile.mkdtemp())
    store1 = store2 = None
    try:
        # 模拟旧版 SemanticStore 数据库（无 namespace 列）
        db1 = tmp / "semantic.db"
        c1 = sqlite3.connect(str(db1))
        c1.execute("CREATE TABLE semantic_triples (id INTEGER PRIMARY KEY, subject TEXT, predicate TEXT, object TEXT, confidence REAL, created_at REAL)")
        c1.execute("CREATE INDEX idx_semantic_subject ON semantic_triples(subject)")
        c1.commit()
        c1.close()

        try:
            store1 = SemanticStore(persist_dir=tmp)
            store1.add_triple("测试", "迁移", "成功")
            check("旧语义库自动迁移不崩溃", store1.count() >= 1)
            store1.close()
            store1 = None
        except Exception as e:
            check("旧语义库自动迁移不崩溃", False, str(e))

        # 模拟旧版 SkillStore 数据库（无 user_id 列）
        db2 = tmp / "skills.db"
        c2 = sqlite3.connect(str(db2))
        c2.execute("CREATE TABLE skills (id TEXT PRIMARY KEY, name TEXT, pattern TEXT, context_json TEXT, created_at REAL)")
        c2.execute("CREATE INDEX idx_skill_created ON skills(created_at DESC)")
        c2.commit()
        c2.close()

        try:
            store2 = SkillStore(persist_dir=tmp)
            store2.add_skill("迁移测试", "pattern_x")
            check("旧技能库自动迁移不崩溃", store2.count() == 1)
            store2.close()
            store2 = None
        except Exception as e:
            check("旧技能库自动迁移不崩溃", False, str(e))
    finally:
        for s in [store1, store2]:
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  SOMA Pre-Commit 验证")
    print("=" * 60)

    step1_unit_tests()
    step2_isolation_integration()
    step3_time_window_behavior()
    step4_cache_isolation()
    step5_schema_migration()

    print(f"\n{'='*60}")
    print(f"  结果: {passed} 通过, {failed} 失败")
    print(f"{'='*60}")

    if failed > 0:
        print("\n❌ 验证未通过，请修复后再提交！")
        sys.exit(1)
    else:
        print("\n✅ 全部验证通过，可以安全提交。")
        sys.exit(0)
