"""Generate SOMA v2.0.4 Capabilities Report PDF - Chinese"""
from fpdf import FPDF
import os, json

FONT = r"C:\Windows\Fonts\simhei.ttf"
D = json.load(open(os.path.join(os.path.dirname(__file__), 'cn_data.json'), 'r', encoding='utf-8')) if os.path.exists(os.path.join(os.path.dirname(__file__), 'cn_data.json')) else {}

class P(FPDF):
    def header(self):
        if self.page_no()>1:
            self.set_font("C","I",8);self.set_text_color(150)
            self.cell(0,6,"SOMA v2.0.4 AI Agent Cognitive Kernel",align="L");self.ln(4)
    def footer(self):
        self.set_y(-15);self.set_font("C","I",7);self.set_text_color(150)
        self.cell(0,10,f"Page {self.page_no()}/{{nb}}",align="C")
    def h1(self,t):
        self.set_font("C","B",22);self.set_text_color(30);self.ln(6)
        self.multi_cell(0,12,t)
        self.line(self.l_margin,self.get_y()+2,self.w-self.r_margin,self.get_y()+2);self.ln(8)
    def h2(self,t):
        self.set_font("C","B",14);self.set_text_color(60);self.ln(4);self.multi_cell(0,9,t);self.ln(2)
    def pp(self,t):
        self.set_font("C","",10);self.set_text_color(40);self.multi_cell(0,7,t)
    def tbl(self,hd,rows):
        self.set_font("C","B",8);self.set_fill_color(40,40,40);self.set_text_color(255)
        w=[28,22,22,22,22,24,24]
        for i,h in enumerate(hd):self.cell(w[i],7,h,border=0,fill=True)
        self.ln()
        self.set_font("C","",8);self.set_text_color(40)
        for r in rows:
            for i,c in enumerate(r):self.cell(w[i],5.5,str(c)[:20],border=0)
            self.ln()
    def li(self,t):
        self.set_font("C","",10);self.set_text_color(40);self.cell(0,6,"  "+t,new_x="LMARGIN",new_y="NEXT")

pdf=P();pdf.alias_nb_pages();pdf.set_auto_page_break(True,18)
pdf.add_font("C","",FONT);pdf.add_font("C","B",FONT);pdf.add_font("C","I",FONT)
pdf.add_page()

