# DAT verification (No-Intro / Redump)

Confirming your ROMs are *known-good dumps* — the right bytes, not just the right
filename. A file named `Chrono Trigger (USA).sfc` can be a bad dump, a hack, or a
truncated download; the only way to know is to hash it and match against a
reference DAT.

Companion script: [../scripts/dat-verify.py](../scripts/dat-verify.py). It reads
Logiqx XML DATs and reports per-system verified / unverified / bad-dump /
corrupt counts, plus a summary. Read-only: it never downloads or modifies ROMs.

## Two DAT families

- **No-Intro** — cartridge systems (NES, SNES, GB/GBC/GBA, Genesis, etc.).
  Verification is a straight hash match: SHA1 (or CRC32 fallback) of the ROM
  against the DAT. For zipped ROMs, hash the *inner* file, not the zip.
- **Redump** — disc systems (PSX, Saturn, Sega CD, Dreamcast, 3DO, Neo Geo CD…).
  Discs are stored as `.chd` (compressed) or `.bin`/`.cue`. Verification is
  extract-then-hash per track, matched against Redump's per-track SHA1s.

Put DATs somewhere on `/userdata` (e.g. `/userdata/system/dats/no-intro/` and
`.../redump/`) and point the script at them.

## Verification tiers (discs)

1. **Tier 1 — integrity.** `chdman verify` on a `.chd` confirms the container
   isn't corrupt. Fast; catches truncated/damaged files.
2. **Tier 2 — name match.** The extracted/contained title matches a DAT entry by
   name. Weak (names lie) but cheap.
3. **Tier 3 — content hash.** Extract the CHD to `.bin`/`.cue`, hash each track,
   and match the set against the DAT's per-track SHA1s. This is the real proof.
   Slow (extracts every disc); make it optional (`--skip-tier3`) for a fast pass.

## The Redump per-track pregap convention

Multi-track discs are the fiddly part. To reproduce Redump's per-track SHA1s from
a combined `.bin`, you must split on the CUE's INDEX/PREGAP boundaries the way
Redump does:

- If a track has **INDEX 00**, its data starts at INDEX 00 (the pregap/pause
  data is present in the BIN).
- If a track has a **PREGAP** directive (no INDEX 00), its data starts at
  INDEX 01 and you must **prepend zero bytes** for the virtual pregap
  (`pregap_sectors * 2352`).
- A track ends where the next track's earliest index begins.

`dat-verify.py` implements exactly this in `hash_combined_bin_tracks()`. Get it
wrong and every multi-track disc reads as a mismatch.

## Known limits — don't over-trust a "fail"

- **GD-ROM discs (Dreamcast) in CHD can't be cleanly hash-verified** against
  Redump the naive way — GD-ROM geometry and the CHD packing don't line up with
  a straight per-track BIN hash. A "mismatch" here is often the method, not the
  dump. Treat Dreamcast Tier-3 results as advisory.
- **Sega CD CDDA (audio) tracks** frequently mismatch due to offset/pregap
  handling differences between rippers even for good dumps. Integrity (Tier 1) is
  the reliable signal there.
- **Non-Redump sources** (a good dump from a different provenance) can fail a
  per-track match while being perfectly playable. When integrity passes but the
  content hash doesn't, classify as *unverified*, not *bad dump* — don't tell a
  user to re-download a working game.

## Reading the output

The script buckets each ROM: **verified** (hash match), **filename** (name-only,
unverifiable format), **unverified** (no DAT match / integrity-OK-but-hash-
mismatch), **bad dump** (hash mismatch on a verifiable format), **corrupt**
(failed integrity), **error**. Act on *bad dump* and *corrupt*; investigate
*unverified* with the known-limits above in mind before concluding anything.

## Environment

The cabinet already has the tools: `chdman` (under the MAME dir), `7z`, and
Python 3. No compiler, so pure-Python + these binaries only. DAT files you supply.
