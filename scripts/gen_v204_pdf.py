"""Generate SOMA v2.0.4 Capabilities Report PDF"""
from fpdf import FPDF
import os

FONT = r"C:\Windows\Fonts\simhei.ttf"

class P(FPDF):
    def header(self):
        if self.page_no()>1:
            self.set_font("C","I",8);self.set_text_color(150)
            self.cell(0,6,"SOMA v2.0.4 Capabilities Report",align="L");self.ln(4)
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

# Cover
pdf.ln(40)
pdf.set_font("C","B",32);pdf.set_text_color(20)
pdf.cell(0,14,"SOMA",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.set_font("C","",16);pdf.set_text_color(100)
pdf.cell(0,10,"Somatic Wisdom Architecture  v2.0.4",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(4)
pdf.cell(0,10,"AI Agent Cognitive Kernel",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(12)
pdf.line(60,pdf.get_y(),pdf.w-60,pdf.get_y());pdf.ln(12)
pdf.set_font("C","B",12)
pdf.cell(0,8,"Capabilities Report / Capabilities Report",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.cell(0,8,"Benchmark Score: 92.6 (All-Time High)",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(30)
pdf.set_font("C","",9);pdf.set_text_color(140)
pdf.cell(0,7,"SOMA Project Team  |  July 2026  |  Apache 2.0",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.cell(0,7,"github.com/sunyan999999/soma",align="C",new_x="LMARGIN",new_y="NEXT")

# TOC
pdf.add_page();pdf.h1("Contents / Contents")
pdf.set_font("C","",10)
for it in["1. What is SOMA / SOMA Explained","2. v2.0.4 Core Capabilities / Core Capabilities","3. Benchmark Comparison / Benchmark Comparison","4. Impact on Zero-Entropy Think Tank / Impact Analysis","5. Technical Specifications / Tech Specs","6. Installation / Installation"]:
    pdf.cell(0,8,it,new_x="LMARGIN",new_y="NEXT")

# Section 1
pdf.add_page();pdf.h1("1. What is SOMA / SOMA Explained")
pdf.pp("SOMA is a lightweight, open-source AI cognitive engine. It does not store more memories. Instead, it uses a reasoning network of 7 thinking laws to first decompose problems from multiple dimensions before the LLM generates an answer. Core formula: Decompose -> Activate -> Reason -> Synthesize -> Evolve.")
pdf.ln(3)
pdf.pp("650 tests pass. Semantic recall rate 100%. Running in production on Zero-Entropy Think Tank with 16,935 memories at large scale. Apache 2.0 license. Zero mandatory external dependencies.")

# Section 2
pdf.add_page();pdf.h1("2. v2.0.4 Core Capabilities / Core Capabilities")

pdf.h2("2.1 Autonomous Cognitive Loop / Autonomous Cognitive Loop")
pdf.pp("SOMA now has full autonomous reasoning capability, completing analysis without waiting for an external LLM:")
pdf.li("soma.reason() — Basic reasoning: 7-law decomposition + memory activation, zero LLM, under 500ms")
pdf.li("soma.reason_deep() — Multi-round self-dialogue + devil's advocate + synthesis correction")
pdf.li("soma.loop() — Full 5-phase cycle: Perceive->Reason->Act->Feedback->Evolve")
pdf.li("soma.loop_multi() — Multi-agent loops + cross-validation + consensus evolution")

pdf.h2("2.2 Intelligent LLM Routing / Smart LLM Routing")
pdf.pp("reason(use_llm='auto') default smart mode, auto-decides based on problem complexity:")
pdf.li("L1 simple questions -> Pure local reasoning, zero token, under 500ms")
pdf.li("L2 medium questions -> Local reasoning + template synthesis, zero extra token")
pdf.li("L3 complex questions -> LLM-enhanced pre-analysis, quality significantly improved")

pdf.h2("2.3 chat() Pre-Analysis Injection / Pre-Analysis")
pdf.pp("For L2+ complexity chat problems, SOMA automatically injects multi-dimensional pre-analysis as thinking material before the LLM generates its answer. API response includes new pre_analysis field with dimension list and analysis text for frontend display.")

pdf.h2("2.4 Seven Thinking Laws / 7 Thinking Laws")
laws=[["1. First Principles","Return to fundamentals"],["2. Systems Thinking","Map interconnections"],["3. Contradiction Analysis","Find core tensions"],["4. Pareto Principle","Focus on critical few"],["5. Inversion","Reason backwards from failure"],["6. Analogical Reasoning","Find cross-domain patterns"],["7. Evolutionary Lens","Track what adapts and evolves"]]
for n,d in laws:
    pdf.cell(0,6.5,f"{n} — {d}",new_x="LMARGIN",new_y="NEXT")
pdf.ln(3)

pdf.h2("2.5 Three-Tier Memory / 3-Tier Memory")
pdf.li("L1 Episodic Fragments — Raw conversations, decisions, trades")
pdf.li("L2 Scene Blocks — Auto-aggregated thematic contexts")
pdf.li("L3 User Profile — Long-term extracted traits (preferences, skills, risk tolerance)")

pdf.h2("2.6 Zhongdao Engine / Zhongdao Engine")
pdf.pp("Session-internal real-time thinking bias detection. When a single law usage rate exceeds threshold, auto-corrects: penalizes overused patterns, boosts neglected patterns. Prevents AI from cognitive rigidity.")

# Section 3
pdf.add_page();pdf.h1("3. Benchmark Comparison / Benchmark Comparison")
pdf.pp("Tested on Zero-Entropy Think Tank with 16,935 memories (large scale). Five-version comparison:")
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
pdf.pp("Key Milestones / Key Milestones:")
pdf.li("Wisdom: 75.9 -> 83.7 (+7.8) — Pre-analysis injection strategy proven highly effective")
pdf.li("Memory: 74.4 -> 94.7 (+20.3) — Three-tier memory + FAISS HNSW index optimization")
pdf.li("Evolution: 76.4 -> 96.3 (+19.9) — Adaptive thresholds + weighted consensus + quality scoring")
pdf.li("Overall: 92.6 — All-time high across all versions (v0.1.0 to v2.0.4)")

# Section 4
pdf.add_page();pdf.h1("4. Impact on Zero-Entropy Think Tank / Impact Analysis")
pdf.h2("4.1 Twin Service Quality / Twin Service Quality")
pdf.pp("Zero-Entropy Think Tank's 6 active twins benefit from v2.0.4 pre-analysis injection:")
pdf.li("L3 complex questions use LLM-enhanced pre-analysis, answer depth significantly improved")
pdf.li("Chat API returns soma_enhancement field for frontend SOMA Deep Analysis badge")
pdf.li("1,075+ weekly sessions, 52 active users receive higher quality multi-dimensional analysis")

pdf.h2("4.2 Memory & Evolution / Memory & Evolution")
pdf.li("94.7 memory score at 16,935 memories — efficient retrieval at large scale")
pdf.li("Evolution engine with adaptive thresholds — more data enables more precise evolution")
pdf.li("FAISS HNSW index batch-save optimization, reduced disk I/O")

pdf.h2("4.3 Autonomous Reasoning / Autonomous Reasoning")
pdf.li("Simple questions: pure local reasoning, zero token cost, under 500ms")
pdf.li("Complex questions: auto LLM enhancement, wisdom score increased by 7.8 points")
pdf.li("Multi-agent collaborative reasoning (loop_multi) — experts analyze independently + cross-validate")

pdf.h2("4.4 User-Perceptible Changes / User-Perceptible Changes")
pdf.li("Chat responses have more depth — multi-dimensional analysis behind every answer")
pdf.li("Frontend can display analysis dimensions and thinking laws — making intelligence visible")
pdf.li("Twin response quality consistency improved — Zhongdao Engine continuously monitors bias")

# Section 5
pdf.add_page();pdf.h1("5. Technical Specifications / Technical Specifications")
specs=[["Full tests:","650 passed"],["Semantic recall:","100%"],["Local reasoning:","under 500ms"],["LLM-enhanced:","~2-3s"],["Zero extra token:","L1/L2 available"],["Offline capable:","Yes (reason/reason_deep)"],["Python:","3.10+"],["License:","Apache 2.0"],["Memory scale:","16,935 (large)"]]
for k,v in specs:
    pdf.cell(0,7,f"  {k} {v}",new_x="LMARGIN",new_y="NEXT")
pdf.ln(4)

pdf.h2("Weekly Production Data (W27) / Weekly Data (W27)")
wdata=[["Total sessions:","1,075"],["Active users:","52"],["Active twins:","6 (top: Private Destiny Advisor 552)"]]
for k,v in wdata:
    pdf.cell(0,7,f"  {k} {v}",new_x="LMARGIN",new_y="NEXT")

# Section 6
pdf.ln(8);pdf.h1("6. Installation / Installation")
pdf.pp('pip install --upgrade soma-wisdom')
pdf.ln(4)
pdf.pp("pip install --upgrade soma-wisdom")
pdf.ln(6)

pdf.line(pdf.l_margin,pdf.get_y(),pdf.w-pdf.r_margin,pdf.get_y());pdf.ln(6)
pdf.set_font("C","I",8);pdf.set_text_color(150)
pdf.cell(0,6,"github.com/sunyan999999/soma  |  pypi.org/project/soma-wisdom  |  Apache 2.0",align="C")

out=r"C:\SOMA\soma-core\docs\SOMA_v2.0.4_Capabilities_CN.pdf"
pdf.output(out)
size_kb = os.path.getsize(out)/1024
print(f"Done: {out} ({size_kb:.0f}KB, {pdf.pages_count}p)")
