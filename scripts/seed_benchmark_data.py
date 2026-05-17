"""SOMA 基准测试数据填充 — 批量写入1000条多领域记忆，供基准测试使用"""
import sys
import time
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from soma import SOMA

# ── 多领域记忆模板 ──
DOMAINS = {
    "哲学": [
        "第一性原理：从最基本要素出发推导问题的本质原因，而非依赖类比推理",
        "系统思维关注要素之间的相互连接和反馈回路，而非孤立分析",
        "矛盾分析识别表面问题下的深层对立统一关系，找到核心矛盾",
        "奥卡姆剃刀原则：如无必要勿增实体，最简单的解释往往最正确",
        "辩证法认为事物在矛盾的对立统一中发展，量变引起质变",
        "归纳推理与演绎推理是两种基本逻辑方法，前者从特殊到一般，后者反之",
        "因果关系与相关性是不同概念，相关性不蕴含因果性",
        "还原论将复杂系统拆解为基本组件，但可能忽略涌现特性",
        "目的论解释关注事物的目的和功能，而非仅关注机制",
        "实用主义强调理论的价值在于其实践效果，而非抽象真理",
    ],
    "技术": [
        "微服务架构将应用拆分为独立部署的小型服务，提高可维护性",
        "容器化技术通过Docker实现环境一致性，解决环境差异问题",
        "CI/CD持续集成持续部署加速软件开发周期，降低发布风险",
        "RESTful API设计遵循资源导向、无状态、统一接口原则",
        "数据库索引优化可以显著提升查询性能，但会增加写入开销",
        "缓存策略应当在一致性和性能之间取得平衡，根据场景选择",
        "消息队列解耦生产者和消费者，提高系统可靠性和扩展性",
        "设计模式如单例、工厂、观察者是常见问题的可复用解决方案",
        "函数式编程强调纯函数和不可变数据，减少副作用",
        "TDD测试驱动开发先写测试再写代码，确保代码质量",
        "Git版本控制的合并与变基各有优势，团队需统一策略",
        "WebSocket提供全双工通信，适合实时应用场景",
        "SQL注入是最常见的安全漏洞，参数化查询是基本防护",
        "负载均衡将请求分发到多个服务器，提高可用性和吞吐量",
        "CAP定理指出分布式系统最多同时满足一致性和可用性",
        "OAuth2.0是目前最广泛使用的授权框架，支持多种授权模式",
        "Kubernetes编排容器集群，自动处理调度、扩缩和故障恢复",
        "GraphQL允许客户端精确指定所需数据，减少过度获取",
        "正则表达式是强大的文本模式匹配工具，但可读性较差",
        "HTTPS通过TLS加密保护数据传输安全，已成Web标配",
    ],
    "管理": [
        "OKR目标管理方法将目标与关键结果对齐，驱动组织执行力",
        "敏捷开发强调迭代交付、响应变化、团队协作",
        "二八法则指出80%的结果来自20%的关键原因",
        "SWOT分析评估优势劣势机会威胁，辅助战略决策",
        "SMART原则要求目标具体、可衡量、可实现、相关、有时限",
        "金字塔原理强调结论先行、以上统下、归类分组",
        "跨部门沟通需要对齐利益点，找到共赢方案",
        "技术债务如果长期不偿还，会导致开发效率持续下降",
        "One-on-One面谈是管理者了解团队状态的重要工具",
        "项目三角形：范围、时间、成本的约束关系不可同时优化",
        "决策疲劳理论：连续决策会导致决策质量下降",
        "心理安全感是高绩效团队的关键特征之一",
        "帕金森定律：工作会膨胀以填满可用的完成时间",
        "破窗效应：小问题得不到治理会引发更多负面行为",
        "团队规模应当符合两个披萨原则，保持沟通效率",
    ],
    "AI/ML": [
        "Transformer架构通过自注意力机制彻底改变了NLP领域",
        "RAG检索增强生成将外部知识库与LLM结合，提高回答准确性",
        "向量数据库通过嵌入向量相似度搜索实现语义检索",
        "LoRA是一种高效的LLM微调方法，只训练少量参数",
        "RLHF通过人类反馈强化学习对齐模型行为与人类偏好",
        "过拟合是机器学习中的常见问题，通过正则化和交叉验证缓解",
        "特征工程是传统ML的关键环节，深度学习减少了对手工特征的依赖",
        "集成学习通过组合多个模型提高预测准确性和稳定性",
        "迁移学习利用预训练模型的知识解决新任务，大幅降低数据需求",
        "注意力机制允许模型关注输入的特定部分，是Transformer的核心",
        "词嵌入如Word2Vec将词语映射到连续向量空间捕获语义关系",
        "扩散模型通过逐步添加和去除噪声来生成高质量数据",
        "多模态AI能同时理解文本、图像、音频等多种信息形式",
        "提示工程是引导LLM产生期望输出的重要技能",
        "联邦学习允许在数据不出本地的前提下训练共享模型",
    ],
    "商业": [
        "网络效应：产品价值随用户数量增加而增加，形成护城河",
        "飞轮效应：各业务环节相互强化形成正向增长循环",
        "颠覆性创新从低端市场或新市场切入，逐步颠覆现有格局",
        "蓝海战略寻找无竞争的细分市场，而非在红海中厮杀",
        "精益创业通过MVP快速验证假设，减少创业浪费",
        "AARRR模型：获取、激活、留存、收入、传播的用户增长漏斗",
        "商业模式画布是分析和设计商业模式的九要素工具",
        "定价策略需要考虑成本、价值感知、竞争格局和支付意愿",
        "平台经济通过连接供需两端创造价值，核心是解决信息不对称",
        "渠道冲突是线上线下分销体系中最常见的管理难题",
        "品牌资产包含知名度、联想、感知质量和忠诚度四个维度",
        "长期主义强调做难而正确的事，追求复利效应",
    ],
    "心理学": [
        "认知偏差如确认偏误影响人们的判断和决策",
        "心流状态是人在挑战与能力平衡时体验到的最佳专注状态",
        "延迟满足能力与长期成就高度相关，是重要的自控力指标",
        "邓宁-克鲁格效应：能力不足者往往高估自己的能力水平",
        "框架效应：同一问题不同的表述方式会显著影响人们的决策",
        "社会认同理论：人们倾向于通过群体身份定义自己",
        "损失厌恶：人们对损失的敏感度大约是等量收益的两倍",
        "峰终定律：体验的记忆主要由峰值和结尾时刻决定",
        "习惯形成需要触发、行动、奖励三个要素构成循环",
        "成长型思维模式相信能力可以通过努力提升，更有韧性",
    ],
}

