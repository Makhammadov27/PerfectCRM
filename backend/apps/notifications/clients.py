"""Tashqi xizmatlar: Eskiz.uz SMS va Telegram Bot API."""

from __future__ import annotations

import requests
from django.conf import settings

from apps.core.models import Setting

TIMEOUT = 30


class SendError(Exception):
    """Yuborib bo'lmadi. `permanent=True` — qayta urinish foydasiz (masalan, bot bloklangan)."""

    def __init__(self, message: str, permanent: bool = False):
        super().__init__(message)
        self.permanent = permanent


class EskizClient:
    BASE = "https://notify.eskiz.uz/api"
    TOKEN_KEY = "eskiz_token"

    def __init__(self, email: str | None = None, password: str | None = None, sender: str | None = None):
        self.email = email or settings.ESKIZ_EMAIL
        self.password = password or settings.ESKIZ_PASSWORD
        self.sender = sender or settings.ESKIZ_FROM

    # Token 30 kun amal qiladi; bazada saqlanadi, 401 kelsa qayta olinadi.
    def _stored_token(self) -> str:
        row = Setting.objects.filter(key=self.TOKEN_KEY).first()
        return row.value if row else ""

    def login(self) -> str:
        if not (self.email and self.password):
            raise SendError("ESKIZ_EMAIL / ESKIZ_PASSWORD sozlanmagan", permanent=True)
        r = requests.post(f"{self.BASE}/auth/login", data={"email": self.email, "password": self.password},
                          timeout=TIMEOUT)
        if r.status_code != 200:
            raise SendError(f"Eskiz login xatosi: HTTP {r.status_code} {r.text[:200]}", permanent=r.status_code < 500)
        token = r.json()["data"]["token"]
        Setting.objects.update_or_create(key=self.TOKEN_KEY, defaults={"value": token})
        return token

    def _request(self, method: str, path: str, **kw) -> requests.Response:
        token = self._stored_token() or self.login()
        for attempt in range(2):
            r = requests.request(method, f"{self.BASE}{path}", headers={"Authorization": f"Bearer {token}"},
                                 timeout=TIMEOUT, **kw)
            if r.status_code == 401 and attempt == 0:
                token = self.login()
                continue
            return r
        return r

    def send_sms(self, phone: str, text: str) -> str:
        r = self._request("POST", "/message/sms/send",
                          data={"mobile_phone": phone, "message": text, "from": self.sender})
        if r.status_code != 200:
            raise SendError(f"Eskiz: HTTP {r.status_code} {r.text[:300]}", permanent=400 <= r.status_code < 500)
        data = r.json()
        return str(data.get("id") or data.get("data", {}).get("id") or "")

    def balance(self) -> dict:
        r = self._request("GET", "/user/get-limit")
        r.raise_for_status()
        return r.json()


class TelegramClient:
    def __init__(self, token: str | None = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN

    def call(self, method: str, http_timeout: int = TIMEOUT, **params) -> dict:
        # http_timeout — HTTP so'rov kutish vaqti; params["timeout"] esa Telegram long-polling vaqti
        if not self.token:
            raise SendError("TELEGRAM_BOT_TOKEN sozlanmagan", permanent=True)
        r = requests.post(f"https://api.telegram.org/bot{self.token}/{method}", json=params, timeout=http_timeout)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not data.get("ok"):
            desc = data.get("description", r.text[:200])
            # 403 — foydalanuvchi botni bloklagan; 400 — chat topilmadi
            raise SendError(f"Telegram: {desc}", permanent=r.status_code in (400, 403))
        return data["result"]

    def send_message(self, chat_id: int, text: str, **extra) -> str:
        result = self.call("sendMessage", chat_id=chat_id, text=text, **extra)
        return str(result.get("message_id", ""))
