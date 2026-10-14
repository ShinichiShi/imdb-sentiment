"""Build the CineSentiment mini-project report from the college template.

    python report/build_report.py "mini project report.docx" "report/CineSentiment Mini Project Report.docx" [pages.json]

The template's cover page, certificate, header/footer, styles and numbering are reused unchanged; the
front-matter text is edited in place and everything after the contents page is regenerated from content.py.
`pages.json` ({"Abstract": "3", ...}) fills the contents table (see report/make_report.sh).
"""
import copy
import json
import re
import shutil
import sys
import tempfile
import zipfile
import os

from lxml import etree

sys.path.insert(0, os.path.dirname(__file__))
from docx_helpers import *          # noqa: E402,F401
import content as C                 # noqa: E402

src, dst = sys.argv[1], sys.argv[2]
pages = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}

tmp = tempfile.mkdtemp()
with zipfile.ZipFile(src) as z:
    z.extractall(tmp)

doc_path = os.path.join(tmp, "word", "document.xml")
tree = etree.parse(doc_path)
body_el = tree.getroot().find("w:body", NS)
kids = list(body_el)
final_sect = kids[-1]                       # body-level sectPr

# ---- cover page -------------------------------------------------------------------------------
set_runs(kids[10], runs_xml(C.TITLE_COVER, 28, bold=True))

name_ppr = ('<w:spacing w:before="0"/><w:ind w:left="3600" w:right="0" w:firstLine="0"/><w:jc w:val="left"/>'
            '<w:rPr><w:b/><w:sz w:val="28"/></w:rPr>')
names = [P(name_ppr, runs_xml("%s (%s)" % (n, usn), 28, bold=True)) for n, usn in C.STUDENTS]
body_el.replace(kids[14], names[0])
for i, p in enumerate(names[1:], 1):
    names[i - 1].addnext(p)
body_el.remove(kids[15])

set_runs(kids[18], runs_xml("Seventh Semester B.E.(CSE)", 28, bold=True) + "<w:r><w:br/></w:r>" + runs_xml("2026-2027", 28, bold=True))
ppr = kids[18].find("w:pPr", NS)
ind = ppr.find("w:ind", NS)
ind.set(q("left"), "3000"); ind.set(q("right"), "3000")

# ---- cover: explicit line breaks instead of narrow-indent wrapping (renders the same in Word and LibreOffice) --
BR = "<w:r><w:br/></w:r>"
def centred_lines(p, lines):
    set_runs(p, BR.join(runs_xml(l, 28, bold=True) for l in lines))
    ind = p.find("w:pPr/w:ind", NS)
    ind.set(q("left"), "0"); ind.set(q("right"), "0"); ind.attrib.pop(q("hanging"), None); ind.set(q("firstLine"), "0")
    p.find("w:pPr/w:jc", NS).set(q("val"), "center")
    sp = p.find("w:pPr/w:spacing", NS)
    sp.attrib.pop(q("lineRule"), None); sp.set(q("line"), "300"); sp.set(q("lineRule"), "auto")
centred_lines(kids[21], ["Prof. Nidhishree", "Assistant Professor", "Dept. of CSE", "DSCE, Bangalore"])
centred_lines(kids[24], ["Department of Computer Science and Engineering", "Dayananda Sagar College of Engineering", "Bangalore-560111"])
body_el.remove(kids[25])
body_el.remove(kids[23])

# ---- certificate --------------------------------------------------------------------------------
cert_names = ", ".join("%s [%s]" % (n, u) for n, u in C.STUDENTS)
set_runs(kids[34],
         runs_xml("This is to certify that the mini-project entitled **%s** is a bonafide work carried out by **%s** "
                  "in partial fulfilment of 7th semester, Bachelor of Engineering in Computer Science and Engineering "
                  "under Visvesvaraya Technological University, Belgaum during the year 2026-27." % (C.TITLE, cert_names), 24))

# ---- acknowledgement ----------------------------------------------------------------------------
set_runs(kids[54], runs_xml("We are pleased to have successfully completed the Mini project **“%s”**. We thoroughly enjoyed "
                            "the process of working on this project and gained a lot of knowledge doing so." % C.TITLE, 24))

