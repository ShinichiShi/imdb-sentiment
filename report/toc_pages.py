"""Find the printed page range of each chapter in the rendered PDF (page numbering starts at the acknowledgement)."""
import json, re, subprocess, sys
pdf = sys.argv[1]
n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
text = [subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), "-layout", pdf, "-"], capture_output=True, text=True).stdout for i in range(1, n + 1)]
OFFSET = 2          # cover + certificate are unnumbered
marks = [("Abstract", r"^\s*ABSTRACT\s*$"), ("Introduction", r"^\s*INTRODUCTION\s*$"), ("Literature Survey", r"^\s*LITERATURE SURVEY\s*$"),
         ("System design & Methodology", r"SYSTEM DESIGN & METHODOLOGY"), ("Snapshots and Results", r"SNAPSHOTS AND RESULTS"),
         ("Conclusion & Future Enhancements", r"FUTURE ENHANCEMENTS"), ("References", r"^\s*REFERENCES\s*$"), ("Appendix", r"^\s*APPENDIX\s*$")]
start = {}
for name, pat in marks:
    for i, t in enumerate(text, 1):
        if i > 4 and re.search(pat, t, re.M) or (name == "Abstract" and i > 2 and re.search(pat, t, re.M)):
            start[name] = i - OFFSET
            break
names = [m[0] for m in marks]
out = {}
for k, name in enumerate(names):
    s = start[name]
    e = (start[names[k + 1]] - 1) if k + 1 < len(names) else n - OFFSET
    out[name] = str(s) if e <= s else "%d-%d" % (s, e)
print(json.dumps(out))
