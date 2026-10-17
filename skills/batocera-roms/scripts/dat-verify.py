#!/usr/bin/env python3
"""
dat-verify.py -- Batocera ROM library DAT verification (read-only).

Verifies cartridge ROMs against No-Intro DATs (hash match) and disc ROMs against
Redump DATs (chdman integrity + extract + per-track hash). Writes per-system
markdown reports and a summary. It NEVER downloads, moves, or modifies any ROM;
it only reads and reports.

Usage: python3 dat-verify.py [--skip-tier3]
  --skip-tier3  Skip CHD extraction/hashing (fast mode: integrity + name only)

Provide DAT files under DATS_DIR (No-Intro under no-intro/, Redump under redump/).
Do NOT place this script in /userdata/system/scripts/ -- ES auto-invokes anything
executable there as a game event hook. Run it from elsewhere on /userdata.
"""

import os, sys, hashlib, subprocess, zipfile, shutil, time, re, binascii
import xml.etree.ElementTree as ET
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# -- Config -----------------------------------------------------
ROMS_DIR = "/userdata/roms"
DATS_DIR = "/userdata/system/dats"
REDUMP_DATS = os.path.join(DATS_DIR, "redump")
NOINTRO_DATS = os.path.join(DATS_DIR, "no-intro")
REPORT_DIR = "/userdata/system/dat-audit/report"
TMP_DIR = "/userdata/system/dat-audit/tmp"
CHDMAN = "/usr/bin/mame/chdman"
SEVENZ = "/usr/bin/7z"
LOG_FILE = "/userdata/system/dat-audit/dat-verify.log"
CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB read chunks

# -- System mapping ---------------------------------------------
# dat_searches: substrings tried in order to find the DAT file.
# verify (disc systems): "chd" = full extract+hash, "bin_cue" = hash tracks
#         directly, "filename" = name match only (unverifiable format).
# For No-Intro (cartridge), verification is always hash-based.

SYSTEMS = {
    # -- Redump (disc-based) --
    "3do": {"type": "redump",
            "dat_searches": ["Panasonic - 3DO Interactive Multiplayer - Datfile"],
            "verify": "bin_cue"},
    "dreamcast": {"type": "redump",
                  "dat_searches": ["Sega - Dreamcast - Datfile"],
                  "verify": "chd"},
    "gamecube": {"type": "redump",
                 "dat_searches": ["Nintendo - GameCube - Datfile"],
                 "verify": "filename"},
    "neogeocd": {"type": "redump",
                 "dat_searches": ["SNK - Neo Geo CD - Datfile"],
                 "verify": "chd"},
    "pcenginecd": {"type": "redump",
                   "dat_searches": ["NEC - PC Engine CD & TurboGrafx CD - Datfile"],
                   "verify": "chd"},
    "psx": {"type": "redump",
            "dat_searches": ["Sony - PlayStation - Datfile"],
            "verify": "chd"},
    "saturn": {"type": "redump",
               "dat_searches": ["Sega - Saturn - Datfile"],
               "verify": "chd"},
    "segacd": {"type": "redump",
               "dat_searches": ["Sega - Mega CD & Sega CD - Datfile"],
               "verify": "chd"},
    # -- No-Intro (cartridge) --
    "atari2600": {"type": "nointro", "dat_searches": ["Atari - Atari 2600 (2"]},
    "colecovision": {"type": "nointro", "dat_searches": ["Coleco - ColecoVision (2"]},
    "gb": {"type": "nointro", "dat_searches": ["Nintendo - Game Boy (2"]},
    "gba": {"type": "nointro", "dat_searches": ["Nintendo - Game Boy Advance (2"]},
    "gbc": {"type": "nointro", "dat_searches": ["Nintendo - Game Boy Color (2"]},
    "jaguar": {"type": "nointro", "dat_searches": ["Atari - Atari Jaguar (J64)"]},
    "megadrive": {"type": "nointro", "dat_searches": ["Sega - Mega Drive - Genesis (2"]},
    "n64": {"type": "nointro", "dat_searches": ["Nintendo - Nintendo 64 (BigEndian)"]},
    "nes": {"type": "nointro",
            "dat_searches": ["Nintendo - Nintendo Entertainment System (Headered)"]},
    "ngpc": {"type": "nointro",
             "dat_searches": ["SNK - NeoGeo Pocket Color", "SNK - Neo Geo Pocket Color"]},
    "odyssey2": {"type": "nointro", "dat_searches": ["Magnavox - Odyssey 2"]},
    "pcengine": {"type": "nointro",
                 "dat_searches": ["NEC - PC Engine - TurboGrafx-16 (2"]},
    "sega32x": {"type": "nointro", "dat_searches": ["Sega - 32X (2"]},
    "snes": {"type": "nointro",
             "dat_searches": ["Nintendo - Super Nintendo Entertainment System (2"]},
    "supergrafx": {"type": "nointro", "dat_searches": ["NEC - PC Engine SuperGrafx"]},
    "vectrex": {"type": "nointro", "dat_searches": ["GCE - Vectrex"]},
    "virtualboy": {"type": "nointro", "dat_searches": ["Nintendo - Virtual Boy"]},
}

