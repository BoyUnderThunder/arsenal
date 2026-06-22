# Arsenal Documentation

Arsenal is a white-hat security OS (Arch + BlackArch) with a cohesive platform
CLI on top of a curated toolkit.

## Contents
- [Commands reference](commands.md) — every `arsenal` subcommand.
- [Platform CLI overview](platform-cli.md) — architecture of the CLI.
- [Weapon framework](weapon-framework.md) — the Armory: weapon → tool aliases.
- [Hardening](hardening.md) — the Fortress: kernel, AppArmor, firewall, LUKS.
- [Workflow engine](workflows.md) — `recon` / `web` / `ad` orchestration.
- [AI assistant](ai.md) — `arsenal ai` providers & configuration.
- [Update & rollback](update.md) — `arsenal update` process.
- [Troubleshooting](troubleshooting.md) — diagnostics, logs, support bundles.

## Quick start
```bash
arsenal                 # the armory (weapon registry)
arsenal doctor          # health & security diagnostics
arsenal recon <target>  # run a recon workflow into an engagement project
arsenal report <proj>   # render Markdown/HTML/PDF
arsenal dashboard       # dark status dashboard (XFCE)
```

## Building Arsenal
The ISO is built by `build.sh` (archiso + BlackArch) and CI
(`.github/workflows/build-iso.yml`); see the repo [README](../README.md).
The CLI source lives in `cli/` and is tested by `ci-test.yml`.
