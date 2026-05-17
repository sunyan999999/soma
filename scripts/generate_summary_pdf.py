"""生成 SOMA 版本演进总结 PDF — 排版精美、关键句彩色加粗"""
import os
from fpdf import FPDF

# ── 颜色定义 ──
C_TITLE      = (25, 60, 120)     # 深蓝 — 主标题
C_SUBTITLE   = (80, 80, 80)      # 深灰 — 副标题
C_VERSION    = (41, 128, 185)    # 蓝色 — 版本号
C_HEADING    = (30, 30, 30)      # 近黑色 — 小标题
C_BODY       = (60, 60, 60)      # 灰色 — 正文
C_HIGHLIGHT  = (192, 57, 43)     # 红 — 核心亮点句
C_TAGLINE    = (39, 174, 96)     # 绿 — 一句话总结
C_ARROW      = (142, 68, 173)    # 紫 — 箭头演进
C_LIGHT_BG   = (245, 248, 252)   # 浅蓝背景

FONT_PATH = "C:/Windows/Fonts/msyh.ttc"  # 微软雅黑


class SummaryPDF(FPDF):
    def __init__(self):
        super().__init__("P", "mm", "A4")
        self.add_font("CN", "", FONT_PATH, uni=True)
        self.add_font("CN", "B", "C:/Windows/Fonts/msyhbd.ttc", uni=True)
        self.set_auto_page_break(True, 20)

    # ── 辅助方法 ──

    def title_block(self, text: str):
        self.ln(8)
        self.set_font("CN", "B", 26)
        self.set_text_color(*C_TITLE)
        self.cell(0, 12, text, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def subtitle(self, text: str):
        self.set_font("CN", "", 11)
        self.set_text_color(*C_SUBTITLE)
        self.cell(0, 7, text, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def divider(self):
        self.ln(2)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.3)
        y = self.get_y()
        self.line(25, y, 185, y)
        self.ln(6)

    def section_title(self, version: str, tagline: str):
        self.ln(4)
        # 版本号
        self.set_font("CN", "B", 16)
        self.set_text_color(*C_VERSION)
        self.cell(0, 8, version, align="L", new_x="LMARGIN", new_y="NEXT")
        # 副标题
        self.set_font("CN", "B", 12)
        self.set_text_color(*C_HEADING)
        self.cell(0, 7, tagline, align="L", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body(self, text: str):
        self.set_font("CN", "", 10)
        self.set_text_color(*C_BODY)
        self.multi_cell(0, 6, text, align="L")
        self.ln(1)

    def bullet(self, text: str):
        self.set_font("CN", "", 10)
        self.set_text_color(*C_BODY)
        x0 = self.get_x()
        self.cell(8, 6, "•", align="C")
        self.multi_cell(0, 6, text, align="L")
        self.ln(0.5)

    def highlight(self, text: str):
        """红色加粗 — 关键句子"""
        self.set_font("CN", "B", 11)
        self.set_text_color(*C_HIGHLIGHT)
        self.multi_cell(0, 7, text, align="L")
        self.ln(1.5)

    def tagline_green(self, text: str):
        """绿色加粗 — 一句话总结"""
        self.set_font("CN", "B", 10.5)
        self.set_text_color(*C_TAGLINE)
        self.multi_cell(0, 6.5, text, align="L")
        self.ln(1)

    def arrow_chain(self, items: list):
        """紫色横向演进箭头"""
        self.set_font("CN", "B", 11)
        self.set_text_color(*C_ARROW)
        text = "  →  ".join(items)
        self.cell(0, 8, text, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def footnote(self, text: str):
        self.set_font("CN", "", 9)
        self.set_text_color(130, 130, 130)
        self.multi_cell(0, 5, text, align="C")


def build():
    pdf = SummaryPDF()
    pdf.set_left_margin(25)
    pdf.set_right_margin(25)

    # ═══ 封面 ═══
    pdf.add_page()
    pdf.ln(25)
    pdf.title_block("SOMA  版本演进总结")
    pdf.subtitle("v0.7.0 → v1.0.0   ·   2026年5月")
    pdf.divider()

    pdf.set_font("CN", "B", 13)
    pdf.set_text_color(*C_HIGHLIGHT)
    pdf.cell(0, 8, "从「聪明的记事本」到「认知伙伴」", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("CN", "", 10.5)
    pdf.set_text_color(*C_BODY)
    pdf.multi_cell(0, 6.5,
        "SOMA 在过去一个月里，从一个「记性好」的知识库，"
        "长成了一个会思考、会协作、会自我进化的智能体系统。"
        "五次版本跃迁，五张王牌，每一次都在解决一个根本问题。", align="C")
    pdf.ln(3)
    pdf.divider()

    # 演进概览
    pdf.arrow_chain(["会整理的记忆", "会推理的记忆", "会协作的团队", "会觉察的伙伴", "会分层的认知"])
    pdf.divider()

    # ═══ v0.7.0 ═══
    pdf.section_title("v0.7.0", "记忆不再「只进不出」")
    pdf.body("之前的 SOMA 像个无限扩容的仓库，什么都往里塞，从不清理。这一版给了它三种人脑才有的能力：")
    pdf.bullet("会合并 — 相似记忆自动归纳成一条，减少重复阅读")
    pdf.bullet("会遗忘 — 不重要的、很久不用的记忆自动归档，模拟人脑遗忘曲线")
    pdf.bullet("会学习 — 批量导入外部文档（Markdown、网页等），快速建立知识基础")
    pdf.ln(2)
    pdf.highlight("从「记账本」升级为「会整理的大脑」。")

    # ═══ v0.8.0 ═══
    pdf.section_title("v0.8.0", "从「找到」到「理解」")
    pdf.body("上一版解决了记忆怎么存，这一版解决了记忆怎么用。SOMA 开始真正理解记忆之间的关系：")
    pdf.bullet("发现因果链 — 不只告诉你「发生了什么」，还能回溯「为什么会这样」")
    pdf.bullet("标记矛盾 — 记忆中互相打架的观点，能自动发现并提醒")
    pdf.bullet("跨域联想 — 用生物学解释企业管理，在看似无关的领域间架桥")
    pdf.bullet("质量自评 — 回答后给自己打分，低了就触发反思改进")
    pdf.ln(2)
    pdf.highlight("查询延迟从1秒降到200毫秒，CPU从接近满载降到13%。")
    pdf.highlight("从「搜索引擎」升级为「推理引擎」。")

    # ═══ v0.9.0 ═══
    pdf.section_title("v0.9.0", "从一个人到一群人")
    pdf.body("之前只有一个 SOMA 在思考。这一版让它能组队——多个 Agent 各自拥有独立记忆、独立专长和独立进化路径：")
    pdf.bullet("专家分工 — 注册多个 Agent，各自专攻技术、商业、心理学等不同领域")
    pdf.bullet("自动路由 — 问题来了自动分发给最懂的那个 Agent 回答，零 LLM 参与路由")
    pdf.bullet("共识机制 — 意见不一致时投票或综合出最优解")
    pdf.bullet("独立进化 — 每个专家在自己的领域越用越强，同时分享群体经验")
    pdf.ln(2)
    pdf.highlight("从「一个人的智慧」升级为「一群人的协作」。")

    # ═══ v0.9.1 ═══
    pdf.section_title("v0.9.1", "多了一个「自知之明」")
    pdf.body("这是最微妙也最特别的一次升级。SOMA 开始察觉用户的认知模式——当你连续5轮只用同一套思维框架分析问题，它会温柔地提醒：")
    pdf.bullet("纯关键词匹配，零额外 LLM 调用，零性能开销")
    pdf.bullet("以脚注形式附加在回答末尾，不强制、不打断、不改变决策")
    pdf.bullet("默认关闭，需要的人自己打开")
    pdf.ln(2)
    pdf.highlight("SOMA 不仅能陪你思考，还能帮你看清「自己是怎么想的」。")

    # ═══ v1.0.0 ═══
    pdf.section_title("v1.0.0", "记忆有了「层次感」")
    pdf.body("这是最新、体量最大的升级。之前的记忆都是扁平的碎片，这一版让记忆有了三层递进结构：")
    pdf.bullet("L1 碎片记忆 — 一条一条的具体信息（原有机制，保持不变）")
    pdf.bullet("L2 场景块（新增）— 自动把相关碎片聚合为「场景」，比如「用户在做Python数据分析项目」")
    pdf.bullet("L3 用户画像（新增）— 从多个场景中提炼：偏好什么、擅长什么、在学什么、缺什么")
    pdf.ln(1)
    pdf.bullet("自动捕获管道 — 整个过程全自动，用户只管正常使用，SOMA 在后台默默聚合提炼")
    pdf.bullet("检索融合 — 场景和画像自动纳入记忆搜索，查得更全更准")
    pdf.bullet("向后兼容 — 所有新功能默认关闭，旧代码零改动直接运行")
    pdf.ln(2)
    pdf.highlight("从「记住你说过什么」升级为「理解你是个什么样的人」。")

    # ═══ 整体脉络 ═══
    pdf.divider()
    pdf.ln(4)
    pdf.set_font("CN", "B", 14)
    pdf.set_text_color(*C_TITLE)
    pdf.cell(0, 9, "整体脉络", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    pdf.arrow_chain(["会整理\nv0.7.0", "会推理\nv0.8.0", "会协作\nv0.9.0", "会觉察\nv0.9.1", "会分层\nv1.0.0"])

    # 演进方向
    pdf.ln(6)
    pdf.set_font("CN", "B", 10)
    pdf.set_text_color(*C_ARROW)
    pdf.cell(0, 7, "从「工具」到「伙伴」的演进方向", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    # 最终总结
    pdf.divider()
    pdf.ln(4)
    pdf.set_font("CN", "B", 12)
    pdf.set_text_color(*C_HIGHLIGHT)
    pdf.multi_cell(0, 8,
        "v0.7.0 是一个聪明的记事本，"
        "v1.0.0 是一个有层次记忆、能推理因果、"
        "会团队协作、还能察觉思维盲区的认知伙伴。", align="C")
    pdf.ln(4)

    # 脚注
    pdf.footnote("SOMA — Somatic Wisdom Architecture   ·   soma-wisdom v1.0.0   ·   github.com/sunyan999999/soma")

    # ── 输出 ──
    out = os.path.join(os.path.dirname(__file__), "..", "docs", "SOMA-版本演进总结.pdf")
    pdf.output(out)
    print(f"PDF已生成: {os.path.abspath(out)}")


if __name__ == "__main__":
    build()
