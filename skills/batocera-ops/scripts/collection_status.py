#!/usr/bin/env python3
"""List every line of a custom collection with its state. Read-only.

Run it ON the Batocera box:

    python3 collection_status.py /userdata/system/configs/emulationstation/collections/custom-<name>.cfg

One output line per collection line:

    <state>  <system>  file=<bool> img=<bool> vid=<bool>  <file name>

state:
    visible     ES indexes the path and the game is not hidden
    hidden      ES indexes the path, the game is hidden (not shown in the tile)
    NOT-INDEXED ES knows the system but not this path (typo, wrong extension,
                file added after ES started)
    NO-SYSTEM   ES has no system with the name of the line's folder. Typical
                cause: the folder is a symlink or an old name of another
                system, and ES indexes the games under the other name.

The exit code is 1 when any line is NOT-INDEXED or NO-SYSTEM.
With --no-api the script reads gamelist.xml files only (use it while ES is
down); it then cannot tell NO-SYSTEM from a missing gamelist entry.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

API = os.environ.get("ES_API", "http://127.0.0.1:1234")


def api_games(system):
    """Return {path: game dict} for one system, or None if ES has no such system."""
    try:
        with urllib.request.urlopen("%s/systems/%s/games" % (API, system), timeout=20) as r:
            return {g.get("path"): g for g in json.load(r)}
    except urllib.error.HTTPError:
        return None


def gamelist_entry(path):
    """Return the <game> block for a ROM path from its folder's gamelist.xml, or ''."""
    folder = os.path.dirname(path)
    gl = os.path.join(os.path.realpath(folder), "gamelist.xml")
    if not os.path.exists(gl):
        return ""
    text = open(gl, encoding="utf-8").read()
    name = re.escape(escape(os.path.basename(path)))
    m = re.search(r"<game[^>]*>(?:(?!</game>).)*?<path>\./" + name + r"</path>.*?</game>", text, re.S)
    return m.group(0) if m else ""


def main():
    args = [a for a in sys.argv[1:] if a != "--no-api"]
    use_api = "--no-api" not in sys.argv
    if len(args) != 1:
        sys.exit(__doc__)
    cache, bad = {}, 0
    for line in open(args[0], encoding="utf-8"):
        path = line.strip()
        if not path:
            continue
        system = os.path.basename(os.path.dirname(path))
        if use_api:
            if system not in cache:
                cache[system] = api_games(system)
            games = cache[system]
            if games is None:
                state, img, vid = "NO-SYSTEM", False, False
            elif path not in games:
                state, img, vid = "NOT-INDEXED", False, False
            else:
                g = games[path]
                state = "hidden" if str(g.get("hidden", "")).lower() == "true" else "visible"
                img, vid = bool(g.get("image")), bool(g.get("video"))
        else:
            block = gamelist_entry(path)
            state = "hidden" if "<hidden>true" in block else ("visible" if block else "NOT-INDEXED")
            img, vid = "<image>" in block, "<video>" in block
        if state in ("NOT-INDEXED", "NO-SYSTEM"):
            bad += 1
        print("%-11s %-14s file=%-5s img=%-5s vid=%-5s %s"
              % (state, system, os.path.exists(path), img, vid, os.path.basename(path)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
