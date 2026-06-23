from pathlib import Path
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, PageBreak
from reportlab.lib.units import mm
from xml.sax.saxutils import escape

SRC = Path('/Users/zall/interviews/cv_pdf_exact_draft.md')
OUT = Path('/Users/zall/interviews/ALEKSANDR_ZALESOV-cv-regenerated.pdf')

text = SRC.read_text()
lines = text.splitlines()

name = ''
contact = ''
headline = ''
summary = ''
core_skills = ''
sections = []
current_section = None
current_role = None
state = None

for raw in lines:
    line = raw.rstrip()
    if not line:
        continue
    if line.startswith('# '):
        name = line[2:].strip()
        continue
    if not contact and not line.startswith('## ') and not line.startswith('### '):
        if line.startswith('['):
            contact = line
        elif not headline:
            contact = line
        continue
    if line.startswith('## '):
        title = line[3:].strip()
        if not headline:
            headline = title
            state = 'after_headline'
            continue
        current_section = {'title': title, 'roles': [], 'items': [], 'paragraphs': []}
        sections.append(current_section)
        current_role = None
        state = title.lower()
        continue
    if state == 'after_headline' and not summary:
        summary = line.strip()
        continue
    if current_section and current_section['title'] == 'Core Skills':
        core_skills = line.strip()
        continue
    if line.startswith('### '):
        current_role = {'title': line[4:].strip(), 'bullets': []}
        if current_section:
            current_section['roles'].append(current_role)
        continue
    if line.startswith('- '):
        item = line[2:].strip()
        if current_role:
            current_role['bullets'].append(item)
        elif current_section:
            current_section['items'].append(item)
        continue
    if current_section:
        current_section['paragraphs'].append(line.strip())

# Parse contact markdown links into plain text
contact = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', contact)

styles = getSampleStyleSheet()
base_font = 'Helvetica'
bold_font = 'Helvetica-Bold'

styles.add(ParagraphStyle(
    name='NameStyle', fontName=bold_font, fontSize=20, leading=24,
    textColor=colors.HexColor('#111111'), alignment=TA_CENTER, spaceAfter=4
))
styles.add(ParagraphStyle(
    name='ContactStyle', fontName=base_font, fontSize=9.5, leading=12,
    textColor=colors.HexColor('#444444'), alignment=TA_CENTER, spaceAfter=8
))
styles.add(ParagraphStyle(
    name='HeadlineStyle', fontName=bold_font, fontSize=13, leading=16,
    textColor=colors.HexColor('#1f4e79'), alignment=TA_CENTER, spaceAfter=10
))
styles.add(ParagraphStyle(
    name='SummaryStyle', fontName=base_font, fontSize=9.6, leading=13,
    textColor=colors.black, alignment=TA_LEFT, spaceAfter=8
))
styles.add(ParagraphStyle(
    name='SectionStyle', fontName=bold_font, fontSize=11, leading=13,
    textColor=colors.HexColor('#1f4e79'), spaceBefore=4, spaceAfter=5,
    borderWidth=0, borderPadding=0
))
styles.add(ParagraphStyle(
    name='RoleStyle', fontName=bold_font, fontSize=10.2, leading=12.5,
    textColor=colors.black, spaceBefore=5, spaceAfter=2
))
styles.add(ParagraphStyle(
    name='BodyStyle', fontName=base_font, fontSize=9.2, leading=11.8,
    textColor=colors.black, spaceAfter=2
))
styles.add(ParagraphStyle(
    name='BulletStyle', fontName=base_font, fontSize=9.0, leading=11.4,
    leftIndent=10, firstLineIndent=0, spaceBefore=0, spaceAfter=1.5
))


def p(txt, style):
    return Paragraph(escape(txt).replace('\n', '<br/>'), styles[style])

story = []
story.append(p(name, 'NameStyle'))
story.append(p(contact, 'ContactStyle'))
story.append(p(headline, 'HeadlineStyle'))
story.append(p(summary, 'SummaryStyle'))
story.append(p('Core Skills', 'SectionStyle'))
story.append(p(core_skills, 'BodyStyle'))

for sec in sections:
    title = sec['title']
    if title == 'Core Skills':
        continue
    story.append(Spacer(1, 2))
    story.append(p(title, 'SectionStyle'))
    if sec['paragraphs']:
        for para in sec['paragraphs']:
            story.append(p(para, 'BodyStyle'))
    for role in sec['roles']:
        story.append(p(role['title'], 'RoleStyle'))
        bullet_items = []
        for b in role['bullets']:
            bullet_items.append(ListItem(p(b, 'BulletStyle')))
        if bullet_items:
            story.append(ListFlowable(
                bullet_items,
                bulletType='bullet',
                start='circle',
                leftIndent=0,
                bulletFontName=base_font,
                bulletFontSize=8,
                bulletColor=colors.black,
            ))
    if sec['items']:
        bullet_items = []
        for item in sec['items']:
            bullet_items.append(ListItem(p(item, 'BulletStyle')))
        story.append(ListFlowable(
            bullet_items,
            bulletType='bullet',
            start='circle',
            leftIndent=0,
            bulletFontName=base_font,
            bulletFontSize=8,
            bulletColor=colors.black,
        ))


def add_page_number(canvas, doc):
    canvas.setFont(base_font, 8)
    canvas.setFillColor(colors.HexColor('#666666'))
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 10 * mm, str(doc.page))


doc = SimpleDocTemplate(
    str(OUT),
    pagesize=A4,
    leftMargin=15 * mm,
    rightMargin=15 * mm,
    topMargin=14 * mm,
    bottomMargin=14 * mm,
)

doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
print(OUT)
