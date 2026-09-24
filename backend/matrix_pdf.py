"""Compact comparison overview followed by complete, flowing two-column details."""
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, NextPageTemplate, PageBreak, Paragraph, Spacer, LongTable, TableStyle
from .tutor_pdf import FONT, register_font, paragraph_text


def matrix_pdf(papers, demo=False, stale=False):
    register_font()
    output=io.BytesIO()
    size=landscape(A4)
    width=size[0]-64
    body=ParagraphStyle('cell',fontName=FONT,fontSize=9,leading=14,wordWrap='CJK',spaceAfter=5,splitLongWords=True)
    title=ParagraphStyle('title',parent=body,fontSize=17,leading=24,spaceAfter=10,keepWithNext=True)
    head=ParagraphStyle('head',parent=body,textColor=colors.white,fontSize=10)
    section=ParagraphStyle('section',parent=body,fontSize=11,leading=16,textColor=colors.HexColor('#17666b'),spaceBefore=9,spaceAfter=6,keepWithNext=True)
    paper_heading=ParagraphStyle('paper',parent=section,fontSize=12,leading=18,spaceBefore=12)
    def para(text,style=body):
        return Paragraph('<br/>'.join(paragraph_text(line) for line in str(text).splitlines()),style)
    def excerpt(text,limit=170):
        text=' '.join(str(text).split())
        return text if len(text)<=limit else text[:limit]+'…'
    def values(p,key):
        return [c['text'] for c in p['extraction'].get(key,[])]
    def evaluations(p):
        return [' · '.join(str(v) for v in [e.get('dataset'),e.get('metric'),e.get('value'),e.get('setting')] if v) for e in p['extraction'].get('evaluations',[])]
    def preview(items,empty):
        # Deterministic excerpts, never AI summaries or replacements for full claims.
        return para(excerpt('；'.join(items[:2])) if items else empty)
    rows=[[para(x,head) for x in ['论文 / 方法','核心方法','方法优势','作者原文局限','数据集 / 指标']]]
    for index,p in enumerate(papers,1):
        metadata=p['metadata'];extraction=p['extraction']
        info=[para(f'{index:02d} · '+excerpt(metadata['title'],110)),para(str(metadata.get('year') or '未知年份')),para(excerpt(extraction.get('method_name') or '',50))]
        rows.append([info,preview(values(p,'methods'),'未找到明确陈述'),preview(values(p,'advantages'),'未找到明确陈述'),preview(values(p,'limitations'),'未找到明确陈述'),preview(evaluations(p),'未抽取到')])
    table=LongTable(rows,colWidths=[width*f for f in [.20,.23,.19,.20,.18]],repeatRows=1,splitByRow=1,splitInRow=1,hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#17666b')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.4,colors.HexColor('#cedadd')),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f5f8f8')])]))
    story=[para('多论文对比矩阵',title),para(f'共 {len(papers)} 篇论文 · 当前筛选范围'),para('矩阵为每项前两条内容的节选；全部方法、优势、局限与指标见后附完整明细。')]
    if demo:story.append(para('原创教学样例，非真实论文分析。'))
    if stale:story.append(para('论文已人工修订；本矩阵使用当前抽取结果。'))
    story.extend([Spacer(1,8),table,NextPageTemplate('details'),PageBreak(),para('完整明细',title)])
    for index,p in enumerate(papers,1):
        story.extend([para(f'{index:02d} · '+p['metadata']['title'],paper_heading),para(str(p['metadata'].get('year') or '未知年份')+' · 版本 '+str(p.get('revision',1))),para(p['extraction'].get('method_name') or '')])
        for label,items in [('核心方法',values(p,'methods')),('方法优势',values(p,'advantages')),('作者原文局限',values(p,'limitations')),('数据集 / 指标',evaluations(p))]:
            story.append(para(label,section))
            if not items:story.append(para('未找到明确陈述'));continue
            for number,text in enumerate(items,1):story.append(para(f'{number}. '+text))
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont(FONT,9);canvas.setFillColor(colors.HexColor('#667780'));canvas.drawCentredString(size[0]/2,20,str(doc.page));canvas.restoreState()
    doc=BaseDocTemplate(output,pagesize=size,leftMargin=32,rightMargin=32,topMargin=30,bottomMargin=42,title='多论文对比矩阵')
    height=size[1]-72
    def frame(x,w,name):return Frame(x,42,w,height,id=name,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    col=(width-24)/2
    doc.addPageTemplates([PageTemplate(id='overview',frames=[frame(32,width,'full')],onPage=footer),PageTemplate(id='details',frames=[frame(32,col,'left'),frame(32+col+24,col,'right')],onPage=footer)])
    doc.build(story)
    return output.getvalue()
