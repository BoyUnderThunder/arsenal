# AI Assistant

`arsenal ai` explains commands, tools, logs and findings, recommends workflows
and helps navigate Arsenal. It uses a swappable provider so models/backends can
change without touching the CLI.

## Usage
```bash
arsenal ai "how do I enumerate SMB shares?"
arsenal ai --tool nmap                 # explain a tool/command
arsenal ai --log /var/log/suricata/fast.log   # explain logs/findings
arsenal ai --provider openai --model gpt-4o-mini "..."   # per-call override
```

## Providers
- **Ollama (default, local/offline):** talks to `http://127.0.0.1:11434`.
  ```bash
  pacman -S ollama && ollama serve && ollama pull llama3
  ```
- **OpenAI-compatible API:** set `provider = openai` and an API key env var.
  ```bash
  export ARSENAL_AI_KEY=sk-...
  ```

## Configuration
`/etc/arsenal/arsenal.conf` (or `~/.config/arsenal/arsenal.conf`):
```ini
[ai]
provider = ollama            ; or: openai
model = llama3
base_url = http://127.0.0.1:11434
api_key_env = ARSENAL_AI_KEY
```

## Design & privacy
- Abstraction: `arsenal_cli/ai/provider.py` defines `Provider`
  (`available()`, `chat()`); `ollama.py` and `openai_compat.py` implement it;
  `get_provider()` selects from config. Add a backend by adding a module.
- **No models or API keys are bundled.** Keys come from the environment.
- If no provider is available, `arsenal ai` prints setup guidance and exits 1
  (it never silently sends data).
- Sending logs/findings to a remote API shares that data with the provider —
  prefer local Ollama for sensitive material.
