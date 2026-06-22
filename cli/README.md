# arsenal-cli

The Python implementation behind the `arsenal` command on Arsenal OS.

- Source: `arsenal_cli/` (stdlib-only foundation; optional features detect
  extras at runtime).
- On the ISO it is installed to `/usr/lib/arsenal/arsenal_cli` and invoked by
  the `/usr/local/bin/arsenal` shim (`PYTHONPATH=/usr/lib/arsenal python -m
  arsenal_cli`).

## Develop & test

```bash
cd cli
python -m unittest discover -s tests -t .     # stdlib, no deps
# or, if pytest is installed:
python -m pytest -q
```

## Subcommands (Phase 0–2)

| Command | Purpose |
|---|---|
| `arsenal` / `arsenal armory` | print the weapon registry |
| `arsenal doctor` | system health & security diagnostics |
| `arsenal reportbug` | redacted support bundle |

More commands (`update`, `ai`, `recon`/`web`/`ad`, `report`, `dashboard`,
`profile`) land in later phases.
