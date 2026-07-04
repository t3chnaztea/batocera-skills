<!-- insert coin to continue -->

# batocera-skills

**Twelve months of babysitting a real arcade cabinet with coding agents, distilled
into agent skills.**

[Batocera](https://batocera.org) is a fantastic retro-gaming distro, but
operating a cabinet day to day — curating a big library, aligning bezels,
keeping the frontend fast, surviving upgrades — accumulates a pile of
hard-won, wiki-doesn't-mention-it knowledge. This repo packages that knowledge
as [Agent Skills](https://agentskills.io): focused, model-readable guides your
coding agent (Claude Code and other harnesses) loads on demand when you ask it
to work on your cabinet.

Five skills, each a self-contained home for one area of cabinet work:

| If you want to… | Skill |
|---|---|
| Connect over SSH, understand the read-only/`/userdata` layout, find configs and logs, verify a change end-to-end | **batocera-ops** (start here) |
| Sort out ROM directories, fix games that won't appear, curate a big library by hiding not deleting, clean up multi-disc games, verify dumps | **batocera-roms** |
| Assign shaders, align and generate bezels, fix moiré, pin the display mode | **batocera-display** |
| Fix a slow/laggy frontend, the governor-stuck-in-powersave bug, overclock scoping, input latency | **batocera-tuning** |
| Run jobs at boot without cron, back up `/userdata`, upgrade between major versions | **batocera-maintenance** |

`batocera-ops` is the foundation — the others assume its connection pattern,
`batocera.conf`/configgen model, and safety doctrine.

---

## ⚠️ Read before you install

**These skills direct an agent to SSH into a real machine as `root` and change
its configuration.** That is exactly as powerful as it sounds.

- **Review the skills before installing.** They're plain Markdown; read what
  they'll do. Nothing here phones home or auto-runs — they're reference guides —
  but you are handing an agent an operating manual for a root shell.
- **Change Batocera's default password.** Batocera ships with the well-known
  default `root` / `linux`. A box you SSH into as root should not keep a
  published password. Change it (ES → System Settings → Security, or `passwd`).
- **The scripts mutate real files.** Every included script is `--dry-run`-first
  where it can delete, backs up configs/gamelists before editing, and is
  idempotent — but read the header and dry-run first anyway. They assume
  paths from a typical cabinet; adjust for yours.
- **Nothing here is destructive by design**, and the whole doctrine is
  non-destructive-first (hide don't delete, back up before edit, verify against
  ground truth). But you own the cabinet and the risk.

---

## Install

### Claude Code plugin (recommended)

```
/plugin marketplace add t3chnaztea/batocera-skills
/plugin install batocera@t3chnaztea
```

The five skills activate automatically when your prompt matches (e.g. "my SNES
bezels crop the screen", "games run slow after the update").

### Manual copy (any Claude Code, no marketplace)

Copy the skill directories into your skills folder:

```bash
git clone https://github.com/t3chnaztea/batocera-skills
cp -r batocera-skills/skills/batocera-* ~/.claude/skills/
```

### Other harnesses

Each `SKILL.md` is harness-neutral Markdown with standard Agent-Skills
frontmatter ([spec](https://agentskills.io/specification)). Drop the `skills/*`
directories wherever your agent framework discovers skills, or point it at this
repo.

---

## What's inside a skill

```
skills/batocera-<area>/
  SKILL.md            # the guide (frontmatter + body, < 500 lines)
  references/*.md     # heavy detail, loaded on demand
  scripts/*.py        # ready-to-adapt tools (dry-run-first, idempotent)
```

Skills are original prose — operational lessons, not a copy of the manual. The
[Batocera wiki](https://wiki.batocera.org) remains the canonical reference for
Batocera itself; these skills capture the parts running a cabinet teaches you
that the wiki doesn't.

## Contributing

Have a hard-won Batocera lesson? Copy [`template/SKILL.md`](template/SKILL.md)
and follow its authoring notes: original prose (no wiki paste), parameterize
anything host-specific (`$BATOCERA_HOST`, env-var secrets), non-destructive
doctrine, and show the reader how to verify the change. PRs welcome.

## Companion repos

- [batocera-toolbox](https://github.com/t3chnaztea/batocera-toolbox) — a
  couch/gamepad-friendly on-device utility (backup, ROM audit, shader picker).
- [batocera-holidays](https://github.com/t3chnaztea/batocera-holidays) — seasonal
  hide/un-hide rotation for a curated cabinet.

## Versions tested

Distilled on Batocera v41–v43 on x86_64 hardware. Batocera changes across
releases (path renames, service model, new systems); confirm version-specific
claims against `cat /usr/share/batocera/batocera.version` on your box. Commands
in these skills are read-only unless explicitly noted. When in doubt, the cabinet
is the source of truth. So is a screenshot of it running.

## License

MIT — see [LICENSE](LICENSE).

---

Insert coin.
