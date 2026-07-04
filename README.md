<!-- insert coin to continue -->

<p align="center">
  <img src="./media/hero.png" alt="batocera-skills — agent skills for running a real arcade cabinet" width="840">
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-00e5ff" alt="MIT license"></a>
  <a href="https://github.com/t3chnaztea/batocera-skills/releases"><img src="https://img.shields.io/github/v/release/t3chnaztea/batocera-skills?color=ff2e97" alt="Latest release"></a>
  <img src="https://img.shields.io/badge/skills-5-ffcc00" alt="5 skills">
  <img src="https://img.shields.io/badge/Batocera-v41%20to%20v43-8a2be2" alt="Batocera v41 to v43">
  <img src="https://img.shields.io/badge/Claude%20Code-plugin-d97706" alt="Claude Code plugin">
</p>

<p align="center">
  <b>Twelve months of babysitting a real arcade cabinet with coding agents, distilled into agent skills.</b>
</p>

> [Batocera](https://batocera.org) is a fantastic retro-gaming distro, but operating a cabinet day to day — curating a big library, aligning bezels, keeping the frontend fast, surviving upgrades — accumulates a pile of hard-won, wiki-doesn't-mention-it knowledge. This repo packages that knowledge as [Agent Skills](https://agentskills.io): focused, model-readable guides your coding agent (Claude Code and other harnesses) loads on demand when you ask it to work on your cabinet.

```
/plugin marketplace add t3chnaztea/batocera-skills
/plugin install batocera@t3chnaztea
```

## The five skills

Each is a self-contained home for one area of cabinet work. **Start with `batocera-ops`** — the others assume its connection pattern, `batocera.conf`/configgen model, and safety doctrine.

<table>
  <tr>
    <td align="center" width="33%" valign="top">
      <a href="skills/batocera-ops/SKILL.md"><b>🔌 batocera-ops</b></a><br />
      <sub>Start here. SSH in, the read-only <code>/userdata</code> model, config/log paths, the safety doctrine, and the remote verify loop (launch + screenshot, no controller).</sub>
    </td>
    <td align="center" width="33%" valign="top">
      <a href="skills/batocera-roms/SKILL.md"><b>💾 batocera-roms</b></a><br />
      <sub>ROM directories, why a game won't appear, hide-not-delete curation, multi-disc cleanup, and dump verification against No-Intro / Redump DATs.</sub>
    </td>
    <td align="center" width="33%" valign="top">
      <a href="skills/batocera-display/SKILL.md"><b>📺 batocera-display</b></a><br />
      <sub>Shaders, bezel artwork and alignment, generating missing <code>.info</code> sidecars, fixing moiré, and pinning the display mode.</sub>
    </td>
  </tr>
  <tr>
    <td align="center" width="33%" valign="top">
      <a href="skills/batocera-tuning/SKILL.md"><b>⚡ batocera-tuning</b></a><br />
      <sub>A slow/laggy frontend, the governor-stuck-in-powersave bug, overclock scoping, 3D-game rendering, and input latency.</sub>
    </td>
    <td align="center" width="33%" valign="top">
      <a href="skills/batocera-maintenance/SKILL.md"><b>🛠️ batocera-maintenance</b></a><br />
      <sub>Run jobs at boot without cron, back up <code>/userdata</code> over SSH, and survive major version upgrades.</sub>
    </td>
    <td align="center" width="33%" valign="top">
      <a href="template/SKILL.md"><b>➕ contribute</b></a><br />
      <sub>Got a hard-won lesson? Copy the template and open a PR. Original prose, host-parameterized, non-destructive.</sub>
    </td>
  </tr>
</table>

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

> Not affiliated with the Batocera project. "Batocera" is used here descriptively;
> this is an independent, community-built collection. The OS lives at
> [batocera.org](https://batocera.org) and its wiki is the canonical manual.

---

Insert coin.
