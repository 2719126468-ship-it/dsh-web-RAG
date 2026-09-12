"""webhook.py 单元测试：未配置时静默，配置后正确发送。"""
import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "rag-private-docs" / "src"
sys.path.insert(0, str(SRC))

pytest.importorskip("dotenv", reason="需要 python-dotenv")


def test_notify_no_url(monkeypatch):
    from config import config
    monkeypatch.setattr(config, "WEBHOOK_URL", "")
    from webhook import notify
    assert notify("test", {}) is False


def test_notify_success(monkeypatch):
    from config import config
    monkeypatch.setattr(config, "WEBHOOK_URL", "http://example.com/hook")

    class FakeResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def fake_urlopen(req, timeout=None):
        assert req.full_url == "http://example.com/hook"
        body = json.loads(req.data.decode("utf-8"))
        assert body["event"] == "test_event"
        assert body["source"] == "dsh-web-rag"
        return FakeResp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    from webhook import notify
    assert notify("test_event", {"key": "value"}) is True


def test_notify_failure(monkeypatch):
    from config import config
    monkeypatch.setattr(config, "WEBHOOK_URL", "http://example.com/hook")

    def fail_urlopen(req, timeout=None):
        raise Exception("network down")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)

    from webhook import notify
    assert notify("test", {}) is False
