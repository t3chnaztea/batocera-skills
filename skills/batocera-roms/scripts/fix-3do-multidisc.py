#!/usr/bin/env python3
"""3DO multi-disc cleanup for Batocera: one visible entry per game, dedupe, cue backfill.

Multi-disc 3DO games otherwise show every disc as its own EmulationStation entry
(a 4-disc game = 4 rows in the menu). The obvious fix is an .m3u playlist, but
the Opera libretro core does NOT support m3u (upstream Opera issue #14; this
build reports supported_extensions "iso|bin|chd|cue" and disk_control false), so
the design here is:

1. Dedupe: .zip copies of games that also exist as bin/cue move to
   ./.dupes-removed/ (moved, not deleted). Region-insensitive title match, so
   '(USA)' vs '(USA, Europe)' rips of the same game collide.
2. Cue backfill: some sets are bin-only, and bare .bin is not an ES extension for
   3do, so those games are invisible entirely. Generate a .cue per disc (track
   mode MODE1/2352 vs MODE1/2048 chosen by raw-CD sync-pattern sniff).
3. One visible entry per game: disc 1's entry gets the clean title (no "(Disc 1)")
   and its hidden flag removed; discs 2+ get hidden=true. Each disc still launches
   independently: Opera has no in-core disc swap, so when a game asks for disc 2,
   toggle ES "show hidden games" and launch it. Batocera defaults
   opera_nvram_storage=shared for disc-named roms, so saves carry across discs.
4. Rollback of any prior m3u attempt: *.m3u are deleted and their gamelist
   entries removed.

Idempotent. Run ON the Batocera box with EmulationStation STOPPED (ES writes
gamelists on exit and would clobber the edits):

    /etc/init.d/S31emulationstation stop && python3 fix-3do-multidisc.py \
        && /etc/init.d/S31emulationstation start

Adjust ROMS if your 3do rom directory differs.
"""
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

ROMS = Path("/userdata/roms/3do")
GAMELIST = ROMS / "gamelist.xml"
DUPES = ROMS / ".dupes-removed"
DISC_RE = re.compile(r"\s*\(Disc [^)]*\)")
CD_SYNC = b"\x00" + b"\xff" * 10 + b"\x00"

def base_title(stem: str) -> str:
    return stem[: DISC_RE.search(stem).start()].rstrip()

def dupe_key(stem: str) -> str:
    """Region-insensitive title: '(USA)' vs '(USA, Europe)' must collide."""
    return re.sub(r"\s*\([^)]*\)", "", base_title(stem)).strip().lower()

DISC_WORDS = {w: i for i, w in enumerate(
    "one two three four five six seven eight nine ten".split(), 1)}

def disc_no(stem: str) -> int | None:
    """'(Disc 2)', '(Disc 02 of 4)', '(Disc B)', '(Disc Two)' -> 2; else None."""
    m = re.search(r"\(Disc ([^)\s]+)", stem)
    tok = m.group(1).lower() if m else ""
    if tok.isdigit():
        return int(tok)
    if len(tok) == 1 and "a" <= tok <= "z":
        return ord(tok) - ord("a") + 1
    return DISC_WORDS.get(tok)

def write_cue(bin_path: Path) -> Path:
    with bin_path.open("rb") as f:
        mode = "MODE1/2352" if f.read(12) == CD_SYNC else "MODE1/2048"
    cue = bin_path.with_suffix(".cue")
    cue.write_text(f'FILE "{bin_path.name}" BINARY\n'
                   f"  TRACK 01 {mode}\n    INDEX 01 00:00:00\n",
                   encoding="utf-8")
    return cue

def main() -> None:
    discs = [p for p in ROMS.iterdir()
             if p.is_file() and DISC_RE.search(p.stem)]
    # validate before touching the filesystem: skip discs we cannot number
    for p in [p for p in discs if disc_no(p.stem) is None]:
        print(f"  skip (unparseable disc number): {p.name}")
        discs.remove(p)

    # --- 1. dedupe zips ---------------------------------------------------
    cue_bin_titles = {dupe_key(p.stem) for p in discs
                      if p.suffix in (".cue", ".bin")}
    moved = []
    for p in list(discs):
        if p.suffix == ".zip" and dupe_key(p.stem) in cue_bin_titles:
            DUPES.mkdir(exist_ok=True)
            shutil.move(str(p), DUPES / p.name)
            moved.append(p.name)
            discs.remove(p)

    # --- group sets; ES-visible representative per disc -------------------
    # (.cue/.iso/.chd are ES extensions; bare .bin is not)
    sets: dict[str, dict[int, Path]] = {}
    cued = []
    for p in discs:
        if p.suffix == ".bin":
            if p.with_suffix(".cue").exists():
                continue  # its cue represents it
            cue = write_cue(p)
            cued.append(cue.name)
            p = cue
        sets.setdefault(base_title(p.stem), {})[disc_no(p.stem)] = p
    multi = {t: d for t, d in sets.items() if len(d) >= 2}

    # --- 2. rollback m3u files --------------------------------------------
    removed_m3us = [m.name for m in ROMS.glob("*.m3u")]
    for m in ROMS.glob("*.m3u"):
        m.unlink()

    # --- 3. gamelist: clean disc1, hide 2+, drop m3u entries ---------------
    tree = ET.parse(GAMELIST)
    root = tree.getroot()
    entries = {}
    dropped = 0
    for game in list(root.findall("game")):
        name = Path(game.findtext("path") or "").name
        if name.endswith(".m3u"):
            root.remove(game)
            dropped += 1
        else:
            entries[name] = game

    def set_child(game: ET.Element, tag: str, text: str | None) -> None:
        el = game.find(tag)
        if text is None:
            if el is not None:
                game.remove(el)
            return
        if el is None:
            el = ET.SubElement(game, tag)
        el.text = text

    d1_fixed = hidden = created = 0
    for title, by_disc in sorted(multi.items()):
        first = min(by_disc)
        for n, rep in sorted(by_disc.items()):
            game = entries.get(rep.name)
            if game is None:
                game = ET.SubElement(root, "game")
                set_child(game, "path", f"./{rep.name}")
                set_child(game, "name", base_title(rep.stem))
                created += 1
            if n == first:
                clean = DISC_RE.sub("", game.findtext("name") or "").strip() \
                        or base_title(rep.stem)
                set_child(game, "name", clean)
                set_child(game, "hidden", None)
                d1_fixed += 1
            else:
                set_child(game, "hidden", "true")
                hidden += 1

    bak = GAMELIST.with_suffix(".xml.bak-3domultidisc")
    if not bak.exists():
        bak.write_bytes(GAMELIST.read_bytes())
    tree.write(GAMELIST, encoding="utf-8", xml_declaration=True)

    print(f"zip_dupes_moved={len(moved)} cues_generated={len(cued)} "
          f"m3us_removed={len(removed_m3us)} m3u_entries_dropped={dropped} "
          f"disc1_cleaned={d1_fixed} discs_hidden={hidden} "
          f"entries_created={created} multi_disc_sets={len(multi)}")
    for t in sorted(multi):
        print(f"  set: {t} ({len(multi[t])} discs)")

if __name__ == "__main__":
    main()
