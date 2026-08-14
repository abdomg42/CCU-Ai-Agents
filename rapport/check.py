from pathlib import Path
from subprocess import run
base = Path("gi.cls").read_text(encoding="utf-8", errors="replace").splitlines(True)
for n in [100,150,200,250,300,320,340,360,380,400,420,430,440,450,460]:
    Path("tmp_test_partial.cls").write_text("".join(base[:n]), encoding="utf-8")
    Path("tmp_test.tex").write_text("\\documentclass{tmp_test_partial}\\begin{document}Test.\\end{document}", encoding="utf-8")
    res = run(["pdflatex","-interaction=nonstopmode","-halt-on-error","tmp_test.tex"], cwd=".", capture_output=True, text=True)
    print(f"n={n} return={res.returncode}")
    if res.returncode != 0:
        print(res.stdout.splitlines()[-30:])
        print(res.stderr.splitlines()[-30:])
        print("---")
        break