# Extensions we care about, grouped
DISC_EXTS = {".chd", ".cue", ".bin", ".iso", ".gdi", ".cdi", ".pbp", ".rvz", ".gcz", ".cso"}
CART_EXTS = {
    ".zip", ".7z", ".nes", ".sfc", ".smc", ".gb", ".gbc", ".gba",
    ".n64", ".z64", ".v64", ".gen", ".md", ".smd", ".a26", ".col",
    ".j64", ".pce", ".sgx", ".32x", ".vec", ".vb", ".ngp", ".ngc",
}


# -- Logging ----------------------------------------------------
def setup_logging():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, mode="w"),
                  logging.StreamHandler(sys.stdout)],
    )


# -- DAT parsing ------------------------------------------------
def find_dat_file(dat_dir, search_terms):
    """Find best-matching DAT file given list of search substrings (tried in order)."""
    if not os.path.isdir(dat_dir):
        return None
    files = [f for f in os.listdir(dat_dir) if f.endswith(".dat")]
    for term in search_terms:
        matches = [f for f in files if term in f]
        if matches:
            # Prefer the shortest match (most specific, avoids BIOS variants)
            best = sorted(matches, key=len)[0]
            return os.path.join(dat_dir, best)
    return None


def parse_dat(dat_path):
    """Parse a Logiqx XML DAT. Returns {game_name: {"roms": [{name, sha1, md5, crc, size}]}}"""
    games = {}
    try:
        tree = ET.parse(dat_path)
    except ET.ParseError as e:
        logging.error(f"Failed to parse DAT {dat_path}: {e}")
        return games
    root = tree.getroot()
    for game in root.findall("game"):
        name = game.get("name", "")
        roms = []
        for rom in game.findall("rom"):
            roms.append({
                "name": rom.get("name", ""),
                "sha1": (rom.get("sha1") or "").lower(),
                "md5": (rom.get("md5") or "").lower(),
                "crc": (rom.get("crc") or "").lower(),
                "size": int(rom.get("size", 0) or 0),
            })
        games[name] = {"roms": roms}
    return games


def build_hash_index(games):
    """Build sha1 -> (game_name, rom_name) and crc -> (game_name, rom_name) lookups."""
    sha1_idx, crc_idx = {}, {}
    for gname, gdata in games.items():
        for rom in gdata["roms"]:
            if rom["sha1"]:
                sha1_idx[rom["sha1"]] = (gname, rom["name"])
            if rom["crc"]:
                crc_idx[rom["crc"]] = (gname, rom["name"])
    return sha1_idx, crc_idx


# -- Scanning ---------------------------------------------------
def scan_roms(system_dir, system_type):
    """Return sorted list of ROM file paths in a directory."""
    if not os.path.isdir(system_dir):
        return []
    exts = DISC_EXTS if system_type == "redump" else CART_EXTS
    roms = []
    for f in sorted(os.listdir(system_dir)):
        fp = os.path.join(system_dir, f)
        if not os.path.isfile(fp):
            continue
        if os.path.splitext(f)[1].lower() in exts:
            roms.append(fp)
    return roms


def dedupe_disc_files(rom_files):
    """For disc systems, return one entry per game (skip .bin when .cue exists)."""
    cue_bases = set()
    for f in rom_files:
        if f.lower().endswith(".cue"):
            cue_bases.add(os.path.splitext(os.path.basename(f))[0].lower())
    deduped = []
    for f in rom_files:
        base = os.path.splitext(os.path.basename(f))[0].lower()
        ext = os.path.splitext(f)[1].lower()
        if ext == ".bin" and base in cue_bases:
            continue
        if ext == ".bin" and re.search(r'\(track \d+\)', base, re.IGNORECASE):
            continue
        deduped.append(f)
    return deduped


