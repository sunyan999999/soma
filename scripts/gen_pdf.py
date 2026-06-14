"""Generate SOMA Introduction PDF"""
from fpdf import FPDF
import os

class P(FPDF):
    def header(self):
        if self.page_no()>1:
            self.set_font("Helvetica","I",8);self.set_text_color(150)
            self.cell(0,6,"SOMA v1.1.4",align="L");self.ln(4)
    def footer(self):
        self.set_y(-15);self.set_font("Helvetica","I",7);self.set_text_color(150)
        self.cell(0,10,f"Page {self.page_no()}/{{nb}}",align="C")
    def h1(self,t):
        self.set_font("Helvetica","B",20);self.set_text_color(30);self.ln(6)
        self.multi_cell(0,10,t)
        self.line(self.l_margin,self.get_y()+2,self.w-self.r_margin,self.get_y()+2);self.ln(8)
    def h2(self,t):
        self.set_font("Helvetica","B",13);self.set_text_color(60);self.ln(4);self.multi_cell(0,8,t);self.ln(2)
    def p(self,t):
        self.set_font("Helvetica","",10);self.set_text_color(40);self.multi_cell(0,6.5,t)
    def tbl(self,hd,rows):
        self.set_font("Helvetica","B",7.5);self.set_fill_color(40,40,40);self.set_text_color(255)
        w=[28,22,28,92]
        for i,h in enumerate(hd):self.cell(w[i],7,h,border=0,fill=True)
        self.ln()
        self.set_font("Helvetica","",7.5);self.set_text_color(40)
        for r in rows:
            for i,c in enumerate(r):self.cell(w[i],5.5,str(c)[:55],border=0)
            self.ln()

pdf=P();pdf.alias_nb_pages();pdf.set_auto_page_break(True,18);pdf.add_page()

