import os
import json

import pytest

from replica.entrypoint import validate_settings
from replica.config import Settings


def test_validate_good_settings(monkeypatch):
    monkeypatch.setenv("TARGET_ORIGIN", "https://example.com")
    monkeypatch.setenv("MY_ORIGIN", "http://localhost:8000")
    monkeypatch.setenv("REPLACEMENTS", json.dumps([{"from": "a", "to": "b"}]))
    monkeypatch.setenv("CACHE_TTL_STATIC", "86400")
    monkeypatch.setenv("CACHE_TTL_HTML", "300")

    settings = Settings()
    errs = validate_settings(settings)
    assert errs == []


def test_validate_bad_urls(monkeypatch):
    monkeypatch.setenv("TARGET_ORIGIN", "not-a-url")
    monkeypatch.setenv("MY_ORIGIN", "also-bad")

    settings = Settings()
    errs = validate_settings(settings)
    assert any("TARGET_ORIGIN" in e for e in errs)
    assert any("MY_ORIGIN" in e for e in errs)


def test_validate_replacements_non_json(monkeypatch):
    monkeypatch.setenv("TARGET_ORIGIN", "https://example.com")
    monkeypatch.setenv("MY_ORIGIN", "http://localhost:8000")
    monkeypatch.setenv("REPLACEMENTS", "not json")

    settings = Settings()
    errs = validate_settings(settings)
    assert any("REPLACEMENTS" in e for e in errs)


def test_validate_replacements_wrong_shape(monkeypatch):
    monkeypatch.setenv("TARGET_ORIGIN", "https://example.com")
    monkeypatch.setenv("MY_ORIGIN", "http://localhost:8000")
    # not a list
    monkeypatch.setenv("REPLACEMENTS", json.dumps({"from": "a"}))

    settings = Settings()
    errs = validate_settings(settings)
    assert any("REPLACEMENTS must be a JSON list" in e for e in errs)
