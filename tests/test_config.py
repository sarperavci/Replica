import os
import json

import pytest

from replica.config import Settings


def test_validate_good_settings(monkeypatch):
    monkeypatch.setenv("TARGET_ORIGIN", "https://example.com")
    monkeypatch.setenv("REPLACEMENTS", json.dumps({"a": "b"}))
    monkeypatch.setenv("CACHE_TTL_STATIC", "86400")
    monkeypatch.setenv("CACHE_TTL_HTML", "300")

    settings = Settings()
    errs = settings.validate()
    assert errs == []


def test_validate_bad_urls(monkeypatch):
    monkeypatch.setenv("TARGET_ORIGIN", "not-a-url")

    settings = Settings()
    errs = settings.validate()
    assert any("TARGET_ORIGIN" in e for e in errs)


def test_validate_replacements_non_json(monkeypatch):
    monkeypatch.setenv("TARGET_ORIGIN", "https://example.com")
    monkeypatch.setenv("REPLACEMENTS", "not json")

    settings = Settings()
    errs = settings.validate()
    assert any("REPLACEMENTS" in e for e in errs)


def test_validate_replacements_wrong_shape(monkeypatch):
    monkeypatch.setenv("TARGET_ORIGIN", "https://example.com")
    # not a dict
    monkeypatch.setenv("REPLACEMENTS", json.dumps(["a", "b"]))

    settings = Settings()
    errs = settings.validate()
    assert any("REPLACEMENTS must be a JSON object" in e for e in errs)


def test_replacements_default_is_dict(monkeypatch):
    monkeypatch.delenv("REPLACEMENTS", raising=False)
    settings = Settings()
    assert settings.REPLACEMENTS == {}
    # A bad/list value must not become the attribute (kept as dict for .items()).
    monkeypatch.setenv("REPLACEMENTS", json.dumps(["a", "b"]))
    assert Settings().REPLACEMENTS == {}


def test_validate_rejects_negative_ttl(monkeypatch):
    monkeypatch.setenv("TARGET_ORIGIN", "https://example.com")
    monkeypatch.setenv("CACHE_TTL_HTML", "-1")
    errs = Settings().validate()
    assert any("CACHE_TTL_HTML" in e for e in errs)
