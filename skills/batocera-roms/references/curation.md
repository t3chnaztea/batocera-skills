# Library curation methodology

How to take a large, noisy retro library down to a focused, intentional set —
for an arcade cabinet, a kids' machine, a "just the bangers" front end — without
destroying anything. Method only; the taste is yours.

**Governing rule: hide, don't delete.** Everything below sets
`<hidden>true</hidden>` in `gamelist.xml` or edits the ES HiddenSystems list.
ROMs stay on disk; every pass is reversible by restoring that pass's backup.

## Two levers

1. **System-level (HiddenSystems).** Hide entire systems that don't fit the
   machine — for a controller-only cabinet, that's analog-primary consoles,
   keyboard-required home micros, light-gun/wheel/spinner platforms, etc. Stored
   in `es_settings.cfg` as the `HiddenSystems` list.
2. **Per-game (`<hidden>`).** Hide individual titles inside the systems you keep.
   This is where most of the work is.

### The HiddenSystems reset landmine

Rewriting the `HiddenSystems` value is destructive-by-omission: ES treats the
list as complete, so any system you *drop* from the list becomes visible again,
and any you *add* disappears wholesale. When editing it, start from the current
value and change deltas — don't hand-author a fresh list from memory, or you'll
silently un-hide a dozen systems or bury a wanted one. Back up `es_settings.cfg`
first, and remember ES rewrites it on exit (stop ES or SIGKILL-restart).

## A staged pass strategy

Big libraries curate best in independent passes, each backed up separately so
any one can roll back:

1. **System scope** — HiddenSystems for the machine's input model.
2. **Genre / input fit** — hide titles whose genre or controls don't suit the
   machine (long-session RPGs on an arcade cabinet, light-gun/trackball/wheel
   games on a stick-and-buttons panel).
3. **Cross-platform canonicalization (1G1R-style).** For a title that exists on
   several systems, keep one canonical version and hide the rest. Tier-rank the
   sources for *your* use (e.g. arcade original > 16-bit port > 8-bit port), and
   **only treat entries as duplicates when a strong signal agrees** — matching
   developer/publisher, not just a matching title. Many same-named games are
   different games (a 1987 arcade brawler vs a 1991 console platformer sharing a
   name); a title-only match will wrongly hide the wrong one. Keep an
   "ambiguous, left alone" bucket.
4. **Regional / format dedup.** Same game as `.zip` and `.7z`, or as multiple
   regional rips — keep one, hide the siblings.
5. **Top-N trim.** Cap each system at a target count of its best titles.

Between passes, verify counts via the ES API rather than trusting the edit:
`curl -s http://127.0.0.1:1234/systems/<system>/games` and count hidden vs
visible.

## Favorites are a separate list

The `<favorite>true</favorite>` flag and any "favorites" auto-collection are
independent of hidden state. Hiding a game does **not** remove it from favorites,
so a curation pass can leave orphaned favorites pointing at now-hidden games.
Sweep favorites separately after a big hide pass.

## Scripting the edits

Past a handful of flags, script it — parse `gamelist.xml` with
`xml.etree.ElementTree`, set/clear `<hidden>`, write back. Non-negotiables:

- **Back up every gamelist before writing** (`gamelist.xml.bak-<tag>`).
- **ES must be stopped** or you must SIGKILL-restart after (ES rewrites
  gamelists on clean exit; see `batocera-ops` → emulationstation reference).
- **Idempotent** — re-running should converge, not double-apply.
- **Keep the proposal.** Emit the list of what you're about to hide (rom, system,
  reason) as a CSV/markdown artifact and review it before applying. A hide is
  cheap to reverse, but a reviewed pass is cheaper than un-picking a bad one.

## Rollback

Because each pass has its own backup, rollback is per-pass:

```bash
cp gamelist.xml.bak-<tag> /userdata/roms/<system>/gamelist.xml
# then SIGKILL-restart ES so it reloads the restored file
```

Keep a one-line rollback note with each applied pass so future-you knows which
backup restores which pass.