# -- Hashing ----------------------------------------------------
def hash_file(filepath, algos=("sha1", "crc32")):
    """Hash a file. Returns {"sha1": hex, "crc": hex8}."""
    result = {}
    sha1 = hashlib.sha1() if "sha1" in algos else None
    crc = 0
    with open(filepath, "rb") as fh:
        while True:
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                break
            if sha1:
                sha1.update(chunk)
            if "crc32" in algos:
                crc = binascii.crc32(chunk, crc)
    if sha1:
        result["sha1"] = sha1.hexdigest()
    if "crc32" in algos:
        result["crc"] = format(crc & 0xFFFFFFFF, "08x")
    return result


def hash_zip_rom(zip_path):
    """Open ZIP, hash each file inside. Returns [(inner_name, {"sha1", "crc", "size"})]."""
    results = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                data = zf.read(info.filename)
                sha1 = hashlib.sha1(data).hexdigest()
                crc = format(binascii.crc32(data) & 0xFFFFFFFF, "08x")
                results.append((info.filename, {"sha1": sha1, "crc": crc, "size": len(data)}))
    except Exception as e:
        logging.warning(f"  ZIP read failed {zip_path}: {e}")
    return results


def hash_7z_rom(filepath):
    """Extract 7z to temp, hash contents. Returns [(inner_name, {"sha1", "crc"})]."""
    results = []
    tmp = os.path.join(TMP_DIR, "7z_tmp")
    try:
        os.makedirs(tmp, exist_ok=True)
        subprocess.run([SEVENZ, "x", "-y", f"-o{tmp}", filepath],
                       capture_output=True, timeout=120)
        for dirpath, _, files in os.walk(tmp):  # ROM may sit in a subfolder
            for f in sorted(files):
                results.append((f, hash_file(os.path.join(dirpath, f))))
    except Exception as e:
        logging.warning(f"  7z read failed {filepath}: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return results


# -- CHD helpers ------------------------------------------------
def chdman_verify(chd_path):
    """chdman verify. Returns (passed, message)."""
    try:
        proc = subprocess.run([CHDMAN, "verify", "-i", chd_path],
                              capture_output=True, text=True, timeout=600)
        return proc.returncode == 0, (proc.stdout + proc.stderr).strip()[:300]
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)


def chdman_extract(chd_path, out_dir):
    """Extract CHD to BIN/CUE. Returns (ok, cue_path_or_error)."""
    base = os.path.splitext(os.path.basename(chd_path))[0]
    cue = os.path.join(out_dir, base + ".cue")
    binf = os.path.join(out_dir, base + ".bin")
    try:
        proc = subprocess.run(
            [CHDMAN, "extractcd", "-i", chd_path, "-o", cue, "-ob", binf],
            capture_output=True, text=True, timeout=600)
        if proc.returncode == 0:
            return True, cue
        return False, (proc.stderr or proc.stdout).strip()[:300]
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)


