"""SOMA 快速验证 — python -m soma"""
import os
import sys
import warnings

# 抑制第三方库噪音，提升首次体验
os.environ.setdefault("LITELLM_LOG", "ERROR")
warnings.filterwarnings("ignore", category=UserWarning, module="jieba")
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*pkg_resources.*")


def main():
    print("=" * 56)
    print("  🧠 SOMA — Somatic Wisdom Architecture v0.3.3b2")
    print("  五分钟接入，让你的 Agent 学会智者思维")
    print("=" * 56)

    try:
        from soma import SOMA

        print("\n⏳ 初始化中...")
        soma = SOMA()

        stats = soma.stats
        print(f"✅ 初始化完成")
        print(f"   思维框架: 7 条智慧规律")
        print(f"   记忆库: {stats['episodic']} 条情节 / {stats['semantic']} 条语义")
        print(f"   向量索引: {stats.get('indexed_vectors', 0)} 条")

        # 冷启动：注入示例记忆
        if stats["episodic"] == 0:
            print("\n📝 注入示例记忆...")
            soma.remember(
                "第一性原理：回归事物最基本的要素，从底层逻辑出发推导。"
                "在商业中，关注客户的根本需求而非竞争对手的行为。",
                context={"domain": "哲学", "type": "理论"},
                importance=0.95,
            )
            soma.remember(
                "系统思维：增长是一个系统行为，涉及产品、市场、团队"
                "等多个要素的相互作用。增长停滞往往是负反馈回路。",
                context={"domain": "思维", "type": "方法论"},
                importance=0.9,
            )
            print("   已注入 2 条示例记忆")

        # 语义搜索
        print("\n🔍 测试语义搜索...")
        results = soma.query_memory("如何找到问题的最根本原因", top_k=3)
        for r in results:
            print(f"   [{r['activation_score']:.3f}] {r['content_preview'][:60]}...")

        # 问题拆解
        print("\n💡 测试问题拆解...")
        foci = soma.decompose("为什么公司增长停滞？")
        for f in foci:
            print(f"   [{f.law_id}] (权重 {f.weight:.2f}) {f.dimension[:80]}")

        # 当前权重
        print(f"\n📊 当前规律权重: {soma.get_weights()}")
        print(f"\n{'=' * 56}")
        print("接入就绪！现在可以在代码中使用:")
        print()
        print("  from soma import SOMA")
        print("  soma = SOMA()")
        print("  answer = soma.respond(\"你的问题\")")
        print()
        print("详细文档: https://github.com/soma-project/soma-core")
        print(f"{'=' * 56}")

    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        print("请确认依赖安装完整: pip install soma-core[dev]")
        sys.exit(1)


if __name__ == "__main__":
    main()
