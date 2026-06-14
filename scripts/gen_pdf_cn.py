# -*- coding: utf-8 -*-
"""SOMA Introduction PDF - Chinese"""
from fpdf import FPDF
import os

FONT = r"C:\Windows\Fonts\simhei.ttf"

class P(FPDF):
    def header(self):
        if self.page_no()>1:
            self.set_font("C","I",8);self.set_text_color(150)
            self.cell(0,6,"SOMA v1.1.4  AI Agent    ",align="L");self.ln(4)
    def footer(self):
        self.set_y(-15);self.set_font("C","I",7);self.set_text_color(150)
        self.cell(0,10,f"  {self.page_no()} / {{nb}}",align="C")
    def h1(self,t):
        self.set_font("C","B",20);self.set_text_color(30);self.ln(6)
        self.multi_cell(0,12,t)
        self.line(self.l_margin,self.get_y()+2,self.w-self.r_margin,self.get_y()+2);self.ln(8)
    def h2(self,t):
        self.set_font("C","B",13);self.set_text_color(60);self.ln(4);self.multi_cell(0,9,t);self.ln(2)
    def pp(self,t):
        self.set_font("C","",10);self.set_text_color(40);self.multi_cell(0,7,t)
    def tbl(self,hd,rows):
        self.set_font("C","B",7.5);self.set_fill_color(40,40,40);self.set_text_color(255)
        w=[26,24,30,90]
        for i,h in enumerate(hd):self.cell(w[i],7,h,border=0,fill=True)
        self.ln()
        self.set_font("C","",7.5);self.set_text_color(40)
        for r in rows:
            for i,c in enumerate(r):self.cell(w[i],5.5,str(c)[:70],border=0)
            self.ln()

pdf=P();pdf.alias_nb_pages();pdf.set_auto_page_break(True,18)
pdf.add_font("C","",FONT);pdf.add_font("C","B",FONT);pdf.add_font("C","I",FONT)
pdf.add_page()

