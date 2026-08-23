# Secrets hygiene for agent-driven ops

These skills have an agent SSH into a real machine as `root`. The agent needs
the *capability*. It never needs the *credential*. Those are different things,
and most setups hand over both without noticing.

An agent transcript is a log file. Anything the agent reads or prints lands in
it, gets summarized into future context, and may sync to whatever service hosts
the session. A password that appears in a transcript once is not a secret
anymore.

## The exposure ladder

From worst to best. Each rung removes a place the credential can leak.

1. **Password pasted into the chat.** Never. It is now in the transcript
   forever, and in every summary of that transcript. `sshpass -p linux` typed
   into an agent session counts.
2. **Password in a file the agent opens.** The common default, and barely
   better: `cat ~/.config/batocera/env` puts it in context just as surely as
   pasting it.
3. **Credential injected without the agent seeing it.** Two good shapes here:
   `sshpass -f ~/.config/batocera/pass` reads the password from a file the
   agent never opens, and an SSH key (`ssh-copy-id root@<cabinet>`) removes
   the password from the loop entirely. The key is the better rung: Batocera
   persists `/userdata/system/.ssh`, so `authorized_keys` survives reboots
   and upgrades. This is the floor these skills assume.
4. **Credential held by a broker the agent cannot read.** The key lives with a
   separate user; the agent calls a wrapper, the wrapper connects, the agent
   gets output only. [HomelabHero](https://github.com/serversathome/homelabhero)
   productized this shape for SSH-driven homelab ops and deserves the credit.
   For a LAN-only arcade cabinet this is usually more machinery than the risk
   justifies, but it exists, and it is the right call the day the cabinet is
   reachable from anywhere you would not hand a root shell.

## Rules that hold at any rung

- **Change the default password first.** Batocera ships `root` / `linux`,
  published in every manual. Hygiene about protecting a credential the whole
  internet already knows is theater. Change it, then protect it.
- **Password file outside any repo, `chmod 600`, never committed.**
- **Never echo the credential.** Not to debug, not to "check it is set".
- **Watch your own logs.** Shell history and pasted debug output can both
  reproduce an `sshpass -p` invocation. Prefer `-f` or the key so there is
  nothing to reproduce.

## The test

Ask the agent what the root password is. The right answer is that it cannot
know. If it can answer, you are on rung 2, and one bad prompt away from rung 1.
