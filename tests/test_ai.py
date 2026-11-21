import sys
from types import SimpleNamespace

import pytest

from devpulse import ai
from test_outputs import report


class FakeClient:
    def __init__(
        self, text="You shipped the UI.\n\nNEXT: Stop committing after midnight.", stop_reason="end_turn", error=None
    ):
        self.calls = []
        self.messages = SimpleNamespace(create=self.create)
        self._response = SimpleNamespace(
            stop_reason=stop_reason,
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        )
        self._error = error

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response


def test_split_answer():
    assert ai.split_answer("Para one.\n\nPara two.\nNEXT: Do less.") == ("Para one.\n\nPara two.", "Do less.")
    assert ai.split_answer("Just a narrative.") == ("Just a narrative.", "")


def test_prompt_holds_numbers_and_subjects_but_no_paths_or_hashes():
    r = report()
    prompt = ai.build_prompt(r)
    assert "Week 11, 2026" in prompt and "- Commits: 5" in prompt and "\napi (3 commits)" in prompt
    assert "app.py" not in prompt and "sha-" not in prompt


def test_narrate_sends_one_request_and_parses_it(monkeypatch):
    pytest.importorskip("anthropic")
    monkeypatch.setenv("DEVPULSE_MODEL", "claude-test-model")
    client = FakeClient()

    assert ai.narrate(report(), client) == ("You shipped the UI.", "Stop committing after midnight.")
    (call,) = client.calls
    assert call["model"] == "claude-test-model"
    assert call["messages"] == [{"role": "user", "content": ai.build_prompt(report())}]


def test_narrate_reports_refusals_and_api_errors(monkeypatch):
    anthropic = pytest.importorskip("anthropic")
    with pytest.raises(ai.AIUnavailable, match="declined"):
        ai.narrate(report(), FakeClient(stop_reason="refusal"))
    with pytest.raises(ai.AIUnavailable, match="no text"):
        ai.narrate(report(), FakeClient(text="  "))
    with pytest.raises(ai.AIUnavailable, match="could not reach"):
        ai.narrate(report(), FakeClient(error=anthropic.APIConnectionError(request=None)))


def test_narrate_without_the_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(ai.AIUnavailable, match="not installed"):
        ai.narrate(report())


def test_narrate_without_credentials_uses_the_real_sdk_and_fails_cleanly(monkeypatch):
    pytest.importorskip("anthropic")
    monkeypatch.delenv("ANTHROPIC_PROFILE", raising=False)  # conftest clears the keys and points HOME at a temp dir
    with pytest.raises(ai.AIUnavailable, match="no API credentials"):
        ai.narrate(report())
