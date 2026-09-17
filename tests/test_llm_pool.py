import importlib

import httpx


def test_given_rate_limited_first_key_when_chat_then_second_key_returns_json(monkeypatch):
    monkeypatch.setenv("OPENROUTER_KEYS", "key-one,key-two")
    import worker.llm_pool as pool
    pool = importlib.reload(pool)
    calls = []

    def handler(request):
        calls.append(request.headers["Authorization"])
        if request.headers["Authorization"] == "Bearer key-one":
            return httpx.Response(429)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert pool.chat_json([], client=client) == "{}"
    assert calls == ["Bearer key-one", "Bearer key-two"]
