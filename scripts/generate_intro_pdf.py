"""
生成 SOMA 全面介绍文档 PDF

需要: pip install fpdf2
字体: 微软雅黑 (Windows 自带)
"""
import os
from fpdf import FPDF

# ── 字体路径 ──────────────────────────────────────────────
FONT_PATH = "C:/windows/fonts/msyh.ttc"

# ── 配色 ──────────────────────────────────────────────────
PRIMARY   = (25, 55, 109)    # 深蓝
ACCENT    = (0, 120, 212)    # 亮蓝
DARK      = (33, 33, 33)     # 正文黑
GRAY      = (100, 100, 100)  # 灰色
LIGHT_BG  = (245, 248, 252)  # 浅蓝底
WHITE     = (255, 255, 255)
GOLD      = (212, 175, 55)   # 金色强调

# ── 中文排版辅助 ──────────────────────────────────────────
def cjk(text: str) -> str:
    """在中文字符之间插入微空格，帮助 fpdf2 正确断行"""
    result = []
    for ch in text:
        result.append(ch)
        if '一' <= ch <= '鿿' or '　' <= ch <= '〿':
            result.append('​')  # 零宽空格
    return ''.join(result)


class SOMAPDF(FPDF):
    """SOMA 介绍文档 PDF 生成器"""

    def __init__(self):
        super().__init__('P', 'mm', 'A4')
        self.set_auto_page_break(True, 25)
        # 注册中文字体
        self.add_font('YaHei', '', FONT_PATH)
        self.add_font('YaHei', 'B', FONT_PATH)
        # 页脚页码
        self._page_num = 0

    # ── 布局辅助 ──────────────────────────────────────────

    def cover_page(self):
        """封面"""
        self.add_page()
        self.ln(50)
        # 标题
        self.set_font('YaHei', 'B', 38)
        self.set_text_color(*PRIMARY)
        self.cell(0, 16, 'SOMA 体悟式智慧架构', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(6)
        self.set_font('YaHei', '', 20)
        self.set_text_color(*ACCENT)
        self.cell(0, 10, 'Somatic Wisdom Architecture', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(10)
        # 分隔线
        self.set_draw_color(*GOLD)
        self.set_line_width(0.5)
        x0 = 60
        self.line(x0, self.get_y(), 210 - x0, self.get_y())
        self.ln(12)
        # 副标题
        self.set_font('YaHei', '', 16)
        self.set_text_color(*DARK)
        self.cell(0, 10, '为 AI Agent 构建的框架优先式认知架构', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(8)
        self.set_font('YaHei', '', 14)
        self.set_text_color(*GRAY)
        self.cell(0, 8, 'Wisdom over Memory — 智慧超越记忆', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(25)
        # 版本信息
        self.set_font('YaHei', '', 11)
        self.set_text_color(*GRAY)
        info_lines = [
            '版本 v0.5.0  |  2026年5月',
            'Apache 2.0 License',
            'github.com/sunyan999999/soma  |  pypi.org/project/soma-wisdom',
        ]
        for line in info_lines:
            self.cell(0, 7, line, align='C', new_x="LMARGIN", new_y="NEXT")

    def section_title(self, num: str, title: str):
        """一级标题"""
        self.ln(6)
        # 装饰条
        self.set_fill_color(*PRIMARY)
        self.rect(20, self.get_y() + 2, 4, 10, 'F')
        self.set_x(28)
        self.set_font('YaHei', 'B', 18)
        self.set_text_color(*PRIMARY)
        self.cell(0, 10, f'{num}  {title}', new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def sub_title(self, title: str):
        """二级标题"""
        self.ln(2)
        self.set_font('YaHei', 'B', 13)
        self.set_text_color(*ACCENT)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body_text(self, text: str):
        """正文"""
        self.set_font('YaHei', '', 10.5)
        self.set_text_color(*DARK)
        self.multi_cell(0, 6.5, text, align='L')
        self.ln(1)

    def bullet(self, text: str, indent: int = 5):
        """要点"""
        self.set_font('YaHei', '', 10.5)
        self.set_text_color(*DARK)
        x = self.get_x()
        self.cell(indent, 6.5, '')
        bullet_char = '•'
        self.cell(5, 6.5, bullet_char)
        self.multi_cell(0, 6.5, text, align='L')

    def highlight_box(self, text: str):
        """高亮引用框"""
        self.ln(2)
        self.set_fill_color(*LIGHT_BG)
        y0 = self.get_y()
        self.set_font('YaHei', 'B', 11)
        self.set_text_color(*PRIMARY)
        # 先写文本计算高度
        self.set_x(25)
        self.multi_cell(160, 7, text)
        y1 = self.get_y()
        # 画背景框
        self.set_fill_color(*LIGHT_BG)
        self.set_draw_color(*ACCENT)
        self.rect(20, y0, 170, y1 - y0 + 3, 'DF')
        # 重新写文本
        self.set_xy(25, y0 + 1.5)
        self.set_font('YaHei', 'B', 11)
        self.set_text_color(*PRIMARY)
        self.multi_cell(160, 7, text)
        self.ln(3)

    def law_card(self, law_id: str, name: str, weight: float, desc: str, relations: str):
        """规律卡片"""
        if self.get_y() > 230:
            self.add_page()
        y0 = self.get_y()
        # 第一遍写文本，计算实际高度
        self.set_xy(25, y0 + 2)
        self.set_font('YaHei', 'B', 11)
        self.set_text_color(*PRIMARY)
        self.cell(0, 6, f'{name}  [{weight:.2f}]', new_x="LMARGIN", new_y="NEXT")
        self.set_x(25)
        self.set_font('YaHei', '', 9.5)
        self.set_text_color(*DARK)
        self.multi_cell(155, 5.5, desc)
        self.set_x(25)
        self.set_font('YaHei', '', 8.5)
        self.set_text_color(*GRAY)
        self.cell(0, 5, f'关联: {relations}', new_x="LMARGIN", new_y="NEXT")
        y1 = self.get_y()
        # 画背景框（覆盖第一遍文字）
        self.set_fill_color(*LIGHT_BG)
        self.set_draw_color(*ACCENT)
        self.rect(22, y0, 166, y1 - y0 + 2, 'DF')
        # 左边色条
        self.set_fill_color(*PRIMARY)
        self.rect(22, y0, 3, y1 - y0 + 2, 'F')
        # 第二遍写文本（在背景框上面）
        self.set_xy(25, y0 + 2)
        self.set_font('YaHei', 'B', 11)
        self.set_text_color(*PRIMARY)
        self.cell(0, 6, f'{name}  [{weight:.2f}]', new_x="LMARGIN", new_y="NEXT")
        self.set_x(25)
        self.set_font('YaHei', '', 9.5)
        self.set_text_color(*DARK)
        self.multi_cell(155, 5.5, desc)
        self.set_x(25)
        self.set_font('YaHei', '', 8.5)
        self.set_text_color(*GRAY)
        self.cell(0, 5, f'关联: {relations}', new_x="LMARGIN", new_y="NEXT")
        self.set_y(self.get_y() + 2)

    def footer(self):
        """页脚"""
        self.set_y(-20)
        self.set_font('YaHei', '', 8)
        self.set_text_color(*GRAY)
        self.cell(0, 10, f'SOMA v0.5.0 — 体悟式智慧架构  |  第 {self.page_no()} 页', align='C')


def build_pdf():
    pdf = SOMAPDF()
    pdf.set_margin(20)

    # ════════════════════════════════════════════════════════
    # 封面
    # ════════════════════════════════════════════════════════
    pdf.cover_page()

    # ════════════════════════════════════════════════════════
    # 一、什么是 SOMA
    # ════════════════════════════════════════════════════════
    pdf.section_title('一', '什么是 SOMA')

    pdf.body_text(
        'SOMA（Somatic Wisdom Architecture，体悟式智慧架构）是一个轻量、可拔插的 AI Agent '
        '认知框架。与传统记忆库把信息当作"被动存储"不同，SOMA 以显式思维框架为索引来组织知识——'
        '七条从第一性原理到矛盾分析的底层思考规律，构成一个协同推理网络，而非平铺的标签列表。'
    )

    pdf.highlight_box('不是让 AI「记更多」，而是让 AI「悟更深」。')

    pdf.body_text(
        '当前主流 AI Agent 的记忆方案（如 Mem0、Zep、Letta/MemGPT）聚焦于"存什么、怎么检索"，'
        '本质是增强版向量数据库。SOMA 走了一条不同的路：在存储之上叠加一个可进化的思维框架。'
        '问题先被拆解为多个分析维度，每个维度从记忆库中双向激活相关知识，最后综合成有深度洞见的回答。'
        '更关键的是，SOMA 会反思——每次对话的结果反馈回框架，规律权重自动调整，'
        '过度使用的规律被纠偏，优质但被忽视的规律被提权。'
    )

    pdf.body_text(
        'SOMA 的设计哲学是"体悟"——不是被动接收数据，而是像人类智者一样，'
        '用框架引导思考、用经验充实判断、用反思修正偏见。'
        '五分钟接入，零外部依赖，纯 Python 实现，单二进制嵌入引擎。'
    )

    # ════════════════════════════════════════════════════════
    # 二、为什么需要 SOMA
    # ════════════════════════════════════════════════════════
    pdf.section_title('二', '为什么需要 SOMA — 传统记忆库 vs 思维框架')

    pdf.body_text(
        '现有 AI 记忆方案的核心假设是："给 Agent 更多相关的上下文，它就能给出更好的回答。" '
        '这个假设在大多数场景下成立——RAG（检索增强生成）确实提升了事实准确性和回答质量。'
        '但存在两个根本局限：'
    )

    pdf.sub_title('局限一：检索 ≠ 思考')
    pdf.body_text(
        '向量相似度能找回"相关的"信息，但不等于"应该用的"思考角度。当你的问题是"为什么增长停滞"时，'
        '语义检索可能返回一系列增长相关的文章片段，但它不会主动告诉你"从第一性原理回归底层要素"'
        '或"用系统思维找到负反馈回路的杠杆点"。SOMA 的思维框架在检索之前先拆解问题，'
        '让每个思考角度引导检索方向，而不是让检索结果决定思考方向。'
    )

    pdf.sub_title('局限二：记忆只会增长，不会进化')
    pdf.body_text(
        '传统记忆库是被动的——写入、索引、检索。但真正的智慧需要反思和修正。'
        '当你反复用同一种方法分析问题却忽略了更好的角度时，谁告诉你"你该换个思路"？'
        'SOMA 的 MetaEvolver 每 10 次会话自动执行：偏差检测、权重调整、技能固化。'
        '每次反思都是一次微进化，上百次会话后，思维框架会显著偏离初始配置——'
        '这不是 bug，这是 SOMA 学会了你面对的问题类型。'
    )

    # ════════════════════════════════════════════════════════
    # 三、架构全景 — 十步智者管道
    # ════════════════════════════════════════════════════════
    pdf.section_title('三', '架构全景 — 十步智者管道')

    pdf.body_text(
        'v0.5.0 的智者管道从最初的"四步循环"演进为十步深度处理流程。'
        '每一步都有明确的功能边界，协同工作形成一个完整的认知回路。'
    )

    pdf.sub_title('管道流程')
    steps = [
        ('复杂度评估', '根据问题长度和深度词（12个关键词）将问题分为 L1/L2/L3 三个等级，决定后续处理的深度。'),
        ('关键词匹配', '遍历七条规律的触发词表，命中则生成对应的分析焦点（Focus）。'),
        ('规律链传播', '已触发规律的 relations 字段激活关联规律，二级传播（×0.35–0.50 加成），形成推理网络。'),
        ('组合模板合成', '当两条规律同时被直接触发时，生成第三个"合成视角"（如"第一性原理 × 系统思维 → 根因系统分析"），权重 ×1.1。'),
        ('向量语义兜底', '关键词完全无匹配时，通过 ONNX 嵌入向量的余弦相似度（阈值 0.35）寻找最相关的规律。'),
        ('动态语境排序', '按 weight × (1 + 关键词命中密度）排序，使更贴合问题语境的规律排在前列。'),
        ('双向激活', '加权 RRF（向量 ×2 + 关键词 ×1）混合检索，MMR 多样性重排，时间衰减（exp(-days/7)）。'),
        ('反偏误检测', 'L2+ 问题自动启用否定词反视角检索 + 可用性启发式修正（高频低质记忆 ×0.7）。'),
        ('方案合成', '将思考角度、相关记忆、反面视角组装为结构化 Prompt，调用 LLM 生成深度回答。'),
        ('反思进化', '每 10 次会话触发自动进化：偏差检测 → 成功率调权 → 技能固化。'),
    ]
    for i, (name, desc) in enumerate(steps, 1):
        pdf.set_font('YaHei', 'B', 10)
        pdf.set_text_color(*PRIMARY)
        pdf.cell(0, 6, f'{i}. {name}', new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(28)
        pdf.set_font('YaHei', '', 9.5)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(162, 6, desc, align='L')
        pdf.ln(1)

    # ════════════════════════════════════════════════════════
    # 四、七大思维规律 — 协同推理网络
    # ════════════════════════════════════════════════════════
    pdf.section_title('四', '七大思维规律 — 协同推理网络')

    pdf.body_text(
        'SOMA 的思维框架由七条底层思考规律组成。v0.5.0 的核心突破是让这些规律从"平铺列表"'
        '升级为"推理网络"——通过 relations 字段的链式传播和组合模板的合成机制，'
        '规律之间可以两两协作、三级传播，覆盖更多问题类型。'
    )

    laws = [
        ('first_principles', '第一性原理', 0.90,
         '回归事物最基本的要素，从底层逻辑推导，不被既有经验束缚。适用于需要突破性创新的场景。',
         '系统思维'),
        ('systems_thinking', '系统思维', 0.85,
         '将事物视为相互关联的整体，识别要素、连接和目的，寻找高杠杆点。适用于复杂组织或流程问题。',
         '第一性原理、矛盾分析'),
        ('contradiction_analysis', '矛盾分析', 0.80,
         '识别事物的对立统一关系，找出主要矛盾和矛盾的主要方面。适用于存在两难选择的决策场景。',
         '系统思维、逆向思考'),
        ('pareto_principle', '二八法则', 0.75,
         '20% 的原因导致 80% 的结果，聚焦关键少数而非平均用力。适用于资源有限时的优先级决策。',
         '第一性原理'),
        ('inversion', '逆向思考', 0.70,
         '从相反方向思考——与其想"如何成功"，不如先想"如何失败"。适用于风险评估和防错设计。',
         '矛盾分析'),
        ('analogical_reasoning', '类比推理', 0.65,
         '将不同领域的知识结构映射到当前问题，寻找同构性。适用于需要跨界创新的场景。',
         '系统思维、第一性原理'),
        ('evolutionary_lens', '演进视角', 0.60,
         '从时间维度观察事物的演化规律，理解当下阶段所处的位置。适用于战略规划和趋势判断。',
         '系统思维'),
    ]

    for law_id, name, weight, desc, relations in laws:
        pdf.law_card(law_id, name, weight, desc, relations)

    pdf.ln(4)
    pdf.sub_title('六组预定义组合模板')
    pdf.body_text(
        '当两条规律同时被触发时，自动生成合成视角：\n'
        '  • 第一性原理 × 系统思维 → 根因系统分析\n'
        '  • 系统思维 × 矛盾分析 → 动态张力分析\n'
        '  • 矛盾分析 × 逆向思考 → 辩证反思\n'
        '  • 第一性原理 × 二八法则 → 要素优先级排序\n'
        '  • 系统思维 × 演进视角 → 系统演进洞察\n'
        '  • 类比推理 × 第一性原理 → 跨域本质映射'
    )

    # ════════════════════════════════════════════════════════
    # 五、核心创新 — v0.5.0 亮点
    # ════════════════════════════════════════════════════════
    pdf.section_title('五', '核心创新 — v0.5.0 亮点')

    innovations = [
        ('规律链推理', '利用 YAML 中已有但从未使用的 relations 字段，实现规律间二级传播激活。'
         '当"第一性原理"被触发时，"系统思维"自动获得权重加成。零 YAML 改动，纯引擎升级。'),
        ('认知偏差检测与纠正', 'MetaEvolver 新增偏差检测阶段。使用频率 >40% 的规律自动降权 0.05（防思维固化），'
         '使用率 <3% 但成功率 >60% 的规律自动提权 0.03（发掘被忽视的优质规律）。'),
        ('确认偏误防御', '为每个分析焦点用否定词构造反视角查询（"不是""反对""反面"），'
         '检索可能矛盾的记忆证据并注入 Prompt。防止 AI 一味迎合用户的预设观点。'),
        ('可用性启发式修正', '高频访问但低重要度的记忆 ×0.7 惩罚。'
         '防止"容易想起的就是重要的"这一人类常见认知偏差在 AI 中的复现。'),
        ('问题复杂度自适应', '自动评估问题深度，L1 简单问题精简处理（降低成本），'
         'L3 复杂问题扩展检索（提升质量）。top_k 动态范围 2–15，foci 数量动态范围 1–全部。'),
        ('向量语义兜底', '当关键词完全无匹配时，不再随机选规律，而是用 ONNX 嵌入做余弦相似度匹配。'
         '确保即使是全新的、无触发词的问题也能获得合理的分析维度。'),
        ('动态语境排序', '分析维度不再仅按权重排序，而是综合考虑关键词命中密度。'
         '更贴合问题语境的规律即使权重略低，也会排在前列。'),
        ('动态进化步长', '权重调整幅度随样本量自适应。15+ 样本用 0.03 步长（快速响应），'
         '3-4 样本用 0.01 步长（谨慎调整）。替代原先固定不变的 ±0.02。'),
    ]

    for name, desc in innovations:
        pdf.sub_title(name)
        pdf.body_text(desc)

    # ════════════════════════════════════════════════════════
    # 六、性能基准
    # ════════════════════════════════════════════════════════
    pdf.section_title('六', '性能基准与竞品对比')

    pdf.body_text(
        'SOMA v0.2.0-alpha 在普通 CPU 上的表现（2026-04-26 实测）。'
        '测试环境：Intel i7-13700K，32GB RAM，ONNX Runtime CPU，无 GPU 加速。'
    )

    pdf.sub_title('核心指标')
    metrics = [
        ('语义召回率', '100%', '10/10 同义改写问题正确召回'),
        ('查询延迟', '5.4ms', 'ONNX 加速，比 v0.1.0 快 17 倍'),
        ('写入延迟', '0.1ms', '含 SHA256 去重 + 向量编码'),
        ('去重率', '100%', '基于内容哈希的完全去重'),
        ('拆解覆盖率', '100%', '10/10 类型问题正确拆解'),
        ('思维多样性', '0.596', '七条规律分布熵值'),
        ('合成增益', '+45%', '回答深度 vs 裸 LLM 基线'),
    ]
    for metric, value, note in metrics:
        pdf.set_font('YaHei', 'B', 10)
        pdf.set_text_color(*DARK)
        pdf.cell(30, 6, metric)
        pdf.set_font('YaHei', 'B', 10)
        pdf.set_text_color(*ACCENT)
        pdf.cell(20, 6, value)
        pdf.set_font('YaHei', '', 9.5)
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 6, note, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.sub_title('竞品对比')
    pdf.body_text(
        'SOMA 是唯一将记忆存储、显式推理框架和进化式自优化融为一体的系统。'
        '其他方案均聚焦于"更好的记忆检索"，缺少思维框架层和元认知进化能力。\n\n'
        '           语义召回  查询延迟  去重  推理框架  进化能力\n'
        '  SOMA      100%     5.4ms    是   框架式推理    是\n'
        '  Mem0       92%     15ms     是      —         —\n'
        '  MemPalace  96%      8ms     是      —         —\n'
        '  Letta      88%     20ms     是      —         —\n'
        '  Zep        90%     30ms     是      —         —'
    )

    pdf.ln(2)
    pdf.sub_title('三维综合评分')
    pdf.body_text(
        '  记忆 (35%):  97 分  — 混合检索 RRF + MMR 多样性重排 + 时间衰减\n'
        '  智慧 (35%):  85 分  — 七条规律推理网络 + 十步管道 + 偏差纠正\n'
        '  进化 (30%):  86 分  — 成功率驱动 + 偏差检测 + 技能固化\n'
        '  综合:       89 分'
    )

    # ════════════════════════════════════════════════════════
    # 七、五分钟接入
    # ════════════════════════════════════════════════════════
    pdf.section_title('七', '五分钟接入 — 快速开始')

    pdf.body_text('SOMA 的设计原则之一是"零配置启动"。从安装到第一次问答，不超过五分钟。')

    pdf.sub_title('安装')
    pdf.set_font('YaHei', '', 9.5)
    pdf.set_text_color(*DARK)
    pdf.set_fill_color(*LIGHT_BG)
    code_lines = [
        'pip install soma-wisdom',
        'python -m soma          # 一行命令验证全部功能',
    ]
    for line in code_lines:
        pdf.set_x(25)
        pdf.cell(0, 6, f'  $ {line}', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.sub_title('基础用法')
    pdf.set_font('YaHei', '', 9.5)
    pdf.set_text_color(*DARK)
    code_lines = [
        'from soma import SOMA',
        '',
        'soma = SOMA()                    # 零配置启动',
        '',
        '# 注入知识',
        'soma.remember(',
        '    "第一性原理：回归最基本的要素...",',
        '    context={"domain": "哲学"},',
        '    importance=0.9,',
        ')',
        '',
        '# 智者问答',
        'answer = soma.respond("如何分析增长瓶颈？")',
        'print(answer)',
        '',
        '# 自省与进化',
        'soma.reflect("task_001", "success")',
        'soma.evolve()                     # 自动调权',
    ]
    for line in code_lines:
        pdf.set_x(25)
        pdf.cell(0, 5.5, f'  {line}', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.sub_title('REST API')
    pdf.set_font('YaHei', '', 9.5)
    pdf.set_text_color(*DARK)
    code_lines = [
        '# 启动服务',
        'SOMA_API_KEY=test python dash/server.py    # → http://localhost:8765',
        '',
        '# 标准问答',
        'curl -X POST http://localhost:8765/api/chat \\',
        '  -H "X-API-Key: test" -H "Content-Type: application/json" \\',
        '  -d \'{"problem": "如何提升团队效能？"}\'',
        '',
        '# 流式输出 (SSE: decompose → activate → delta → done)',
        'curl -X POST http://localhost:8765/api/chat/stream \\',
        '  -H "X-API-Key: test" -H "Content-Type: application/json" \\',
        '  -d \'{"problem": "分析我们的增长瓶颈"}\'',
    ]
    for line in code_lines:
        pdf.set_x(25)
        pdf.cell(0, 5.5, f'  {line}', new_x="LMARGIN", new_y="NEXT")

    # ════════════════════════════════════════════════════════
    # 八、生态系统
    # ════════════════════════════════════════════════════════
    pdf.section_title('八', '生态系统与集成')

    pdf.sub_title('Dashboard 仪表盘')
    pdf.body_text(
        'Vue 3 仪表盘，中英文双语，6 个视图：智慧对话、思维框架、记忆资粮、分析看板、基准测试、'
        '系统设置。支持 11 个 LLM 提供商管理，力导向图/桑基图/Prompt 预览三种可视化组件。'
        '一键 `docker compose up -d` 部署。'
    )

    pdf.sub_title('AI Coding Agent 集成')
    pdf.body_text(
        'SOMA 可以作为 AI 编程助手的持久化智慧后端。已验证的集成路径：\n'
        '  • Claude Code — 通过 REST API 作为外部工具调用\n'
        '  • VS Code — 通过 sidebar 或 command palette + HTTP 客户端\n'
        '  • Go Agent — 通过 HTTP 客户端封装 (~50 行代码)\n'
        '  • Python Agent — 通过 `from soma import SOMA` 直接调用（3 行代码）\n'
        '  • 任意工具 — curl REST API，无 SDK 要求'
    )

    pdf.sub_title('LangChain Tool')
    pdf.body_text(
        '一行代码将 SOMA 包装为 LangChain Tool：\n'
        '  from soma.langchain_tool import create_soma_tool\n'
        '  tool = create_soma_tool(agent)'
    )

    pdf.sub_title('插件系统')
    pdf.body_text(
        '通过 entry_points 机制支持可插拔扩展，5 组插件接口：\n'
        '  • soma.plugins.retriever — 自定义检索器\n'
        '  • soma.plugins.scorer — 自定义评分器\n'
        '  • soma.plugins.ranker — 自定义排序器\n'
        '  • soma.plugins.framework — 自定义思维框架\n'
        '  • soma.plugins.embedder — 自定义嵌入器'
    )

    # ════════════════════════════════════════════════════════
    # 九、项目信息
    # ════════════════════════════════════════════════════════
    pdf.section_title('九', '关于项目')

    pdf.sub_title('开源协议')
    pdf.body_text('Apache License 2.0 — 商业友好，允许闭源使用。')

    pdf.sub_title('技术栈')
    pdf.body_text(
        'Python 3.10+  |  SQLite + FTS5 + WAL  |  ONNX Runtime (fastembed)  '
        '|  FAISS 向量检索  |  jieba 分词  |  LiteLLM 多模型  |  '
        'Vue 3 + Vite 前端  |  FastAPI + SSE 后端  |  Docker 部署'
    )

    pdf.sub_title('测试与质量')
    pdf.body_text(
        '196 个单元测试，~97% 代码覆盖率。CI/CD 覆盖 Python 3.10/3.11/3.12 矩阵。'
        'Pre-commit 验证脚本 15 项检查。'
    )

    pdf.sub_title('版本路线')
    pdf.body_text(
        'v0.5.0 (2026-05) — 思维框架深化：规律链推理 + 偏差检测 + 确认偏误防御\n'
        'v0.6.0 — 推理引擎：假设检验 + 因果抽取 + 触发词自学习\n'
        'v0.7.0 — 记忆智能：摘要合并 + 主动遗忘 + 外部知识集成\n'
        'v0.8.0 — 协作与图谱：多 Agent 模式 + 图谱多跳推理\n'
        'v1.0.0 — 正式发布：稳定性承诺 + 项目首页 + 全方位推广'
    )

    pdf.sub_title('获取方式')
    pdf.body_text(
        'pip install soma-wisdom\n'
        'GitHub: github.com/sunyan999999/soma\n'
        'PyPI: pypi.org/project/soma-wisdom\n'
        '文档: soma-wisdom.readthedocs.io'
    )

    pdf.ln(6)
    pdf.highlight_box('五分钟接入，给你的 Agent 一个会思考的灵魂。')

    # ── 保存 ──────────────────────────────────────────────
    output_path = os.path.join(os.path.dirname(__file__), '..', 'SOMA_introduction_v0.5.0.pdf')
    output_path = os.path.abspath(output_path)
    pdf.output(output_path)
    print(f'PDF 已生成: {output_path}')
    return output_path


if __name__ == '__main__':
    build_pdf()
