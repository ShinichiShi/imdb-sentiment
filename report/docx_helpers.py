"""Tiny XML helpers to emit paragraphs that match the formatting of the college report template."""
import copy
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
q = lambda t: "{%s}%s" % (W, t)
DECL = 'xmlns:w="%s"' % W


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def runs_xml(text, size=None, bold=False, italic=False):
    """'plain **bold** plain' -> runs. size in half-points."""
    out = []
    for i, part in enumerate(text.split("**")):
        if not part:
            continue
        rpr = ""
        if bold or i % 2 == 1:
            rpr += "<w:b/>"
        if italic:
            rpr += "<w:i/>"
        if size:
            rpr += '<w:sz w:val="%d"/>' % size
        out.append('<w:r><w:rPr>%s</w:rPr><w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, esc(part)))
    return "".join(out)


def P(ppr, content=""):
    return etree.fromstring("<w:p %s><w:pPr>%s</w:pPr>%s</w:p>" % (DECL, ppr, content))


def blank():
    return P('<w:pStyle w:val="BodyText"/>')


def chapter_label(n):
    return P('<w:spacing w:before="258"/><w:ind w:left="153" w:right="0" w:firstLine="0"/><w:jc w:val="left"/>'
             '<w:rPr><w:b/><w:sz w:val="28"/></w:rPr>', runs_xml("Chapter %s" % n, 28, bold=True))


def heading1(text, lines=None):
    c = ""
    for i, t in enumerate(lines or [text]):
        c += ("<w:r><w:br/></w:r>" if i else "") + "<w:r><w:t>%s</w:t></w:r>" % esc(t)
    return P('<w:pStyle w:val="Heading1"/><w:spacing w:before="84"/>', c)


def heading2(text):
    return P('<w:pStyle w:val="Heading2"/>', "<w:r><w:t>%s</w:t></w:r>" % esc(text))


def body(text, left=153, right=151):
    return P('<w:pStyle w:val="BodyText"/><w:spacing w:line="300" w:lineRule="auto"/>'
             '<w:ind w:left="%d" w:right="%d"/><w:jc w:val="both"/>' % (left, right), runs_xml(text))


def label(text, left=161):
    return P('<w:keepNext/><w:spacing w:before="0"/><w:ind w:left="%d" w:right="0" w:firstLine="0"/><w:jc w:val="both"/>'
             '<w:rPr><w:b/><w:sz w:val="28"/></w:rPr>' % left, runs_xml(text, 28, bold=True))


def listp(text, num, ilvl, left, hang, bold=False, jc="both", line=295, before=0, size=28, keep=False):
    return P('<w:pStyle w:val="ListParagraph"/>' + ('<w:keepNext/>' if keep else '') + '<w:numPr><w:ilvl w:val="%d"/><w:numId w:val="%d"/></w:numPr>'
             '<w:spacing w:line="%d" w:lineRule="auto" w:before="%d" w:after="0"/>'
             '<w:ind w:left="%d" w:right="154" w:hanging="%d"/><w:jc w:val="%s"/><w:rPr><w:sz w:val="%d"/></w:rPr>'
             % (ilvl, num, line, before, left, hang, jc, size), runs_xml(text, size, bold=bold))


# bullets / numbering exactly as used by the template
def bullet(text):            return listp(text, 2, 0, 874, 360)                      # chapter 1 bullets
def lit_title(text):         return listp(text, 3, 0, 873, 360, bold=True, line=300, before=1, keep=True)
def lit_bullet(text):        return listp(text, 3, 1, 1593, 360, jc="both", line=290)
def c3_num(text):            return listp(text, 5, 0, 431, 278, bold=True, jc="left", line=240, keep=True)
def c3_bullet(text):         return listp(text, 6, 0, 873, 359, jc="left", line=240, before=80)
def c3_sub(text):            return listp(text, 5, 1, 640, 487, bold=True, jc="left", line=240, before=79, keep=True)
def c3_subbullet(text):      return listp(text, 5, 2, 1233, 359, jc="left", line=240, before=80)
def ref(text):               return listp(text, 12, 0, 873, 360, line=276)


def centered(text, size=28, bold=False, italic=False, before=0):
    return P('<w:pStyle w:val="BodyText"/><w:spacing w:before="%d"/><w:jc w:val="center"/>' % before,
             runs_xml(text, size, bold=bold, italic=italic))


def placeholder(text):
    """Bordered grey box where a screenshot will be pasted."""
    return etree.fromstring(
        '<w:tbl %s><w:tblPr><w:tblW w:w="9400" w:type="dxa"/><w:jc w:val="center"/><w:tblBorders>'
        '<w:top w:val="dashed" w:sz="6" w:space="0" w:color="808080"/><w:left w:val="dashed" w:sz="6" w:space="0" w:color="808080"/>'
        '<w:bottom w:val="dashed" w:sz="6" w:space="0" w:color="808080"/><w:right w:val="dashed" w:sz="6" w:space="0" w:color="808080"/>'
        '</w:tblBorders></w:tblPr><w:tblGrid><w:gridCol w:w="9400"/></w:tblGrid><w:tr><w:trPr><w:cantSplit/><w:trHeight w:val="3000" w:hRule="atLeast"/></w:trPr>'
        '<w:tc><w:tcPr><w:tcW w:w="9400" w:type="dxa"/><w:vAlign w:val="center"/></w:tcPr>'
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>%s</w:p></w:tc></w:tr></w:tbl>'
        % (DECL, runs_xml("[ " + text + " ]", 24, italic=True)))


def flow_table(cells):
    """One-row boxed architecture strip: list of (title, subtitle)."""
    n = len(cells)
    cw = 1700
    grid = "".join('<w:gridCol w:w="%d"/>' % cw for _ in range(n))
    tcs = ""
    for i, (t, s) in enumerate(cells):
        tcs += ('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="F3F3F3"/><w:vAlign w:val="center"/></w:tcPr>'
                '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="60" w:after="0"/></w:pPr>%s</w:p>'
                '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="0" w:after="60"/></w:pPr>%s</w:p></w:tc>'
                % (cw, runs_xml(t, 22, bold=True), runs_xml(s, 18)))
    return etree.fromstring(
        '<w:tbl %s><w:tblPr><w:tblW w:w="%d" w:type="dxa"/><w:jc w:val="center"/><w:tblBorders>'
        '<w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/><w:left w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/><w:right w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
        '<w:insideV w:val="single" w:sz="8" w:space="0" w:color="000000"/></w:tblBorders></w:tblPr><w:tblGrid>%s</w:tblGrid>'
        '<w:tr><w:trPr><w:trHeight w:val="900" w:hRule="atLeast"/></w:trPr>%s</w:tr></w:tbl>' % (DECL, cw * n, grid, tcs))


def simple_table(rows, widths, header=True):
    """Bordered table of short text cells (size 22)."""
    grid = "".join('<w:gridCol w:w="%d"/>' % w for w in widths)
    trs = ""
    for ri, row in enumerate(rows):
        tcs = ""
        for ci, cell in enumerate(row):
            b = header and ri == 0
            shade = '<w:shd w:val="clear" w:color="auto" w:fill="E7E6E6"/>' if b else ""
            tcs += ('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s</w:tcPr><w:p><w:pPr><w:spacing w:before="40" w:after="40"/>'
                    '<w:ind w:left="80" w:right="80"/></w:pPr>%s</w:p></w:tc>' % (widths[ci], shade, runs_xml(cell, 22, bold=b)))
        trs += "<w:tr>%s</w:tr>" % tcs
    bd = "".join('<w:%s w:val="single" w:sz="4" w:space="0" w:color="000000"/>' % s
                 for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
    return etree.fromstring('<w:tbl %s><w:tblPr><w:tblW w:w="%d" w:type="dxa"/><w:jc w:val="center"/><w:tblBorders>%s</w:tblBorders>'
                            '</w:tblPr><w:tblGrid>%s</w:tblGrid>%s</w:tbl>' % (DECL, sum(widths), bd, grid, trs))


def section_break():
    return P('<w:pStyle w:val="BodyText"/><w:spacing w:after="0" w:line="300" w:lineRule="auto"/><w:jc w:val="both"/>'
             '<w:sectPr><w:pgSz w:w="11910" w:h="16840"/><w:pgMar w:header="714" w:footer="1294" w:top="1080" '
             'w:bottom="1480" w:left="566" w:right="566"/></w:sectPr>')


def set_runs(p, content_xml):
    """Replace all runs in paragraph p (keeps pPr)."""
    for ch in list(p):
        if ch.tag != q("pPr"):
            p.remove(ch)
    for r in etree.fromstring("<w:x %s>%s</w:x>" % (DECL, content_xml)):
        p.append(r)
