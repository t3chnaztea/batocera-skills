#!/usr/bin/env python3
"""Set or clear <hidden> on gamelist.xml entries without reformatting the file.

It edits the text in place, so every other field, the entry order, and the
whitespace stay as ES wrote them. It writes a backup next to the gamelist first.

Usage:
  python3 set_hidden.py <gamelist.xml> <map.json> <backup-suffix>
  python3 set_hidden.py <gamelist.xml> --all <backup-suffix>

map.json: {"<file name or file name without extension>": true | false, ...}
Entries that are not in the map stay as they are. --all hides every entry.

Run it while ES is stopped, or kill ES with SIGKILL straight after. A clean ES
exit writes its own copy of the gamelist back and discards the edit.
"""
import json
import re
import shutil
import sys
from pathlib import Path
from xml.sax.saxutils import unescape

if len(sys.argv) != 4:
    sys.exit(__doc__)
ALL = sys.argv[2] == "--all"
gl, suffix = Path(sys.argv[1]), sys.argv[3]
want = {} if ALL else json.load(open(sys.argv[2], encoding="utf-8"))
shutil.copy2(gl, f"{gl}.{suffix}")
text = gl.read_text(encoding="utf-8")
changed = 0


def lookup(block):
    m = re.search(r"<path>\./(.+?)</path>", block)
    if not m:
        return None
    name = unescape(m.group(1))
    for key in (name, name.rsplit(".", 1)[0]):
        if key in want:
            return want[key]
    return None


def fix(m):
    global changed
    block = m.group(0)
    hide = True if ALL else lookup(block)
    if hide is None:
        return block
    new = re.sub(r"\s*<hidden>[^<]*</hidden>", "", block)
    if hide:
        new = new[: -len("</game>")].rstrip() + "\n\t\t<hidden>true</hidden>\n\t</game>"
    changed += new != block
    return new


# Some entries close with </game> on the same line as a field, so match on the tag pair.
out = re.sub(r"<game[ >].*?</game>", fix, text, flags=re.S)
gl.write_text(out, encoding="utf-8")
print(f"{gl}: changed {changed}, hidden now {out.count('<hidden>true</hidden>')}, games {out.count('<path>')}")
