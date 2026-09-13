"""Portable, embedded-CJK-font PDF export of completed user/tutor turns."""
import io
import os
import re
import reportlab
from pathlib import Path
from threading import Lock
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

FONT='TutorCJK'
_font_lock=Lock()

def register_font():
    with _font_lock:
        if FONT in pdfmetrics.getRegisteredFontNames():
            return
        candidates=[os.getenv('PDF_CJK_FONT',''), '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 'C:/Windows/Fonts/simhei.ttf']
        for path in candidates:
            if path and Path(path).is_file():
                pdfmetrics.registerFont(TTFont(FONT,path,subfontIndex=0))
                pdfmetrics.registerFontFamily(FONT,normal=FONT,bold=FONT,italic=FONT,boldItalic=FONT)
                pdfmetrics.registerFont(TTFont('TutorSymbols',str(Path(reportlab.__file__).parent/'fonts'/'Vera.ttf')))
                return
        raise FileNotFoundError('PDF_CJK_FONT')

def paragraph_text(text):
    # User/model strings are data, never ReportLab XML or external resources.
    primary=pdfmetrics.getFont(FONT).face.charToGlyph
    symbols=pdfmetrics.getFont('TutorSymbols').face.charToGlyph
    value=''.join(escape(ch) if ord(ch) in primary else ('<font name="TutorSymbols">'+escape(ch)+'</font>' if ord(ch) in symbols else escape('[U+%04X]'%ord(ch))) for ch in text)
    value=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',value)
    value=re.sub(r'`([^`]+)`',r'\1',value)
    return value

def conversation_pdf(turns):
    register_font()
    out=io.BytesIO()
    body=ParagraphStyle('body',fontName=FONT,fontSize=10.5,leading=17,wordWrap='CJK',alignment=TA_LEFT,spaceAfter=7,splitLongWords=True)
    role=ParagraphStyle('role',parent=body,fontSize=13,leading=20,textColor=colors.HexColor('#17666b'),spaceBefore=15,spaceAfter=7,keepWithNext=True)
    heading=ParagraphStyle('heading',parent=body,fontSize=12,leading=18,spaceBefore=8,keepWithNext=True)
    story=[]
    def add_text(text):
        for line in text.splitlines():
            if not line.strip():
                story.append(Spacer(1,5));continue
            if line.strip().startswith('```'):
                continue
            title=re.match(r'^#{1,6}\s+(.+)',line)
            story.append(Paragraph(paragraph_text(title.group(1) if title else line),heading if title else body))
    for turn in turns:
        story.append(Paragraph('用户提问',role));add_text(turn['question'])
        if isinstance(story[-1],Paragraph):
            story[-1].keepWithNext=True
        story.append(Paragraph('助教回答',role))
        answer=turn['answer']
        for block in answer.get('blocks',[]):
            add_text(block['text'])
        if answer.get('question'):
            add_text(answer['question'])
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont(FONT,9);canvas.setFillColor(colors.HexColor('#667780'))
        canvas.drawCentredString(A4[0]/2,22,str(doc.page));canvas.restoreState()
    SimpleDocTemplate(out,pagesize=A4,leftMargin=48,rightMargin=48,topMargin=38,bottomMargin=58,title='论文助教问答',author='').build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