# === Cover ===
pdf.ln(40)
pdf.set_font("C","B",30);pdf.set_text_color(20)
pdf.cell(0,14,"SOMA",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.set_font("C","",14);pdf.set_text_color(100)
pdf.cell(0,10,"Somatic Wisdom Architecture  v1.1.4",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(4)
pdf.cell(0,10,"AI Agent    ",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(8)
pdf.set_font("C","I",12)
pdf.cell(0,8,"Wisdom over Memory --     ",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(12)
pdf.line(60,pdf.get_y(),pdf.w-60,pdf.get_y());pdf.ln(12)
pdf.set_font("C","B",11)
pdf.cell(0,8,"    ,    ,    ,  ",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(4)
pdf.cell(0,8,"     --      ",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(30)
pdf.set_font("C","",9);pdf.set_text_color(140)
pdf.cell(0,7,"SOMA     | 2026  6  | Apache 2.0 License",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.cell(0,7,"github.com/sunyan999999/soma  |  pypi.org/project/soma-wisdom",align="C",new_x="LMARGIN",new_y="NEXT")

# === TOC ===
pdf.add_page();pdf.h1("  ")
pdf.set_font("C","",10)
for it in[
    "1. SOMA        ",
    "2.      : v0.1.0 -> v1.1.4",
    "3.     ",
    "   3.1    ",
    "   3.2    ",
    "   3.3    ",
    "   3.4    ",
    "   3.5  AI   ",
    "   3.6    ",
]:
    pdf.cell(0,8,it,new_x="LMARGIN",new_y="NEXT")

# === Section 1 ===
pdf.add_page();pdf.h1("1. SOMA        ")
pdf.pp(
    "SOMA v1.1.4          AI Agent    (Cognitive Kernel)。       Framework First --     。 LLM         ，  7              。  ：         ，          。"
)
pdf.ln(2)
pdf.pp(
    "650      。   100%。       (Zero-Entropy Think Tank)     80.5 "
    "(  79.7，   76.2，   75.0，   100.0)。PyPI     2,063 。GitHub      291  (74    )。       30  ，  11,000   。"
)
pdf.ln(3)
pdf.pp(
    "    (LLM)   ：SOMA      LLM   ，        "
    "     ：     (     ) +     (    ) + "
    "     (    ) +     (    ) +     (     )。"
    "    token    5%，        。        ，  50ms，   LLM  。"
)
pdf.ln(3)
pdf.pp(
    "     (Agent)   ：SOMA         (        )、"
    "        (Zhongdao Engine --        40%  ，"
    "            )、       。Agent       ，       。"
    "    ：    4.9x  ，5       。    ：REST API + MCP   + CLI    。"
    "         。"
)
pdf.ln(3)
pdf.pp(
    "    ：   <50ms (    ) /    ~10s (  LLM) /    <100us。"
    "    ：L1     / L2     (    ) / L3     (    )。"
    "    ：FrameAnchoringDetector (   ) + ZhongdaoEngine (   ) + "
    "MetaEvolver (    )。7     。17    。3     (  /  /  )。"
    "11  LLM      。      。     (Windows/Linux/macOS)。"
)

# === Section 2 ===
pdf.add_page();pdf.h1("2.      : v0.1.0 -> v1.1.4")
vs=[
["v0.1.0","2025-05","MVP","5      + ChromaDB +      +    "],
["v0.2.0","2025-10","Alpha","ONNX    + FAISS     +     + Dashboard + MkDocs"],
["v0.3.x","2026-04","Beta","   Hub + FTS5/WAL + MMR    + 30 REST + 11  LLM  "],
["v0.4.x","2026-05","    ","    (user/session/namespace) + API    +     + 34   "],
["v0.5.0","2026-05","    ","      +      +      +      "],
["v0.6.0","2026-05","    ","17     +      +      +       "],
["v0.7.0","2026-05","    ","     +        +     + LLM    "],
["v0.8.0","2026-05","    ","     +      +      +      + CPU  "],
["v0.9.0","2026-05","    ","     + 3    + 3     +      +      "],
["v1.0.0","2026-05","    ","     +     +    +       + 511   "],
["v1.1.0","2026-05","    ","      (4.9x  ) + DistributedEvolver   + 618   "],
["v1.1.1","2026-05","    ","L1       +       +      "],
["v1.1.2","2026-05","    ","        +      (  0.80，  1.15) + 639   "],
["v1.1.3","2026-06","    ","     + Dash   +       +      + 650   "],
["v1.1.4","2026-06","    ","     +      + Dash    +      + 650   "],
]
pdf.tbl(["  ","  ","  ","    "],vs)

# === Section 3 ===
pdf.add_page();pdf.h1("3.     / Impact Analysis")
impacts=[
("3.1    / Individuals",
 "SOMA        。       ，7          ，"
 "        ，         。"
 "            ，          。"
 "           ：    、    、    、         。"
 "    ，   CLI   (decompose/analyze/compare)        "
 "         。pip install soma-wisdom      。"
 "            。"),
("3.2    / Families",
 "SOMA           ，         、"
 "     。       ，SOMA          "
 "       。       (   ->   ->   )"
 "            。      ，SOMA        "
 "    、       ，             "
 "        。"),
("3.3    / Teams",
 "SOMA           AI           。"
 "                 、   、  -- "
 "           。      4.9x   ，5       。"
 "CodeMonitor      admin、Claude Code、Cursor、Codex、Qoder、Reasonix "
 "            、      、     。       。"),
("3.4    / Enterprises",
 "     (REST API + MCP   + CLI)          AI      SOMA     。"
 "Dash       :     、    、    、Agent    。"
 "RBAC      +         。"
 "Apache 2.0     +      (ONNX     + SQLite  )"
 "             。    : 30+    ，11,000+   。"
 "11  LLM        。CI/CD        。"),
("3.5  AI   / AI Industry",
 "SOMA       : Framework First, Memory Second。"
 "   AI              (RAG)，"
 "SOMA  :               。"
 "         AI         -- "
 "               40% (  5   )，"
 "           (  0.80)       (  1.15,    2  )。"
 "        AI        。SOMA      、     ，"
 "     LLM    。"),
("3.6    / Society",
 "SOMA      Wisdom over Memory       :     ，"
 "       ，        。"
 "SOMA                :       "
 "(    、     、     、     )，"
 "     (   、   、   、   、   )"
 "        。"
 "2,063     、      (    )、GitHub Codespaces     -- "
 "SOMA                ，       。"),
]
for t,te in impacts:
    pdf.h2(t);pdf.pp(te);pdf.ln(2)

pdf.ln(8)
pdf.line(pdf.l_margin,pdf.get_y(),pdf.w-pdf.r_margin,pdf.get_y());pdf.ln(6)
pdf.set_font("C","I",8);pdf.set_text_color(150)
pdf.cell(0,6,"github.com/sunyan999999/soma  |  pypi.org/project/soma-wisdom  |  Apache 2.0",align="C")

out=r"C:\SOMA\soma-core\SOMA_Introduction_v1.1.4_CN.pdf"
pdf.output(out)
print(f"Done: {out} ({os.path.getsize(out)/1024:.0f}KB, {pdf.pages_count}p)")
