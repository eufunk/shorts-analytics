import pytest

from shorts_analytics.classification.llm_client import LLMClient


class _FakeTextBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeTextBlock(text)]


def _make_client(mocker, response_text):
    fake_anthropic_client = mocker.Mock()
    fake_anthropic_client.messages.create.return_value = _FakeResponse(response_text)
    mocker.patch(
        "shorts_analytics.classification.llm_client.anthropic.Anthropic",
        return_value=fake_anthropic_client,
    )
    return LLMClient(api_key="fake-key", model="fake-model")


def test_complete_json_parses_plain_json(mocker):
    client = _make_client(mocker, '{"foo": "bar"}')
    result = client.complete_json("system", "user")
    assert result == {"foo": "bar"}


def test_complete_json_parses_fenced_json(mocker):
    client = _make_client(mocker, '```json\n{"foo": "bar"}\n```')
    result = client.complete_json("system", "user")
    assert result == {"foo": "bar"}


def test_complete_json_raises_on_invalid_json(mocker):
    client = _make_client(mocker, "das ist kein JSON")
    with pytest.raises(ValueError):
        client.complete_json("system", "user")


def test_complete_text_returns_plain_text(mocker):
    client = _make_client(mocker, "Eine kurze Zusammenfassung.")
    result = client.complete_text("system", "user")
    assert result == "Eine kurze Zusammenfassung."
