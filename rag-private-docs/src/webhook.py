"""Webhook 通知：索引完成等事件发生时，向指定 URL 发送 POST 请求。

配置：config.WEBHOOK_URL
"""
import json
import os
from typing import Any, Dict


def notify(event: str, data: Dict[str, Any]) -> bool:
    """发送 webhook 通知。

    返回 True 表示发送成功，False 表示未配置或失败。
    """
    from config import config

    url = getattr(config, "WEBHOOK_URL", "") or os.getenv("WEBHOOK_URL", "")
    if not url:
        return False

    try:
        import urllib.request
    except ImportError:
        return False

    payload = {
        "event": event,
        "data": data,
        "source": "dsh-web-rag",
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = 200 <= resp.status < 300
            if not ok:
                print(f"[warn] Webhook 返回 {resp.status}")
            return ok
    except Exception as e:
        print(f"[warn] Webhook 发送失败：{e}")
        return False


def notify_index_done(summary: Dict[str, Any]) -> None:
    """索引完成后发送通知（在 indexer 里调用）。"""
    notify("index_done", summary)
