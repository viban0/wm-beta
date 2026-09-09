"""Shared reliability helpers for the Kwangwoon Telegram bots."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def create_session() -> requests.Session:
    """Create one polite, retrying HTTP session for a bot run."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "KW-Alert-Bot/2.0 (+https://github.com/viban0/web-monitor)"
    })
    return session


def send_telegram(
    session: requests.Session, message: str, buttons: dict | None = None,
    *, disable_notification: bool = False,
) -> bool:
    """Send a Telegram message and report whether Telegram accepted it.

    Returning a boolean is intentional: callers must not mark an alert as seen
    when delivery failed.
    """
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("⚠️ Telegram credentials are missing; notification was not sent.")
        return False

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "disable_notification": disable_notification,
    }
    if buttons:
        payload["reply_markup"] = json.dumps(buttons, ensure_ascii=False)

    try:
        response = session.post(
            f"https://api.telegram.org/bot{token}/sendMessage", data=payload, timeout=15
        )
        response.raise_for_status()
        return True
    except requests.RequestException as error:
        print(f"⚠️ Telegram delivery failed: {error}")
        return False


def read_state(path: str) -> set[str]:
    try:
        return {line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()}
    except FileNotFoundError:
        return set()


def write_state(path: str, identifiers: Iterable[str]) -> None:
    """Atomically replace state so interrupted jobs cannot leave a blank file."""
    target = Path(path)
    values = list(dict.fromkeys(identifiers))
    content = "\n".join(values) + ("\n" if values else "")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
        handle.write(content)
        temp_path = handle.name
    os.replace(temp_path, target)
