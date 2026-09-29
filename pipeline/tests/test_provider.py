from pathlib import Path

import pytest
import requests

from pipeline.ingest.provider import ProviderAdapter, ProviderContractError, RateBudget, require_keys


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code), response=self)

    def json(self):
        if self.payload == "bad-json":
            raise ValueError("bad json")
        return self.payload


class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append(kwargs)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def test_429_retries_with_identifying_user_agent_and_writes_snapshot(tmp_path: Path):
    session = Session([Response({}, 429), Response({"items": []})])
    sleeps = []
    adapter = ProviderAdapter(
        "fixture", "GridOracle/1.0 contact@example.invalid", tmp_path, RateBudget(99), sleeps.append, lambda: 0
    )
    payload, path = adapter.fetch_json("https://example.invalid", validator=require_keys("items"), session=session)
    assert payload == {"items": []}
    assert path.exists()
    assert session.calls[0]["headers"]["User-Agent"].startswith("GridOracle/")
    assert sleeps == [0.5]


@pytest.mark.parametrize("response", [Response("bad-json"), Response({"wrong": []})])
def test_timeout_or_malformed_payload_is_retried_then_quarantined(tmp_path: Path, response):
    session = Session([requests.Timeout("slow"), response])
    adapter = ProviderAdapter("fixture", "GridOracle/test", tmp_path, sleep=lambda _: None, random_source=lambda: 0)
    with pytest.raises((ValueError, ProviderContractError, requests.Timeout)):
        adapter.fetch_json("https://example.invalid", validator=require_keys("items"), attempts=2, session=session)
    assert list((tmp_path / "quarantine").glob("*.json"))
