import json, os
from fpdf import FPDF

FONT = r"C:\Windows\Fonts\simhei.ttf"
d = json.load(open(os.path.join(os.path.dirname(__file__), 'cn_data.json'), 'r', encoding='utf-8'))

class P(FPDF):
    def header(self):
        if self.page_no()>1:
            self.set_font("C","I",8);self.set_text_color(150)
            self.cell(0,6,"SOMA v1.1.4 -- AI Agent Cognitive Kernel",align="L");self.ln(4)
    def footer(self):
        self.set_y(-15);self.set_font("C","I",7);self.set_text_color(150)
        self.cell(0,10,f"Page {self.page_no()}/{{nb}}",align="C")
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

# Cover
pdf.ln(40)
pdf.set_font("C","B",30);pdf.set_text_color(20)
pdf.cell(0,14,d['cover_title'],align="C",new_x="LMARGIN",new_y="NEXT")
pdf.set_font("C","",14);pdf.set_text_color(100)
pdf.cell(0,10,d['cover_sub'],align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(4)
pdf.cell(0,10,d['cover_tag'],align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(8)
pdf.set_font("C","I",12)
pdf.cell(0,8,d['cover_motto'],align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(12)
pdf.line(60,pdf.get_y(),pdf.w-60,pdf.get_y());pdf.ln(12)
pdf.set_font("C","B",11)
pdf.cell(0,8,d['cover_desc'],align="C",new_x="LMARGIN",new_y="NEXT")
pdf.ln(30)
pdf.set_font("C","",9);pdf.set_text_color(140)
pdf.cell(0,7,"SOMA Project Team  |  2026 Nian 6 Yue  |  Apache 2.0 License",align="C",new_x="LMARGIN",new_y="NEXT")
pdf.cell(0,7,"github.com/sunyan999999/soma  |  pypi.org/project/soma-wisdom",align="C",new_x="LMARGIN",new_y="NEXT")

# TOC
pdf.add_page();pdf.h1("Mu Lu")
pdf.set_font("C","",10)
for it in d['toc']:pdf.cell(0,8,it,new_x="LMARGIN",new_y="NEXT")

# Section 1
pdf.add_page();pdf.h1(d['s1_title'])
for k in ['s1_p1','s1_p2','s1_p3','s1_p4','s1_p5']:
    pdf.pp(d[k]);pdf.ln(3)

# Section 2
pdf.add_page();pdf.h1(d['s2_title'])
pdf.tbl(["Ban Ben","Ri Qi","Zhu Ti","He Xin Jiao Fu"],d['versions'])

# Section 3
pdf.add_page();pdf.h1(d['s3_title'])
for t,te in d['impacts']:
    pdf.h2(t);pdf.pp(te);pdf.ln(2)

pdf.ln(8)
pdf.line(pdf.l_margin,pdf.get_y(),pdf.w-pdf.r_margin,pdf.get_y());pdf.ln(6)
pdf.set_font("C","I",8);pdf.set_text_color(150)
pdf.cell(0,6,"github.com/sunyan999999/soma  |  pypi.org/project/soma-wisdom  |  Apache 2.0",align="C")

out=r"C:\SOMA\soma-core\SOMA_Introduction_v1.1.4_CN.pdf"
pdf.output(out)
print(f"Done: {out} ({os.path.getsize(out)/1024:.0f}KB, {pdf.pages_count}p)")