def parse_cue_detailed(cue_path):
    """Parse CUE with track boundaries including INDEX 00/01 and PREGAP.
    Returns list of {num, type, pregap_sectors, index00, index01}. Offsets in bytes.
    pregap_sectors > 0 means virtual pregap (not in BIN). index00 is set when
    pause data IS in the BIN."""
    tracks = []
    cur = None
    with open(cue_path, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            m = re.match(r"TRACK\s+(\d+)\s+(\S+)", line, re.IGNORECASE)
            if m:
                if cur:
                    tracks.append(cur)
                cur = {"num": int(m.group(1)), "type": m.group(2).upper(),
                       "pregap_sectors": 0, "index00": None, "index01": None}
            m = re.match(r"PREGAP\s+(\d+):(\d+):(\d+)", line, re.IGNORECASE)
            if m and cur:
                cur["pregap_sectors"] = (int(m.group(1)) * 60 + int(m.group(2))) * 75 + int(m.group(3))
            m = re.match(r"INDEX\s+(\d+)\s+(\d+):(\d+):(\d+)", line, re.IGNORECASE)
            if m and cur:
                idx = int(m.group(1))
                offset = ((int(m.group(2)) * 60 + int(m.group(3))) * 75 + int(m.group(4))) * 2352
                if idx == 0:
                    cur["index00"] = offset
                elif idx == 1:
                    cur["index01"] = offset
    if cur:
        tracks.append(cur)
    return tracks


def hash_combined_bin_tracks(bin_path, cue_tracks):
    """Hash per-track segments from a combined BIN to match Redump per-track SHA1s.

    Redump convention:
    - If INDEX 00 present: track data starts at INDEX 00 (pregap data is in the BIN)
    - If PREGAP directive: track data starts at INDEX 01, prepend zeros for pregap
    - Track N ends where Track N+1 starts (at next track's INDEX 00 or INDEX 01)
    """
    bin_size = os.path.getsize(bin_path)
    sha1s = []
    for i, t in enumerate(cue_tracks):
        if t["index00"] is not None:
            start = t["index00"]
            virtual_pregap = 0
        else:
            start = t["index01"] or 0
            virtual_pregap = t["pregap_sectors"]
        if i + 1 < len(cue_tracks):
            nxt = cue_tracks[i + 1]
            end = nxt["index00"] if nxt["index00"] is not None else (nxt["index01"] or bin_size)
        else:
            end = bin_size
        h = hashlib.sha1()
        if virtual_pregap:
            h.update(b"\x00" * (virtual_pregap * 2352))
        with open(bin_path, "rb") as f:
            f.seek(start)
            rem = end - start
            while rem > 0:
                chunk = f.read(min(CHUNK_SIZE, rem))
                if not chunk:
                    break
                h.update(chunk)
                rem -= len(chunk)
        sha1s.append(h.hexdigest())
    return sha1s


def parse_cue(cue_path):
    """Parse CUE sheet, return list of referenced file paths."""
    tracks = []
    cue_dir = os.path.dirname(cue_path)
    try:
        with open(cue_path, "r", errors="replace") as f:
            for line in f:
                m = re.match(r'FILE\s+"([^"]+)"', line.strip(), re.IGNORECASE)
                if not m:
                    m = re.match(r'FILE\s+(\S+)', line.strip(), re.IGNORECASE)
                if m:
                    fp = os.path.join(cue_dir, m.group(1))
                    if os.path.isfile(fp) and fp not in tracks:
                        tracks.append(fp)
    except Exception as e:
        logging.warning(f"  CUE parse failed {cue_path}: {e}")
    return tracks


# -- Name normalization -----------------------------------------
def norm(name):
    """Normalize game name for fuzzy matching."""
    n = name.lower()
    n = re.sub(r"\s*\(.*?\)", "", n)     # strip parentheticals
    n = re.sub(r"[^a-z0-9]", "", n)      # alphanumeric only
    return n


def find_dat_entry(game_name, dat_games):
    """Find a DAT entry by exact name, then fuzzy."""
    if game_name in dat_games:
        return game_name, dat_games[game_name]
    gn = norm(game_name)
    for dn, dv in dat_games.items():
        if norm(dn) == gn:
            return dn, dv
    return None, None


# -- Cartridge audit --------------------------------------------
def audit_cartridge(sys_name, rom_files, dat_games, sha1_idx, crc_idx):
    res = {"system": sys_name, "type": "cartridge", "total": len(rom_files),
           "verified": [], "unverified": [], "name_mismatch": [], "errors": []}
    for rpath in rom_files:
        fname = os.path.basename(rpath)
        base = os.path.splitext(fname)[0]
        ext = os.path.splitext(fname)[1].lower()
        try:
            if ext == ".zip":
                contents = hash_zip_rom(rpath)
            elif ext == ".7z":
                contents = hash_7z_rom(rpath)
            else:
                contents = [(fname, hash_file(rpath))]
            if not contents:
                res["errors"].append({"file": fname, "error": "Could not read"})
                continue
            matched = False
            for inner_name, hashes in contents:
                sha1 = hashes.get("sha1", "")
                crc = hashes.get("crc", "")
                if sha1 in sha1_idx:
                    dat_game, dat_rom = sha1_idx[sha1]
                    exp = os.path.splitext(dat_rom)[0]
                    if norm(base) == norm(exp):
                        res["verified"].append({"file": fname, "dat_game": dat_game})
                    else:
                        res["name_mismatch"].append({"file": fname, "dat_game": dat_game,
                                                     "canonical": dat_rom})
                    matched = True
                    break
                if crc in crc_idx:
                    dat_game, dat_rom = crc_idx[crc]
                    res["verified"].append({"file": fname, "dat_game": dat_game, "note": "CRC"})
                    matched = True
                    break
            if not matched:
                res["unverified"].append({"file": fname, "sha1": sha1, "crc": crc})
        except Exception as e:
            res["errors"].append({"file": fname, "error": str(e)})
            logging.error(f"  Error on {rpath}: {e}")
    return res


# -- Disc audit -------------------------------------------------
def audit_disc(sys_name, config, rom_files, dat_games, skip_tier3):
    verify = config.get("verify", "chd")
    game_files = dedupe_disc_files(rom_files)
    res = {"system": sys_name, "type": "disc", "total": len(game_files),
           "verified": [], "unverified": [], "bad_dump": [],
           "integrity_fail": [], "filename_only": [], "errors": []}
    for rpath in game_files:
        fname = os.path.basename(rpath)
        base = os.path.splitext(fname)[0]
        ext = os.path.splitext(fname)[1].lower()
        try:
            # Unverifiable formats
            if ext in (".pbp", ".rvz", ".gcz", ".cso") or verify == "filename":
                dat_name, entry = find_dat_entry(base, dat_games)
                if entry:
                    res["filename_only"].append({"file": fname, "detail": f"Name matches: {dat_name}"})
                else:
                    res["unverified"].append({"file": fname, "detail": f"No DAT match ({ext})"})
                continue

            # CHD
            if ext == ".chd":
                logging.info(f"  [{sys_name}] chdman verify: {fname}")
                ok, msg = chdman_verify(rpath)
                if not ok:
                    res["integrity_fail"].append({"file": fname, "error": msg})
                    continue
                if skip_tier3:
                    dat_name, entry = find_dat_entry(base, dat_games)
                    if entry:
                        res["verified"].append({"file": fname, "detail": f"Integrity OK, name matches: {dat_name}"})
                    else:
                        res["unverified"].append({"file": fname, "detail": "Integrity OK, no DAT name match"})
                    continue
                logging.info(f"  [{sys_name}] extract+hash: {fname}")
                extract_dir = os.path.join(TMP_DIR, "chd_ext")
                os.makedirs(extract_dir, exist_ok=True)
                try:
                    ok, cue_or_err = chdman_extract(rpath, extract_dir)
                    if not ok:
                        res["errors"].append({"file": fname, "error": f"extractcd: {cue_or_err}"})
                        continue
                    dat_name, entry = find_dat_entry(base, dat_games)
                    if not entry:
                        res["unverified"].append({"file": fname, "detail": "Integrity OK, no DAT entry for name"})
                        continue
                    dat_bins = [r for r in entry["roms"]
                                if r["name"].lower().endswith(".bin") and r["sha1"]]
                    dat_sha1s = [r["sha1"] for r in dat_bins]
                    cue_tracks = parse_cue_detailed(cue_or_err)
                    bin_files = [os.path.join(extract_dir, f)
                                 for f in os.listdir(extract_dir)
                                 if f.lower().endswith(".bin")]
                    if len(cue_tracks) == 1 and len(bin_files) == 1:
                        h = hash_file(bin_files[0], ("sha1",))
                        if h["sha1"] in set(dat_sha1s):
                            res["verified"].append({"file": fname, "detail": f"SHA1 match (single track) [{dat_name}]"})
                        else:
                            res["bad_dump"].append({"file": fname, "detail": "SHA1 mismatch (single track)"})
                    elif len(cue_tracks) > 1 and len(bin_files) == 1:
                        our_sha1s = hash_combined_bin_tracks(bin_files[0], cue_tracks)
                        if set(our_sha1s) == set(dat_sha1s):
                            res["verified"].append({"file": fname, "detail": f"All {len(dat_sha1s)} tracks match (split+pregap) [{dat_name}]"})
                        elif set(our_sha1s) & set(dat_sha1s):
                            res["bad_dump"].append({"file": fname, "detail": f"Partial: {len(set(our_sha1s) & set(dat_sha1s))}/{len(dat_sha1s)}"})
                        else:
                            # Integrity passed but per-track hashes don't match:
                            # could be a non-Redump source or pregap difference.
                            # Flag as unverified, not bad_dump.
                            res["unverified"].append({"file": fname, "detail": "Multi-track SHA1 mismatch (integrity OK, may be non-Redump source)"})
                    else:
                        our_sha1s = [hash_file(bf, ("sha1",))["sha1"] for bf in sorted(bin_files)]
                        if set(our_sha1s) == set(dat_sha1s):
                            res["verified"].append({"file": fname, "detail": f"All {len(dat_sha1s)} tracks match [{dat_name}]"})
                        else:
                            res["unverified"].append({"file": fname, "detail": f"Track hash mismatch ({len(our_sha1s)} vs {len(dat_sha1s)} DAT tracks)"})
                finally:
                    shutil.rmtree(extract_dir, ignore_errors=True)
                continue

            # CUE (BIN/CUE pairs, e.g. 3DO)
            if ext == ".cue":
                logging.info(f"  [{sys_name}] hash BIN/CUE: {fname}")
                tracks = parse_cue(rpath)
                if not tracks:
                    res["errors"].append({"file": fname, "error": "No tracks in CUE"})
                    continue
                our_sha1s = [hash_file(tf, ("sha1",))["sha1"] for tf in tracks]
                dat_name, entry = find_dat_entry(base, dat_games)
                if not entry:
                    res["unverified"].append({"file": fname, "detail": "No DAT entry"})
                    continue
                dat_bins = [r for r in entry["roms"]
                            if r["name"].lower().endswith(".bin") and r["sha1"]]
                dat_sha1s = [r["sha1"] for r in dat_bins]
                if set(our_sha1s) == set(dat_sha1s):
                    res["verified"].append({"file": fname, "detail": f"{len(dat_sha1s)} track(s) match"})
                elif set(our_sha1s) & set(dat_sha1s):
                    res["bad_dump"].append({"file": fname, "detail": "Partial match"})
                else:
                    if len(our_sha1s) != len(dat_sha1s):
                        res["unverified"].append({"file": fname, "detail": f"Track count: ours={len(our_sha1s)} DAT={len(dat_sha1s)}"})
                    else:
                        res["bad_dump"].append({"file": fname, "detail": "SHA1 mismatch"})
                continue

            # ISO
            if ext == ".iso":
                logging.info(f"  [{sys_name}] hash ISO: {fname}")
                h = hash_file(rpath, ("sha1",))
                dat_name, entry = find_dat_entry(base, dat_games)
                if not entry:
                    res["unverified"].append({"file": fname, "detail": "No DAT entry"})
                    continue
                dat_iso = [r for r in entry["roms"]
                           if r["name"].lower().endswith(".iso") and r["sha1"]]
                if any(r["sha1"] == h["sha1"] for r in dat_iso):
                    res["verified"].append({"file": fname, "detail": "SHA1 match"})
                else:
                    res["bad_dump"].append({"file": fname, "detail": "SHA1 mismatch"})
                continue

            res["unverified"].append({"file": fname, "detail": f"Unhandled format {ext}"})
        except Exception as e:
            res["errors"].append({"file": fname, "error": str(e)})
            logging.error(f"  Error on {rpath}: {e}")
    return res


# -- Reports ----------------------------------------------------
def system_report(res, dat_games=None):
    """Generate markdown report for one system."""
    lines = []
    sn = res["system"]
    t = res["total"]
    cats = [
        ("verified", "Verified"),
        ("filename_only", "Filename match"),
        ("name_mismatch", "Name mismatch"),
        ("unverified", "Unverified"),
        ("bad_dump", "Bad dump"),
        ("integrity_fail", "Integrity fail"),
        ("errors", "Error"),
    ]
    lines.append(f"# {sn} -- {t} ROMs\n")
    lines.append("| Status | Count | % |")
    lines.append("|--------|------:|--:|")
    for key, label in cats:
        c = len(res.get(key, []))
        if c:
            lines.append(f"| {label} | {c} | {c * 100 // max(t, 1)}% |")
    lines.append("")
    for key, label in cats:
        items = res.get(key, [])
        if not items or key in ("verified", "filename_only"):
            continue
        lines.append(f"## {label}\n")
        for it in items:
            det = it.get("detail", it.get("error", it.get("canonical", "")))
            lines.append(f"- `{it['file']}` -- {det}")
        lines.append("")
    if dat_games:
        usa = [g for g in dat_games if "(USA" in g]
        lines.append("## Coverage\n")
        lines.append(f"- DAT entries: {len(dat_games)}")
        lines.append(f"- DAT USA entries: {len(usa)}")
        lines.append(f"- Your collection: {t}")
        lines.append("")
    return "\n".join(lines)


# -- Main -------------------------------------------------------
def main():
    setup_logging()
    start = time.time()
    skip_tier3 = "--skip-tier3" in sys.argv

    logging.info("=" * 60)
    logging.info("ROM Library DAT Verification (read-only)")
    logging.info(f"  skip-tier3={skip_tier3}")
    logging.info("=" * 60)

    os.makedirs(REPORT_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    all_results = {}
    for sn, cfg in SYSTEMS.items():
        sys_dir = os.path.join(ROMS_DIR, sn)
        if not os.path.isdir(sys_dir):
            continue
        rom_files = scan_roms(sys_dir, cfg["type"])
        if not rom_files:
            continue
        dat_dir = REDUMP_DATS if cfg["type"] == "redump" else NOINTRO_DATS
        dat_path = find_dat_file(dat_dir, cfg["dat_searches"])
        if not dat_path:
            logging.warning(f"[{sn}] No DAT found (searched: {cfg['dat_searches']})")
            continue
        logging.info(f"[{sn}] {len(rom_files)} files, DAT: {os.path.basename(dat_path)}")
        dat_games = parse_dat(dat_path)
        logging.info(f"  DAT has {len(dat_games)} entries")

        if cfg["type"] == "nointro":
            sha1_idx, crc_idx = build_hash_index(dat_games)
            res = audit_cartridge(sn, rom_files, dat_games, sha1_idx, crc_idx)
        else:
            res = audit_disc(sn, cfg, rom_files, dat_games, skip_tier3)
        all_results[sn] = res

        with open(os.path.join(REPORT_DIR, f"{sn}.md"), "w") as f:
            f.write(system_report(res, dat_games))

        v = len(res.get("verified", []))
        fn = len(res.get("filename_only", []))
        u = len(res.get("unverified", []))
        b = len(res.get("bad_dump", []))
        i = len(res.get("integrity_fail", []))
        e = len(res.get("errors", []))
        logging.info(f"  => verified={v} filename={fn} unverified={u} bad={b} corrupt={i} err={e}")

    # Summary
    logging.info("Generating summary...")
    lines = ["# ROM Library DAT Verification Summary", "",
             f"Generated: {datetime.now().isoformat()}",
             f"Mode: {'fast (skip-tier3)' if skip_tier3 else 'full (extract+hash)'}",
             ""]
    lines.append("| System | Total | Verified | Filename | Unverified | Bad | Corrupt | Errors |")
    lines.append("|--------|------:|---------:|---------:|-----------:|----:|--------:|-------:|")
    totals = defaultdict(int)
    for sn in sorted(all_results):
        r = all_results[sn]
        t = r["total"]
        v = len(r.get("verified", []))
        fn = len(r.get("filename_only", []))
        u = len(r.get("unverified", []))
        b = len(r.get("bad_dump", []))
        i = len(r.get("integrity_fail", []))
        e = len(r.get("errors", []))
        lines.append(f"| {sn} | {t} | {v} | {fn} | {u} | {b} | {i} | {e} |")
        totals["total"] += t
        totals["verified"] += v + fn
        totals["unverified"] += u
        totals["bad"] += b + i
        totals["errors"] += e
    lines.append("")
    lines.append(f"**Totals**: {totals['total']} ROMs -- "
                 f"{totals['verified']} verified, {totals['unverified']} unverified, "
                 f"{totals['bad']} bad/corrupt, {totals['errors']} errors")
    with open(os.path.join(REPORT_DIR, "SUMMARY.md"), "w") as f:
        f.write("\n".join(lines))

    elapsed = time.time() - start
    h, m = int(elapsed // 3600), int((elapsed % 3600) // 60)
    logging.info("=" * 60)
    logging.info(f"Done in {h}h {m}m. Reports: {REPORT_DIR}")
    logging.info("=" * 60)


if __name__ == "__main__":
    main()