# ── 记忆条目生成器 ──

def generate_memories(total_count: int = 1000):
    """生成多领域多样化记忆条目"""
    domain_names = list(DOMAINS.keys())
    all_templates = []

    # 展开所有模板，按领域组织
    for domain, templates in DOMAINS.items():
        for i, template in enumerate(templates):
            all_templates.append((domain, template, i))

    # 重复模板直到达到所需数量
    memories = []
    base_count = len(all_templates)

    for i in range(total_count):
        domain, template, idx = all_templates[i % base_count]
        # 每次迭代添加细微变化，使内容不完全重复
        variation = i // base_count
        if variation > 0:
            content = f"{template}。这是第{variation+1}次强化记忆，加深对该概念的理解和应用。"
        else:
            content = template

        # 根据内容分配重要性
        importance = round(random.uniform(0.5, 0.95), 2)

        memories.append({
            "content": content,
            "context": {"domain": domain, "type": "理论" if idx % 3 == 0 else "案例" if idx % 3 == 1 else "方法论"},
            "importance": importance,
        })

    return memories


def main():
    total = 1000
    print(f"🧠 开始生成 {total} 条多领域记忆数据...")

    # 连接到 dashboard 使用的同一数据目录
    persist_dir = Path(__file__).parent.parent / "soma_data"

    soma = SOMA(
        persist_dir=str(persist_dir),
        top_k=5,
    )

    memories = generate_memories(total)

    print(f"  共生成 {len(memories)} 条记忆条目")
    print(f"  覆盖领域: {list(DOMAINS.keys())}")
    print()

    start_time = time.time()
    batch_size = 50
    last_report = 0

    for i, mem in enumerate(memories):
        soma.remember(
            mem["content"],
            context=mem["context"],
            importance=mem["importance"],
        )

        if (i + 1) % batch_size == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            remaining = (total - i - 1) / rate
            print(f"  进度: {i+1}/{total} ({((i+1)/total*100):.1f}%) "
                  f"速率: {rate:.1f}条/秒 预计剩余: {remaining:.0f}秒")

    elapsed = time.time() - start_time
    print(f"\n✅ 完成！共写入 {total} 条记忆，耗时 {elapsed:.1f} 秒")
    print(f"   平均速率: {total/elapsed:.1f} 条/秒")

    # 确认数据量
    stats = soma.stats
    print(f"\n📊 当前记忆统计:")
    for k, v in stats.items():
        print(f"   {k}: {v}")

    soma.close()


if __name__ == "__main__":
    main()