# Cover
pdf.ln(40)
pdf.set_font("Helvetica","B",30);pdf.set_text_color(20)
pdf.cell(0,14,"SOMA",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.set_font("Helvetica","",14);pdf.set_text_color(100)
pdf.cell(0,10,"Somatic Wisdom Architecture  v1.1.4",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(8)
pdf.set_font("Helvetica","I",11)
pdf.cell(0,8,"Wisdom over Memory",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(12)
pdf.line(60,pdf.get_y(),pdf.w-60,pdf.get_y());pdf.ln(12)
pdf.set_font("Helvetica","B",11)
pdf.cell(0,8,"A Cognitive Kernel for AI Agents",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(30)
pdf.set_font("Helvetica","",9);pdf.set_text_color(140)
pdf.cell(0,7,"SOMA Project Team  |  June 2026  |  Apache 2.0",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.cell(0,7,"github.com/sunyan999999/soma  |  pypi.org/project/soma-wisdom",align="C",new_x="LMARGIN",new_y="NEXT")

# TOC
pdf.add_page();pdf.h1("Contents")
pdf.set_font("Helvetica","",10)
for it in["1. SOMA Current Capabilities & Advantages","2. Version Evolution: v0.1.0 to v1.1.4","3. Impact Analysis","   3.1 Individuals","   3.2 Families","   3.3 Teams","   3.4 Enterprises","   3.5 AI Industry","   3.6 Society"]:
    pdf.cell(0,8,it,new_x="LMARGIN",new_y="NEXT")

# Section 1
pdf.add_page();pdf.h1("1. SOMA Current Capabilities & Advantages")
pdf.p("SOMA v1.1.4 is a lightweight, pluggable cognitive framework for AI agents. It does not store more memories. Instead, it uses a reasoning network of 7 thinking laws to decompose problems BEFORE calling the LLM, upgrading the model from intuitive answering to structured thinking. 650 tests pass, semantic recall 100%, Zero-Entropy Think Tank benchmark overall score 80.5.")
pdf.ln(2)
pdf.p("For LLMs: Multi-dimensional analysis injected before each call transforms single-perspective answers into syntheses of First Principles + Systems Thinking + Contradiction Analysis + Pareto Principle + Inversion. Token overhead under 5%, answer depth improves dramatically. For Agents: Reusable decision memory, real-time cognitive bias correction (Zhongdao Engine), and auto-tuning suggestions turn agents from task-executors into systems that improve with experience.")
pdf.ln(2)
pdf.p("2,063 PyPI downloads. 291 GitHub clones (74 unique) in 2 weeks. Running in production for 30+ days with 11,000+ memories. Decompose <50ms (local, zero LLM). Deep analysis ~10s. Correction <100us/event. Three-tier memory (L1 fragments / L2 scenes / L3 profile). Three-phase bias correction (FrameAnchoringDetector / ZhongdaoEngine / MetaEvolver).")

# Section 2
pdf.add_page();pdf.h1("2. Version Evolution")
vs=[
["v0.1.0","2025-05","MVP","5 hardcoded laws + ChromaDB + keyword trigger + template synthesis"],
["v0.2.0","2025-10","Alpha","ONNX embeddings + FAISS semantic search + evolution loop + Dashboard"],
["v0.3.x","2026-04","Beta","Pluggable Hub + FTS5/WAL + MMR diversity + 30 REST endpoints + 11 LLM providers"],
["v0.4.x","2026-05","Production Audit","Data isolation (user/session/namespace) + API stability + security + 34 tests"],
["v0.5.0","2026-05","Deep Thinking","Law chaining + cognitive bias detection + complexity adaptive + combo templates"],
["v0.6.0","2026-05","Reasoning Engine","17 reasoning templates + hypothesis testing + causal extraction + trigger learning"],
["v0.7.0","2026-05","Memory Intelligence","Consolidation + Ebbinghaus forgetting + external knowledge + LLM retry"],
["v0.8.0","2026-05","Graph Reasoning","Causal chains + conflict detection + cross-domain analogy + CPU optimization"],
["v0.9.0","2026-05","Multi-Agent","Expert registry + 3-level routing + 3 consensus modes + distributed evolution"],
["v1.0.0","2026-05","5-Line Milestone","3-tier memory + deep reasoning + multi-agent + complete evolution + 511 tests"],
["v1.1.0","2026-05","Parallel Collab","Parallel dispatch (4.9x speedup) + DistributedEvolver integration + 618 tests"],
["v1.1.1","2026-05","Production Refine","L1 complexity adaptive + multi-agent route completion + embedding warmup"],
["v1.1.2","2026-05","Zhongdao Engine","Real-time bias detection + auto-correction (penalty x0.80, boost x1.15) + 639 tests"],
["v1.1.3","2026-06","Zhongdao Deepen","Configurable params + Dash viz + cross-agent convergence + persistent log + 650 tests"],
["v1.1.4","2026-06","Zhongdao Closed Loop","Effectiveness tracking + auto-tuning + trend charts + auto-archive + 650 tests"],
]
pdf.tbl(["Version","Date","Theme","Key Deliverables"],vs)

# Section 3
pdf.add_page();pdf.h1("3. Impact Analysis")
impacts=[
("3.1 Individuals","SOMA helps individuals build structured thinking habits. Facing any problem, 7 laws automatically decompose it from multiple angles. The Zhongdao Engine detects cognitive bias in real-time, preventing over-reliance on a single thinking pattern. Like carrying an interdisciplinary advisor: philosophy, systems science, economics, and evolutionary thinking always available. For developers: three CLI commands (decompose/analyze/compare) turn any technical decision into structured analysis. pip install soma-wisdom in one minute."),
("3.2 Families","SOMA's memory system can become a family wisdom repository, recording rationale, lessons, and constraints behind important decisions. Unlike passive note-taking tools, SOMA actively retrieves relevant historical decisions to prevent repeated mistakes. Three-tier memory automatically distills long-term insights from daily interactions. At Zero-Entropy Think Tank, SOMA has been used for life planning, relationship counseling, and education decisions through multi-dimensional analysis."),
("3.3 Teams","SOMA's multi-agent collaboration lets every AI assistant share the same cognitive framework. The distributed evolution mechanism aggregates, refines, and redistributes each agent's experience. One person's lesson becomes the team's wisdom. Parallel agent dispatch achieves 4.9x speedup. CodeMonitor group chat integrates six agents (admin, Claude Code, Cursor, Codex, Qoder, Reasonix) under a unified protocol for collaborative discussion and task distribution."),
("3.4 Enterprises","Three integration channels (REST API + MCP protocol + CLI) let enterprises embed SOMA into any AI workflow. Dash dashboard provides enterprise-grade observability: 5D benchmarks, correction trends, memory statistics. RBAC + audit logging meet compliance. Apache 2.0 license + zero external dependencies (ONNX local inference + SQLite) means no vendor lock-in or data leakage. Zero-Entropy Think Tank: 30+ days production, 11,000+ memories processed."),
("3.5 AI Industry","SOMA validates a core thesis: Framework First, Memory Second. While the industry pursues larger context windows and stronger RAG, SOMA proves that structured thinking before memory retrieval produces qualitative leaps. The Zhongdao Engine is the industry's first real-time AI cognitive bias correction system, detecting and auto-correcting overuse of single thinking patterns. This opens a new path for solving LLM template-answer and thinking-rigidity problems."),
("3.6 Society","SOMA's core philosophy of Wisdom over Memory carries deeper social value: in the age of information explosion, what matters is not storing more, but building better thinking frameworks. SOMA engineers Zero-Entropy Think Tank's six-year empirical goodness-wisdom system: four categories of explicitly prohibited content with a five-pillar audit standard. 2,063 downloads, bilingual documentation, GitHub Codespaces one-click demo. SOMA works to make structured thinking a public good, not a privilege."),
]
for t,te in impacts:
    pdf.h2(t);pdf.p(te);pdf.ln(2)

pdf.ln(8)
pdf.line(pdf.l_margin,pdf.get_y(),pdf.w-pdf.r_margin,pdf.get_y());pdf.ln(6)
pdf.set_font("Helvetica","I",8);pdf.set_text_color(150)
pdf.cell(0,6,"github.com/sunyan999999/soma  |  pypi.org/project/soma-wisdom",align="C")

out=r"C:\SOMA\soma-core\SOMA_Introduction_v1.1.4.pdf"
pdf.output(out)
print(f"Done: {out} ({os.path.getsize(out)/1024:.0f}KB, {pdf.pages_count}p)")
