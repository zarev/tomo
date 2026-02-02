import backend.gemini_cli as gemini


def test_gemini_responds_hi(monkeypatch):
    calls = []

    def fake_run(payload, api_key=None):
        calls.append(payload)
        assert payload["prompt"] == "hi"
        return {"text": "Hi there!"}

    monkeypatch.setenv("GEMINI_CLI_ENABLED", "1")
    monkeypatch.setattr(gemini, "_run_prompt", fake_run)

    result = gemini.run_simple_prompt("hi")
    assert result == "Hi there!"
    assert calls, "_run_prompt was not invoked"


def test_gemini_fetches_news(monkeypatch):
    calls = []

    def fake_run(payload, api_key=None):
        calls.append(payload)
        assert "news.ycombinator.com" in payload["prompt"]
        return {"response": "https://news.ycombinator.com/item?id=1"}

    monkeypatch.setenv("GEMINI_CLI_ENABLED", "1")
    monkeypatch.setattr(gemini, "_run_prompt", fake_run)

    result = gemini.run_simple_prompt("fetch the first result of https://news.ycombinator.com/")
    assert result == "https://news.ycombinator.com/item?id=1"
    assert calls, "_run_prompt was not invoked"