# === Cover ===
pdf.ln(35)
pdf.set_font("C","B",34);pdf.set_text_color(20)
pdf.cell(0,14,"SOMA",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.set_font("C","",16);pdf.set_text_color(100)
pdf.cell(0,10,"Somatic Wisdom Architecture  v2.0.4",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(4)
pdf.cell(0,10,"AI Agent Cognitive Kernel",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(12)
pdf.line(60,pdf.get_y(),pdf.w-60,pdf.get_y());pdf.ln(12)
pdf.set_font("C","B",13)
pdf.cell(0,8,"SOMA v2.0.4 Capabilities Report",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.cell(0,8,"Benchmark 92.6 — All-Time High",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(30)
pdf.set_font("C","",9);pdf.set_text_color(140)
pdf.cell(0,7,"SOMA Project Team  |  2026 Nian 7 Yue  |  Apache 2.0 License",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.cell(0,7,"github.com/sunyan999999/soma  |  pypi.org/project/soma-wisdom",align="C",new_x="LMARGIN",new_y="NEXT")

# === TOC ===
pdf.add_page();pdf.h1("Mu Lu / Contents")
pdf.set_font("C","",10)
for it in["1. SOMA v2.0.4 Overview","2. Core Capabilities: Six Major Systems","3. Benchmark Comparison Across Five Versions","4. Impact on Zero-Entropy Think Tank","5. Technical Specifications","6. Installation and Usage"]:
    pdf.cell(0,8,it,new_x="LMARGIN",new_y="NEXT")

# === Section 1 ===
pdf.add_page();pdf.h1("1. SOMA v2.0.4 Overview")
pdf.pp("SOMA is a lightweight, open-source AI cognitive engine. Its core philosophy is Framework First, Memory Second. It uses 7 thinking laws to decompose problems from multiple dimensions before calling the LLM. The result: large models shift from intuitive quick-answering to structured deep thinking. v2.0.4 achieved a benchmark score of 92.6, the highest across all versions.")
pdf.ln(3)
pdf.pp("650 tests all pass. Semantic recall rate 100 percent. Running in production on Zero-Entropy Think Tank with 16,935 memories at large scale, 1,075 weekly sessions, 52 active users, 6 active twins. Apache 2.0 license. Zero mandatory external dependencies.")

# === Section 2 ===
pdf.add_page();pdf.h1("2. Core Capabilities: Six Major Systems")

pdf.h2("2.1 Autonomous Cognitive Loop")
pdf.pp("SOMA can now complete full autonomous reasoning without an external LLM. Five-phase cycle: Perceive to Reason to Act to Feedback to Evolve.")
pdf.li("soma.reason(): 7-law decomposition plus memory activation, zero LLM, under 500ms")
pdf.li("soma.reason_deep(): Multi-round self-dialogue plus devil advocate plus synthesis correction")
pdf.li("soma.loop(): Full 5-phase cycle, auto-record insights and trigger evolution")
pdf.li("soma.loop_multi(): Multiple agents independently loop plus cross-validation plus consensus")

pdf.h2("2.2 Intelligent LLM Routing")
pdf.pp("Default smart mode automatically decides LLM usage based on problem complexity.")
pdf.li("L1 easy problems: pure local reasoning, zero token cost, under 500ms")
pdf.li("L2 medium problems: local reasoning plus template synthesis, zero extra token")
pdf.li("L3 complex problems: LLM-enhanced pre-analysis, quality significantly improved")

pdf.h2("2.3 Chat Pre-Analysis Injection")
pdf.pp("For L2-plus complexity chat problems, SOMA automatically injects multi-dimensional pre-analysis as thinking material before the LLM answer. The API response now includes a pre_analysis field with dimension lists and analysis text for frontend display. Users can see which thinking laws were applied and how many dimensions were analyzed.")

pdf.h2("2.4 Seven Thinking Laws")
laws=[["1 First Principles","Return to fundamentals and basic elements"],
["2 Systems Thinking","Identify interconnections and feedback loops"],
["3 Contradiction Analysis","Reveal hidden tensions and core conflicts"],
["4 Pareto Principle","Focus on the critical few factors that matter most"],
["5 Inversion","Think backwards from failure to avoid blind spots"],
["6 Analogical Reasoning","Bridge knowledge across different domains"],
["7 Evolutionary Lens","Track what adapts and what becomes obsolete"]]
for n,d in laws:
    pdf.cell(0,6.5,f"{n} — {d}",new_x="LMARGIN",new_y="NEXT")
pdf.ln(3)

pdf.h2("2.5 Three-Tier Memory System")
pdf.li("L1 Episodic Fragments: raw conversations, decisions, trading records")
pdf.li("L2 Scene Blocks: auto-aggregated thematic contexts from daily interactions")
pdf.li("L3 User Profile: long-term extracted traits, preferences, and risk tolerance")

pdf.h2("2.6 Zhongdao Engine")
pdf.pp("Session-internal real-time thinking bias detection and correction. When any single thinking law exceeds the usage threshold, it automatically penalizes overused patterns and boosts neglected complementary patterns. Prevents the AI from cognitive rigidity and template-answer syndrome.")

# === Section 3 ===
pdf.add_page();pdf.h1("3. Benchmark Comparison Across Five Versions")
pdf.pp("Tested on Zero-Entropy Think Tank with 16,935 memories at large scale. Five versions compared:")
pdf.ln(3)
hd=["Metric","v1.1.8","v1.1.9","v2.0.0","v2.0.2","v2.0.4","Gain"]
rows=[
["Overall","78.2","80.5","80.2","80.5","92.6","+14.4"],
["Memory","74.4","78.0","78.8","78.0","94.7","+20.3"],
["Wisdom","72.6","75.4","74.5","75.9","83.7","+11.1"],
["Evolution","76.4","77.8","76.7","77.3","96.3","+19.9"],
["Scalability","100","100","100","100","100","0"],
]
pdf.tbl(hd,rows)
pdf.ln(6)
pdf.pp("Key Milestones:")
pdf.li("Wisdom: 75.9 to 83.7, up 7.8 points. Pre-analysis injection strategy proven highly effective")
pdf.li("Memory: 74.4 to 94.7, up 20.3 points. Three-tier memory plus FAISS HNSW optimization")
pdf.li("Evolution: 76.4 to 96.3, up 19.9 points. Adaptive thresholds plus weighted consensus")
pdf.li("Overall 92.6 is the all-time high across 17 versions from v0.1.0 to v2.0.4")

# === Section 4 ===
pdf.add_page();pdf.h1("4. Impact on Zero-Entropy Think Tank")
pdf.h2("4.1 Twin Service Quality")
pdf.pp("Zero-Entropy Think Tank has 6 active twins. All benefit from v2.0.4 pre-analysis injection.")
pdf.li("L3 complex questions use LLM-enhanced pre-analysis, answer depth significantly improved")
pdf.li("Chat API returns soma_enhancement field for frontend display of deep analysis badge")
pdf.li("1,075 weekly sessions across 52 active users receive higher quality multi-dimensional analysis")

pdf.h2("4.2 Memory and Evolution")
pdf.li("94.7 memory score at 16,935 memories with efficient retrieval at large scale")
pdf.li("Evolution engine with adaptive thresholds: more data enables more precise weight tuning")
pdf.li("FAISS HNSW index batch-save optimization significantly reduces disk I/O")

pdf.h2("4.3 User-Perceptible Changes")
pdf.li("Chat responses show more depth with visible multi-dimensional analysis")
pdf.li("Frontend displays analysis dimensions and thinking laws, making intelligence visible")
pdf.li("Twin response quality consistency improved through continuous Zhongdao monitoring")
pdf.li("Simple questions answered instantly via pure local reasoning at zero token cost")

# === Section 5 ===
pdf.add_page();pdf.h1("5. Technical Specifications")
specs=[["Full tests","650 passed"],["Semantic recall","100 percent"],["Local reasoning latency","under 500ms"],
["LLM-enhanced latency","approx 2 to 3 seconds"],["Zero extra token mode","L1 and L2 available"],
["Offline capable","Yes via reason and reason_deep"],["Python","3.10 or higher"],["License","Apache 2.0"],
["Memory scale","16,935 at large tier"]]
for k,v in specs:
    pdf.cell(0,7,f"  {k}: {v}",new_x="LMARGIN",new_y="NEXT")
pdf.ln(4)

pdf.h2("Weekly Production Data (Week 27)")
wdata=[["Total sessions","1,075"],["Active users","52"],["Active twins","6"],
["Top twin","Private Destiny Advisor with 552 sessions"],["Average response","approx 22 seconds"]]
for k,v in wdata:
    pdf.cell(0,7,f"  {k}: {v}",new_x="LMARGIN",new_y="NEXT")
pdf.ln(4)

pdf.h2("Version History Highlights")
hist=[["v1.1.7","2026-06-17","v1.1.4 baseline rebuild, FAISS HNSW, multi-agent, 83.4 pts"],
["v1.1.9","2026-06-19","soma.reason() zero-LLM autonomous reasoning"],
["v2.0.0","2026-06-26","Autonomous cognitive loop: perceive plus loop plus reason_deep"],
["v2.0.2","2026-07-03","Smart LLM routing plus execute plus FAISS batch save"],
["v2.0.4","2026-07-07","Wisdom depth enhancement: L3 LLM pre-analysis plus pre_analysis field"]]
pdf.set_font("C","",9)
for v,d,s in hist:
    pdf.cell(0,6,f"  {v} ({d}): {s}",new_x="LMARGIN",new_y="NEXT")

# === Section 6 ===
pdf.ln(8);pdf.h1("6. Installation and Usage")

pdf.pp("pip install --upgrade soma-wisdom")
pdf.ln(5)

pdf.line(pdf.l_margin,pdf.get_y(),pdf.w-pdf.r_margin,pdf.get_y());pdf.ln(6)
pdf.set_font("C","I",8);pdf.set_text_color(150)
pdf.cell(0,6,"github.com/sunyan999999/soma  |  pypi.org/project/soma-wisdom  |  Apache 2.0 License",align="C")

out=r"C:\SOMA\soma-core\docs\SOMA_v2.0.4_Capabilities_CN.pdf"
pdf.output(out)
size_kb=os.path.getsize(out)/1024
print(f"Done: {out} ({size_kb:.0f}KB, {pdf.pages_count}p)")
