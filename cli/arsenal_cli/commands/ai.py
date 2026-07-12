"""``arsenal ai`` — the Arsenal AI assistant.

Explains commands/tools/logs, recommends workflows and helps navigate Arsenal.
Backed by a swappable provider (local Ollama by default, or any OpenAI-compatible
API). Degrades gracefully with setup guidance when no provider is configured.
"""
from __future__ import annotations

from pathlib import Path

from .. import config, ui
from ..ai import assistant
from ..ai.provider import ProviderError, get_provider
from ..project import Project

NAME = "ai"
HELP = "ask the Arsenal AI assistant (local Ollama or API)"


def add_arguments(parser) -> None:
    parser.add_argument("prompt", nargs="*", help="your question")
    parser.add_argument("--tool", help="explain a security tool or command")
    parser.add_argument("--log", help="explain a log / findings file")
    parser.add_argument("--summarize", metavar="PROJECT",
                        help="write an executive summary into an engagement project")
    parser.add_argument("--provider", help="override provider (ollama|openai)")
    parser.add_argument("--model", help="override model")


def _project_context(proj: Project) -> str:
    """Bounded, redacted context for the summary — structured fields only (never
    raw scan output), so the prompt-injection surface stays small."""
    lines = [f"Engagement: {proj.name} · kind={proj.kind} · target={proj.target or '—'}"]
    if proj.findings:
        lines.append("Findings:")
        for f in proj.findings_sorted():
            loc = f" @ {f.target}" if f.target else ""
            ev = f" — {f.evidence}" if f.evidence else ""
            lines.append(f"- [{f.severity}] {f.title}{loc}{ev}")
    lines.append("Steps:")
    for s in proj.steps:
        lines.append(f"- {s.name}: {s.status} — {s.summary}")
    return assistant.truncate("\n".join(lines))


def _unavailable_hint(name: str) -> None:
    ui.print_status(ui.Status.WARN, f"AI provider '{name}' is not available")
    if name == "ollama":
        print("  " + ui.style("Start it with:  ollama serve   (then: ollama pull llama3)", ui.DIM))
        print("  " + ui.style("Install:        pacman -S ollama", ui.DIM))
    else:
        print("  " + ui.style("Set your API key, e.g.:  export ARSENAL_AI_KEY=sk-...", ui.DIM))
    print("  " + ui.style("Configure defaults in /etc/arsenal/arsenal.conf [ai]", ui.DIM))


def run(args) -> int:
    cfg = config.load()
    provider = get_provider(cfg, provider=args.provider, model=args.model)

    if not provider.available():
        _unavailable_hint(provider.name)
        return 1

    context = ""
    summarize = getattr(args, "summarize", None)
    if summarize:
        ppath = Path(summarize)
        if not (ppath / "arsenal.json").is_file():
            ui.print_status(ui.Status.FAIL, f"no engagement at {ppath}", "expected an arsenal.json")
            return 1
        proj = Project.load(ppath)
        prompt = assistant.summary_prompt()
        context = _project_context(proj)
        print(ui.style(f"[arsenal ai · {provider.name}] summarizing {proj.name}…", ui.DIM))
        try:
            answer = assistant.ask(provider, prompt, context)
        except ProviderError as exc:
            ui.print_status(ui.Status.FAIL, "AI request failed", str(exc))
            return 1
        proj.summary = (answer or "").strip()
        proj.save()
        print(answer or ui.style("(empty response)", ui.DIM))
        ui.print_status(ui.Status.OK, "summary saved to project",
                        "regenerate the report to include it: arsenal report " + str(ppath))
        return 0

    if args.tool:
        prompt = assistant.tool_prompt(args.tool)
    elif args.log:
        path = Path(args.log)
        if not path.is_file():
            ui.print_status(ui.Status.FAIL, f"file not found: {path}")
            return 1
        prompt = assistant.log_prompt()
        context = assistant.truncate(path.read_text(errors="replace"))
    else:
        prompt = " ".join(args.prompt).strip()
        if not prompt:
            ui.print_status(ui.Status.FAIL, "nothing to ask",
                            "provide a question, or use --tool / --log")
            return 1

    print(ui.style(f"[arsenal ai · {provider.name}]", ui.DIM))
    try:
        answer = assistant.ask(provider, prompt, context)
    except ProviderError as exc:
        ui.print_status(ui.Status.FAIL, "AI request failed", str(exc))
        return 1

    print(answer or ui.style("(empty response)", ui.DIM))
    return 0
