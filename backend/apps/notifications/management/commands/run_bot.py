"""Telegram botni ishga tushiradi va navbatdagi xabarlarni (Telegram + SMS) yuboradi.

    python manage.py run_bot
"""

import logging
import time

from django.core.management.base import BaseCommand

from apps.notifications.bot import CenterBot
from apps.notifications.clients import SendError, TelegramClient
from apps.notifications.services import send_pending

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ota-onalar Telegram botini ishga tushiradi (long polling) va xabarlar navbatini yuboradi"

    def handle(self, *args, **opts):
        api = TelegramClient()
        bot = CenterBot(api)
        me = api.call("getMe")
        self.stdout.write(self.style.SUCCESS(f"Bot ishga tushdi: @{me['username']}"))
        offset = None
        while True:
            try:
                params = {"timeout": 20, "allowed_updates": ["message", "callback_query"]}
                if offset is not None:
                    params["offset"] = offset
                for upd in api.call("getUpdates", http_timeout=30, **params):
                    offset = upd["update_id"] + 1
                    try:
                        bot.handle_update(upd)
                    except Exception:
                        log.exception("Update xatosi: %s", upd.get("update_id"))
                send_pending()
            except KeyboardInterrupt:
                self.stdout.write("To'xtatildi")
                return
            except (SendError, OSError) as exc:
                log.warning("Tarmoq xatosi: %s — 5 soniyadan keyin qayta urinish", exc)
                time.sleep(5)
