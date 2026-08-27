"""Tests for the response-parsing logic in llm.generate.

These stub out the Anthropic client entirely -- the point is to exercise the
branches that are awkward or impossible to trigger against the live API
(a refusal, an empty response), plus the thinking-block filtering that keeps
reasoning out of the stored answer.
"""

from types import SimpleNamespace

import pytest

import llm


class FakeBlock:
    def __init__(self, type_: str, text: str = ""):
        self.type = type_
        self.text = text


class FakeMessage:
    def __init__(self, content, stop_reason="end_turn", stop_details=None):
        self.content = content
        self.stop_reason = stop_reason
        self.stop_details = stop_details
        self._request_id = "req_stub"


def stub_client(monkeypatch, message):
    """Point llm.generate at a client that returns `message` verbatim."""
    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return message

    monkeypatch.setattr(
        llm, "_client", lambda: SimpleNamespace(messages=SimpleNamespace(create=create))
    )
    return captured


def test_refusal_raises_422_with_category(monkeypatch):
    """A refusal arrives as HTTP 200, so it must be caught via stop_reason."""
    stub_client(
        monkeypatch,
        FakeMessage(
            content=[FakeBlock("text", "some partial text")],
            stop_reason="refusal",
            stop_details=SimpleNamespace(type="refusal", category="cyber"),
        ),
    )

    with pytest.raises(llm.GenerationError) as exc:
        llm.generate("a prompt that gets declined", "claude-opus-5")

    assert exc.value.status_code == 422
    assert "declined" in exc.value.message
    # the category should be surfaced, not swallowed
    assert "cyber" in exc.value.message


def test_refusal_with_no_stop_details_still_raises(monkeypatch):
    """stop_details can be absent; that must not turn into an AttributeError."""
    stub_client(
        monkeypatch,
        FakeMessage(content=[], stop_reason="refusal", stop_details=None),
    )

    with pytest.raises(llm.GenerationError) as exc:
        llm.generate("prompt", "claude-opus-5")

    assert exc.value.status_code == 422


def test_thinking_blocks_are_not_stored(monkeypatch):
    """Adaptive thinking is on by default, so the reply carries thinking blocks.

    Only the text must survive -- otherwise reasoning gets scored as the answer.
    """
    stub_client(
        monkeypatch,
        FakeMessage(
            content=[
                FakeBlock("thinking", "Let me reason about this privately..."),
                FakeBlock("text", "Paris is the capital of France."),
            ]
        ),
    )

    result = llm.generate("What is the capital of France?", "claude-opus-5")

    assert result == "Paris is the capital of France."
    assert "reason about this privately" not in result


def test_multiple_text_blocks_are_joined(monkeypatch):
    stub_client(
        monkeypatch,
        FakeMessage(
            content=[
                FakeBlock("text", "Part one. "),
                FakeBlock("thinking", "ignored"),
                FakeBlock("text", "Part two."),
            ]
        ),
    )

    assert llm.generate("prompt", "claude-opus-5") == "Part one. Part two."


def test_text_only_thinking_raises(monkeypatch):
    """A reply with no text block at all is not a usable response."""
    stub_client(
        monkeypatch,
        FakeMessage(content=[FakeBlock("thinking", "thought but never answered")]),
    )

    with pytest.raises(llm.GenerationError) as exc:
        llm.generate("prompt", "claude-opus-5")

    assert exc.value.status_code == 502
    assert "no text content" in exc.value.message


def test_max_tokens_still_returns_text(monkeypatch):
    """Truncation is logged, not fatal -- the partial answer is still returned."""
    stub_client(
        monkeypatch,
        FakeMessage(
            content=[FakeBlock("text", "a truncated answer")],
            stop_reason="max_tokens",
        ),
    )

    assert llm.generate("prompt", "claude-opus-5") == "a truncated answer"


def test_request_uses_the_model_it_was_given(monkeypatch):
    captured = stub_client(
        monkeypatch, FakeMessage(content=[FakeBlock("text", "ok")])
    )

    llm.generate("prompt text", "claude-sonnet-5")

    assert captured["model"] == "claude-sonnet-5"
    assert captured["messages"] == [{"role": "user", "content": "prompt text"}]


def test_missing_api_key_raises_503(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(llm.GenerationError) as exc:
        llm._client()

    assert exc.value.status_code == 503
    assert "ANTHROPIC_API_KEY" in exc.value.message
