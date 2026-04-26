"""Chat 标签页 — 问题输入、拆解可视化、记忆卡片、最终答案"""
import streamlit as st


def render_chat_tab(agent):
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("💭 提出问题")
        problem = st.text_area(
            "输入你想分析的问题",
            placeholder="例如：为什么新产品增长停滞？",
            height=80,
            key="chat_problem",
        )

        if st.button("🔍 深度分析", type="primary", disabled=not problem.strip()):
            with st.spinner("正在拆解问题..."):
                foci = agent.decompose(problem)

            st.markdown("### 🔬 问题拆解")
            for f in foci:
                with st.expander(f"**{f.law_id}** (权重: {f.weight:.2f})", expanded=True):
                    st.caption(f"触发原因: {f.rationale}")
                    st.write(f.dimension)
                    st.caption(f"关键词: {', '.join(f.keywords[:5])}")

            with st.spinner("正在激活相关记忆..."):
                activated = agent.hub.activate(foci)

            st.markdown("### 🧩 激活的记忆资粮")
            if activated:
                for am in activated:
                    with st.container(border=True):
                        cols = st.columns([3, 1])
                        cols[0].markdown(
                            f"**[{am.source}]** 关联度: `{am.activation_score:.3f}`"
                        )
                        cols[0].write(am.memory.content)
                        cols[1].metric("重要度", f"{am.memory.importance:.2f}")
                        cols[1].metric("访问", am.memory.access_count)
            else:
                st.info("无直接相关的记忆资粮")

            with st.spinner("正在综合分析..."):
                answer = agent.respond(problem)

            st.markdown("### 📝 智者回答")
            st.markdown(answer)

            # 记录为成功
            agent.reflect(f"dashboard_{len(agent.evolver.get_log())}", "success")

    with col2:
        st.subheader("📊 系统概览")
        stats = agent.memory.stats()
        st.metric("情节记忆", stats["episodic"])
        st.metric("语义三元组", stats["semantic"])
        st.metric("技能模式", stats["skill"])
        st.metric("向量索引", stats["indexed_vectors"])

        st.divider()
        st.subheader("⚖️ 规律权重")
        weights = agent.evolver.get_weights()
        for law_id, weight in weights.items():
            st.metric(law_id, f"{weight:.3f}")

        st.divider()
        st.subheader("🧠 提示词结构")
        st.caption("最后一步 LLM 调用的完整 Prompt")
        if "last_prompt" not in st.session_state:
            st.session_state.last_prompt = ""
        if st.button("📋 复制上一个 Prompt"):
            st.code(st.session_state.last_prompt or "（暂无）", language="markdown")
