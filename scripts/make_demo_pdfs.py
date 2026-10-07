"""Render original teaching evidence verbatim; never represent it as published research."""
import json
import unicodedata
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
import argparse

parser=argparse.ArgumentParser()
parser.add_argument('--font', default='C:/Windows/Fonts/simhei.ttf', help='Chinese TTF available on the authoring machine; font is embedded as PDF subsets')
args=parser.parse_args()
pdfmetrics.registerFont(TTFont('Teaching',args.font))
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'public/demo.json').read_text(encoding='utf-8'))
output=root/'public/demo-pdfs';output.mkdir(exist_ok=True)
style=ParagraphStyle('body',fontName='Teaching',fontSize=12,leading=21,textColor=HexColor('#223747'))
heading=ParagraphStyle('heading',parent=style,fontSize=18,leading=28)
for paper in data['papers']:
    pdf=Canvas(str(output/(paper['id']+'.pdf')),pagesize=(595,842),invariant=1)
    pdf.setTitle(paper['metadata']['title']+' - Original Teaching Document')
    pdf.setAuthor('PaperReview-Agent Teaching Team')
    for number,evidence in enumerate(paper['evidence'],1):
        evidence['page']=number
        pdf.setFillColor(HexColor('#17666b'));pdf.rect(0,810,595,32,fill=1,stroke=0)
        pdf.setFillColor(HexColor('#ffffff'));pdf.setFont('Teaching',11)
        pdf.drawString(42,820,'研脉 | 原创教学文档 - 非已发表论文')
        title=Paragraph(escape(paper['metadata']['title']),heading);_,h=title.wrap(510,120);title.drawOn(pdf,42,765-h)
        section=Paragraph(escape(evidence['section']),style);_,sh=section.wrap(510,100);section.drawOn(pdf,42,735-h-sh)
        body=Paragraph(escape(evidence['text']).replace('\n','<br/>'),style);_,bh=body.wrap(510,600)
        top=690-h-sh
        assert bh<top-100, (paper['id'],number,bh)
        body.drawOn(pdf,42,top-bh)
        node=next((n for n in paper['theory']['nodes'] if evidence['id'] in n['evidence_ids']),None)
        if node:
            note=Paragraph('中文导读：'+escape(unicodedata.normalize('NFKC',node['statement']).replace('⊆',' 包含于 ').replace('∉',' 不属于 ').replace('−','-')),style);_,nh=note.wrap(510,200);note.drawOn(pdf,42,top-bh-45-nh)
            assert top-bh-45-nh>75
        pdf.setFont('Teaching',9);pdf.setFillColor(HexColor('#617887'))
        pdf.drawString(42,45,'仅用于功能演示与学习；不代表对应研究方法的真实实验效果。')
        pdf.drawRightString(553,45,f'{number} / {len(paper["evidence"])}')
        pdf.showPage()
    pdf.save()
(root/'public/demo.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print('Generated five teaching PDFs with exact evidence page mappings.')
