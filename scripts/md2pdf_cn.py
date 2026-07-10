"""Convert Chinese markdown to PDF using fpdf2 + SimHei"""
from fpdf import FPDF
import os, re

FONT = r"C:\Windows\Fonts\simhei.ttf"
INPUT = r"C:\SOMA\soma-core\docs\SOMA_v2.0.4_Capabilities_CN.md"
OUTPUT = r"C:\SOMA\soma-core\docs\SOMA_v2.0.4_Capabilities_CN.pdf"

lines = open(INPUT,'r',encoding='utf-8').readlines()

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
    def h3(self,t):
        self.set_font("C","B",11);self.set_text_color(60);self.ln(3);self.multi_cell(0,8,t);self.ln(1)
    def pp(self,t):
        self.set_font("C","",10);self.set_text_color(40)
        try:
            self.multi_cell(self.w-40,7,t)
        except:
            for ch in t: self.write(7,ch);self.ln()
    def li(self,t):
        t = t.replace('"',' ').replace("'",' ').replace('`',' ').replace('(',' ').replace(')',' ')
        t = t.replace('[',' ').replace(']',' ')
        self.set_font("C","",10);self.set_text_color(40);self.cell(0,6,"  "+t,new_x="LMARGIN",new_y="NEXT")
    def code(self,t):
        t = t.replace('"',' ').replace("'",' ')
        self.set_font("C","",8.5);self.set_text_color(80);self.cell(0,5.5,"  "+t,new_x="LMARGIN",new_y="NEXT")
    def tbl(self,headers,rows):
        self.set_font("C","B",8);self.set_fill_color(40,40,40);self.set_text_color(255)
        n=len(headers);w=self.w-40
        cw=[w//n]*n
        for i,h in enumerate(headers):self.cell(cw[i],7,h,border=0,fill=True)
        self.ln()
        self.set_font("C","",8);self.set_text_color(40)
        for row in rows:
            if len(row)!=n:continue
            for i,c in enumerate(row):
                txt=str(c)[:18].replace('"',' ').replace("'",' ')
                self.cell(cw[i],5.5,txt,border=0)
            self.ln()

pdf=P();pdf.alias_nb_pages();pdf.set_auto_page_break(True,18)
pdf.add_font("C","",FONT);pdf.add_font("C","B",FONT);pdf.add_font("C","I",FONT)

# Parse and render markdown
in_code=False;in_table=False;table_rows=[];table_header=[]
for line in lines:
    line=line.rstrip('\n').rstrip('\r')
    if not line.strip():
        pdf.ln(2);continue
    if line.startswith('# '):
        pdf.add_page();pdf.h1(line[2:]);continue
    if line.startswith('## '):
        pdf.h2(line[3:]);continue
    if line.startswith('### '):
        pdf.h3(line[4:]);continue
    if line.startswith('> '):
        pdf.set_font("C","I",9);pdf.set_text_color(100);pdf.multi_cell(0,6,line[2:]);pdf.ln(2);continue
    if line.startswith('```'):
        in_code=not in_code;pdf.ln(2);continue
    if in_code:
        pdf.code(line);continue
    if line.startswith('| '):
        cells=[c.strip() for c in line.split('|')[1:-1]]
        if not table_header and all(c.startswith('-') or c.strip()=='' for c in cells):
            continue
        if not table_header:
            table_header=cells
        elif not all(c.startswith('-') for c in cells):
            table_rows.append(cells)
        continue
    if table_header:
        pdf.tbl(table_header,table_rows)
        table_header=[];table_rows=[];pdf.ln(4)
    if line.startswith('- '):
        pdf.li(line[2:]);continue
    pdf.pp(line)

pdf.ln(6)
pdf.line(pdf.l_margin,pdf.get_y(),pdf.w-pdf.r_margin,pdf.get_y());pdf.ln(6)
pdf.set_font("C","I",8);pdf.set_text_color(150)
pdf.cell(0,6,"github.com/sunyan999999/soma  |  pypi.org/project/soma-wisdom  |  Apache 2.0 License",align="C")

pdf.output(OUTPUT)
size_kb=os.path.getsize(OUTPUT)/1024
print(f"Done: {OUTPUT} ({size_kb:.0f}KB, {pdf.pages_count}p)")
