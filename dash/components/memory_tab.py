"""Memory 标签页 — 记忆统计、浏览、搜索、添加"""
import streamlit as st

from soma.base import Focus


def render_memory_tab(agent):
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("📊 统计面板")
        stats = agent.memory.stats()
        st.metric("情节记忆", stats["episodic"])
        st.metric("语义三元组", stats["semantic"])
        st.metric("技能模式", stats["skill"])
        st.metric("向量已索引", stats.get("indexed_vectors", 0))

        st.divider()
        st.subheader("➕ 添加记忆")
        with st.form("add_memory_form"):
            content = st.text_area("记忆内容", placeholder="输入知识片段...")
            domain = st.text_input("领域 (domain)", value="通用")
            mem_type = st.text_input("类型 (type)", value="笔记")
            importance = st.slider("重要性", 0.0, 1.0, 0.7, 0.05)
            if st.form_submit_button("保存记忆", type="primary"):
                if content.strip():
                    mid = agent.remember(
                        content,
                        context={"domain": domain, "type": mem_type},
                        importance=importance,
                    )
                    st.success(f"已保存: {mid[:8]}...")
                    st.rerun()

        st.divider()
        st.subheader("🔗 添加语义三元组")
        with st.form("add_semantic_form"):
            subj = st.text_input("主语 (subject)")
            pred = st.text_input("谓词 (predicate)")
            obj = st.text_input("宾语 (object)")
            if st.form_submit_button("保存三元组"):
                if subj.strip() and pred.strip() and obj.strip():
                    agent.remember_semantic(subj, pred, obj)
                    st.success("已保存语义三元组")
                    st.rerun()

    with col2:
        st.subheader("🔍 记忆搜索")

        search_query = st.text_input(
            "搜索关键词", placeholder="输入关键词搜索记忆..."
        )

        if search_query.strip():
            results = agent.query_memory(search_query, top_k=20)
            if results:
                st.caption(f"找到 {len(results)} 条相关记忆")
                for r in results:
                    with st.container(border=True):
                        st.markdown(
                            f"**分数**: `{r['activation_score']:.3f}` "
                            f"| **来源**: {r['source']} "
                            f"| **重要性**: {r['importance']:.2f}"
                        )
                        st.write(r["content_preview"])
            else:
                st.info("未找到相关记忆")
