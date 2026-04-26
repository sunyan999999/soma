"""Framework 标签页 — 规律权重可视化、进化日志、手动调权"""
import streamlit as st


def render_framework_tab(agent):
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("⚖️ 规律权重")
        weights = agent.evolver.get_weights()

        # 简易条形图
        for law_id, weight in sorted(weights.items(), key=lambda x: -x[1]):
            ratio = weight
            color = (
                f"rgb({int(255*(1-ratio))}, {int(255*ratio)}, 100)"
            )
            st.markdown(
                f"**{law_id}**: {weight:.3f}"
            )
            st.progress(ratio)

        st.divider()
        st.subheader("📊 成功率统计")
        stats = agent.evolver.get_stats()
        if stats:
            for law_id, s in stats.items():
                st.metric(
                    f"{law_id}",
                    f"{s['success_rate']:.1%}",
                    delta=f"n={s['total']}",
                )
        else:
            st.info("暂无统计数据 — 完成分析后使用 reflect() 记录结果")

    with col2:
        st.subheader("🔧 手动调权")
        weights = agent.evolver.get_weights()
        for law_id, current_weight in weights.items():
            cols = st.columns([3, 1])
            new_weight = cols[0].slider(
                law_id,
                0.0,
                1.0,
                current_weight,
                0.01,
                key=f"weight_{law_id}",
            )
            if new_weight != current_weight:
                if cols[1].button("应用", key=f"apply_{law_id}"):
                    agent.evolver.adjust_weight(law_id, new_weight)
                    st.rerun()

        st.divider()
        st.subheader("🔄 自动进化")
        st.caption("基于成功率统计自动调整权重 (±0.02)")
        if st.button("执行 evolve()", type="primary"):
            changes = agent.evolver.evolve()
            if changes:
                st.success(f"已应用 {len(changes)} 项变更")
                for c in changes:
                    if c.get("type") == "skill_solidified":
                        st.info(f"🔨 固化技能: {c['skill_name']}")
                    else:
                        st.write(
                            f"**{c['law_id']}**: "
                            f"{c['old_weight']:.3f} → {c['new_weight']:.3f} "
                            f"(成功率: {c['success_rate']:.1%}, n={c['total_samples']})"
                        )
            else:
                st.info("无变更（数据不足或无需调整）")

        st.divider()
        st.subheader("📝 反思日志")
        log = agent.evolver.get_log()
        st.caption(f"共 {len(log)} 条记录")
        if st.button("🗑 清空日志"):
            agent.evolver.clear_log()
            st.rerun()
        if log:
            for entry in reversed(log[-20:]):
                st.text(
                    f"[{entry['task_id']}] {entry['outcome']} "
                    f"@ {entry.get('timestamp', '?')}"
                )
