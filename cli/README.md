# arsenal-cli

The Python implementation behind the `arsenal` command on Arsenal OS.

- Source: `arsenal_cli/` — stdlib-only foundation; optional features (PDF export
  via WeasyPrint, local/remote AI) detect their extras at runtime and degrade
  gracefully when missing.
- On the ISO it is installed to `/usr/lib/arsenal/arsenal_cli` and invoked by the
  `/usr/local/bin/arsenal` shim (`PYTHONPATH=/usr/lib/arsenal python -m
  arsenal_cli`). Bare `arsenal` prints the armory (backward compatible).

## Subcommands (all shipped)

| Command | Purpose |
|---|---|
| `arsenal` / `arsenal armory` | print the weapon registry |
| `arsenal doctor` | system health & security diagnostics |
| `arsenal update` | keyrings-first safe upgrade with rollback prep & verify |
| `arsenal reportbug` | redacted, compressed support bundle |
| `arsenal recon\|web\|ad <target>` | multi-tool workflows into engagement projects |
| `arsenal report <project>` | render Markdown / HTML / PDF |
| `arsenal profile <name>` | install a curated toolset (red/blue/forensics/reverse) |
| `arsenal ai` | AI assistant (local Ollama or OpenAI-compatible API) |
| `arsenal dashboard` | dark status dashboard (XFCE launcher, or `--tui`) |

Full flag/exit-code reference: [`../docs/commands.md`](../docs/commands.md).
Architecture: [`../docs/platform-cli.md`](../docs/platform-cli.md).

## Develop & test

```bash
cd cli
python -m unittest discover -s tests -t .     # stdlib, no deps
ruff check .                                   # lint (pyproject.toml; pinned in CI)
# or, if pytest is installed:
python -m pytest -q
```

Layout: core modules (`ui`, `prompts`, `config`, `log`, `runner`, `version`,
`project`) + `commands/`, `workflows/`, `ai/`, `report/`, `data/profiles/`.
Tests live in `tests/` (stdlib `unittest`). CI: `.github/workflows/ci-test.yml`
runs ruff + the suite + a CLI smoke + ShellCheck.
