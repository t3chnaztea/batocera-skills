#!/usr/bin/env python3
"""Copy settings from the old GZDoom ini into the UZDoom ini (v44 renamed the emulator).

A setting is copied only when the key exists in both files and the values differ.
Keys that UZDoom removed stay removed. Not copied: search paths and autoexec paths,
[LastRun], the Joy:JS sections and Joy<n> bindings (batocera-launch writes them at
each launch), F11 (bumpgamma became bumplight) and the two keys that hold the
emulator name.

usage: doom_import.py [--apply] [<gzdoom.ini> <uzdoom.ini>]     (dry run prints each change)
Backup: uzdoom.ini.pre-import next to the file. Run it with no Doom game open,
because UZDoom writes its ini at exit.
"""
import re
import shutil
import sys

GZ = "/userdata/system/configs/gzdoom/gzdoom.ini"
UZ = "/userdata/system/configs/uzdoom/uzdoom.ini"
paths = [a for a in sys.argv[1:] if not a.startswith("--")]
if len(paths) == 2:
    GZ, UZ = paths
APPLY = "--apply" in sys.argv
SKIP_SECTION = re.compile(r"(Directories|AutoExec|LastRun)$|^Joy:")
SKIP_KEY = {"fluid_patchset", "timidity_config", "F11"}
SAME = ({"1", "true"}, {"0", "false"})


def parse(path):
    d, sec = {}, None
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.rstrip("\n")
        m = re.match(r"\[(.+)\]$", line)
        if m:
            sec = m.group(1)
            d.setdefault(sec, {})
        elif sec and "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            d[sec][k] = v
    return d


old = parse(GZ)
out, sec, n = [], None, 0
for line in open(UZ, encoding="utf-8", errors="replace"):
    raw = line.rstrip("\n")
    m = re.match(r"\[(.+)\]$", raw)
    if m:
        sec = m.group(1)
    elif sec in old and "=" in raw and not SKIP_SECTION.search(sec):
        k, v = raw.split("=", 1)
        nv = old[sec].get(k)
        if (nv is not None and nv != v and k not in SKIP_KEY and not re.match(r"Joy\d+$", k)
                and not any({nv, v} == s for s in SAME)):
            print(f"[{sec}] {k}: {v} -> {nv}")
            line = f"{k}={nv}\n"
            n += 1
    out.append(line)
print(n, "settings to copy" if not APPLY else "settings copied")
if APPLY and n:
    shutil.copy2(UZ, UZ + ".pre-import")
    open(UZ, "w", encoding="utf-8").writelines(out)
