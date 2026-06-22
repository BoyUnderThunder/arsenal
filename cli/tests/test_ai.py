import io
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

from arsenal_cli import config, ui
from arsenal_cli.ai import assistant
from arsenal_cli.ai import ollama as ollama_mod
from arsenal_cli.ai import openai_compat as openai_mod
from arsenal_cli.ai.provider import Provider, ProviderError, get_provider
from arsenal_cli.commands import ai as ai_cmd


class FakeProvider(Provider):
    name = "fake"

    def __init__(self, ok=True, reply="hello from AI"):
        self._ok = ok
        self._reply = reply
        self.seen = None

    def available(self):
        return self._ok

    def chat(self, messages):
        self.seen = messages
        return self._reply


class TestFactory(unittest.TestCase):
    def test_default_is_ollama(self):
        prov = get_provider(config.load())
        self.assertEqual(prov.name, "ollama")

    def test_openai_selected(self):
        prov = get_provider(config.load(), provider="openai")
        self.assertEqual(prov.name, "openai")


class TestProviders(unittest.TestCase):
    def test_ollama_chat_parses(self):
        with mock.patch.object(ollama_mod, "http_json",
                               return_value={"message": {"content": "  hi  "}}):
            out = ollama_mod.OllamaProvider("http://x:11434", "m").chat([])
        self.assertEqual(out, "hi")

    def test_ollama_available_false_on_error(self):
        with mock.patch.object(ollama_mod, "http_json", side_effect=ProviderError("down")):
            self.assertFalse(ollama_mod.OllamaProvider("http://x:11434", "m").available())

    def test_openai_chat_parses(self):
        payload = {"choices": [{"message": {"content": "answer"}}]}
        with mock.patch.object(openai_mod, "http_json", return_value=payload):
            out = openai_mod.OpenAICompatProvider("https://api", "m", "key").chat([])
        self.assertEqual(out, "answer")

    def test_openai_available_needs_key(self):
        self.assertFalse(openai_mod.OpenAICompatProvider("https://api", "m", "").available())
        self.assertTrue(openai_mod.OpenAICompatProvider("https://api", "m", "k").available())


class TestAssistant(unittest.TestCase):
    def test_ask_builds_messages(self):
        fp = FakeProvider()
        out = assistant.ask(fp, "what is nmap?", context="ctx")
        self.assertEqual(out, "hello from AI")
        self.assertEqual(fp.seen[0]["role"], "system")
        self.assertIn("ctx", fp.seen[1]["content"])
        self.assertIn("nmap", fp.seen[1]["content"])


class TestAICommand(unittest.TestCase):
    def setUp(self):
        ui.set_color(False)

    def test_run_with_available_provider(self):
        fp = FakeProvider(ok=True, reply="nmap scans networks")
        with mock.patch.object(ai_cmd, "get_provider", return_value=fp):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = ai_cmd.run(types.SimpleNamespace(
                    prompt=["explain", "nmap"], tool=None, log=None, provider=None, model=None))
        self.assertEqual(rc, 0)
        self.assertIn("nmap scans networks", buf.getvalue())

    def test_run_unavailable_provider(self):
        fp = FakeProvider(ok=False)
        with mock.patch.object(ai_cmd, "get_provider", return_value=fp):
            with redirect_stdout(io.StringIO()):
                rc = ai_cmd.run(types.SimpleNamespace(
                    prompt=["hi"], tool=None, log=None, provider=None, model=None))
        self.assertEqual(rc, 1)

    def test_run_empty_prompt(self):
        fp = FakeProvider(ok=True)
        with mock.patch.object(ai_cmd, "get_provider", return_value=fp):
            with redirect_stdout(io.StringIO()):
                rc = ai_cmd.run(types.SimpleNamespace(
                    prompt=[], tool=None, log=None, provider=None, model=None))
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
