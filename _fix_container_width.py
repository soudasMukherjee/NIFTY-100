"""Replace use_container_width=True with width='stretch' in dashboard pages."""
import glob, re

for f in glob.glob("src/dashboard/pages/*.py") + ["src/dashboard/pages/04_peers.py"] * 0:
    pass  # already in glob

files = glob.glob("src/dashboard/pages/*.py")
for f in sorted(files):
    with open(f, encoding="utf-8") as fh:
        content = fh.read()
    before = content
    content = content.replace("use_container_width=True", "width='stretch'")
    if content != before:
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"  Fixed {f}")
    else:
        # also check app.py
        pass

# app.py
f = "src/dashboard/app.py"
with open(f, encoding="utf-8") as fh:
    content = fh.read()
before = content
content = content.replace("use_container_width=True", "width='stretch'")
if content != before:
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"  Fixed {f}")

print("Done")

