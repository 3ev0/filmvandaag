import logging

import telegram

log = logging.getLogger(__name__)


class TelegramAlertBot:
    def __init__(self, config: dict, program_name: str) -> None:
        self.config = config
        self.chat_id = config["TG_ALERT_CHANNEL"]
        self.program_name = program_name
        self.instance_name = config["TG_ALERT_INSTANCE_NAME"]
        self.bot = telegram.Bot(config["TG_ALERT_BOT_TOKEN"])
        log.info(f"TelegramAlertBot initialized: {self}")

    def __repr__(self):
        return f"TelegramAlertBot(token=<secret>, chat_id={repr(self.chat_id)}, " \
               f"program_name={repr(self.program_name)})"

    def info(self, message: str) -> None:
        icon = "\U00002139"
        self._send_message(f"{icon} {message}")

    def error(self, message: str) -> None:
        icon = "\U00002757"
        self._send_message(f"{icon} {message}")

    def warning(self, message: str) -> None:
        icon = "\U000026A0"
        self._send_message(f"{icon} {message}")

    def _send_message(self, message: str) -> None:
        idx = 0
        message = f"{self.program_name} ({self.instance_name}) | {message}"
        while idx < len(message):
            ttext = message[idx:idx + 4096]
            params = {"text": ttext, "chat_id": self.chat_id, "parse_mode": "Markdown"}
            self.bot.sendMessage(self.chat_id, ttext)
            idx += 4096