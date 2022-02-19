import logging

from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

log = logging.getLogger(__name__)

POLL_INTERVAL = 2.0


class FilmVandaagBot:

    def __init__(self, config: dict) -> None:
        self.updater = Updater(token=config["TG_FV_BOT_TOKEN"])
        self.updater.dispatcher.add_handler(CommandHandler(["new", "nieuw"], self.new_movies))
        self.updater.dispatcher.add_handler(CommandHandler(["best", "top", "beste"], self.top_movies))
        self.updater.dispatcher.add_handler(CommandHandler(["random", "kiesmaar"], self.random_movies))
        log.info("FilmVandaagBot initialized.")

    def start(self):
        self.updater.start_polling(poll_interval=POLL_INTERVAL)
        log.info("FilmVandaagBot started polling")

    def new_movies(self, update: Update, context: CallbackContext) -> None:
        context.bot.sendMessage(chat_id=update.effective_chat.id, text="Hier zijn de laatst toegevoegde films:")

    def top_movies(self, update: Update, context: CallbackContext) -> None:
        context.bot.sendMessage(chat_id=update.effective_chat.id, text="Hier zijn de beste films:")

    def random_movies(self, update: Update, context: CallbackContext) -> None:
        context.bot.sendMessage(chat_id=update.effective_chat.id, text="Hier heb je een film:")