ack_ppr = ('<w:spacing w:before="0" w:line="396" w:lineRule="auto"/><w:ind w:left="7041" w:right="0" w:firstLine="0"/>'
           '<w:jc w:val="left"/><w:rPr><w:rFonts w:ascii="Calibri"/><w:sz w:val="24"/></w:rPr>')
ack = []
for n, usn in C.STUDENTS:
    p = P(ack_ppr, '<w:r><w:rPr><w:rFonts w:ascii="Calibri"/><w:sz w:val="24"/></w:rPr><w:t xml:space="preserve">%s, %s</w:t></w:r>' % (n, usn))
    p.find("w:pPr/w:spacing", NS).set(q("line"), "300")
    ack.append(p)
body_el.replace(kids[59], ack[0])
for i, p in enumerate(ack[1:], 1):
    ack[i - 1].addnext(p)
body_el.remove(kids[60])

# ---- contents table page numbers ---------------------------------------------------------------
if pages:
    rows = kids[66].findall("w:tr", NS)[1:]
    labels = ["Abstract", "Introduction", "Literature Survey", "System design & Methodology",
              "Snapshots and Results", "Conclusion & Future Enhancements", "References", "Appendix"]
    for tr, lab in zip(rows, labels):
        cell = tr.findall("w:tc", NS)[2]
        ts = cell.findall(".//w:t", NS)
        ts[0].text = pages[lab]
        for t in ts[1:]:
            t.text = ""

# ---- abstract + regenerated body ----------------------------------------------------------------
set_runs(kids[72], runs_xml(C.ABSTRACT))

for el in kids[74:-1]:                      # everything after the abstract's section break
    body_el.remove(el)
for chunk in (C.chapter1(), C.chapter2(), C.chapter3(), C.chapter4(), C.chapter5(), C.references(), C.appendix()):
    for el in chunk:
        final_sect.addprevious(el)

tree.write(doc_path, xml_declaration=True, encoding="UTF-8", standalone=True)

# ---- header title ---------------------------------------------------------------------------------
hp = os.path.join(tmp, "word", "header1.xml")
raw = open(hp, encoding="utf8").read()
raw = re.sub(r"<w:t>CROWDWAVE:</w:t>(.*?)<w:t>PLATFORM</w:t>",
             lambda m: "<w:t>%s</w:t>" % C.HEADER_TITLE, raw, flags=re.S)
open(hp, "w", encoding="utf8").write(raw)

# ---- core properties --------------------------------------------------------------------------------
cp = os.path.join(tmp, "docProps", "core.xml")
if os.path.exists(cp):
    x = open(cp, encoding="utf8").read()
    x = re.sub(r"<dc:title>.*?</dc:title>", "<dc:title>%s</dc:title>" % C.TITLE, x)
    open(cp, "w", encoding="utf8").write(x)

# ---- footer: widen the page-number text box so two-digit page numbers are not clipped ----------------
fp = os.path.join(tmp, "word", "footer1.xml")
fx = open(fp, encoding="utf8").read()
fx = fx.replace("486409", "760000")
fx = fx.replace("width:38.3pt", "width:59.8pt")
open(fp, "w", encoding="utf8").write(fx)

# ---- cover page: make the first section a normal page-type section (keeps the page border in LibreOffice) --
dx = open(doc_path, encoding="utf8").read()
dx = dx.replace('<w:sectPr><w:type w:val="continuous"/><w:pgSz w:w="11910" w:h="16840"/><w:pgMar w:top="720"', '<w:sectPr><w:pgSz w:w="11910" w:h="16840"/><w:pgMar w:top="720"', 1)
open(doc_path, "w", encoding="utf8").write(dx)

# ---- zip ---------------------------------------------------------------------------------------------
if os.path.exists(dst):
    os.remove(dst)
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
    # [Content_Types].xml first, as Word expects
    z.write(os.path.join(tmp, "[Content_Types].xml"), "[Content_Types].xml")
    for d, _, files in os.walk(tmp):
        for f in files:
            full = os.path.join(d, f)
            arc = os.path.relpath(full, tmp)
            if arc != "[Content_Types].xml":
                z.write(full, arc)
shutil.rmtree(tmp)
print("wrote", dst)
