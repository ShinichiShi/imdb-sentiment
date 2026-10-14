#!/bin/sh
# Build the report twice: pass 1 renders to find chapter pages, pass 2 fills the contents table.
# usage: report/make_report.sh "<template.docx>"   (run from the repo root)
set -e
T="${1:-mini project report.docx}"; OUT="report/CineSentiment Mini Project Report"
python3 -I report/build_report.py "$T" "$OUT.docx"
(cd report && soffice --headless --convert-to pdf "CineSentiment Mini Project Report.docx" >/dev/null 2>&1)
python3 -I report/toc_pages.py "$OUT.pdf" > report/pages.json
python3 -I report/build_report.py "$T" "$OUT.docx" report/pages.json
(cd report && soffice --headless --convert-to pdf "CineSentiment Mini Project Report.docx" >/dev/null 2>&1)
rm -f report/pages.json; echo built "$OUT".docx / .pdf
