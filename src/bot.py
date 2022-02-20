import logging

from telegram import Update, ReplyKeyboardRemove, ReplyKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext, \
    ConversationHandler, MessageHandler, Filters, Defaults

import config

log = logging.getLogger(__name__)

POLL_INTERVAL = 2.0

STATE_INIT_NEWMOVIES, STREAMINGSERVICE, GENRE, IMDB_SCORE, RELEASE_DATE = range(5)


def parse_services_input(services_str: str) -> (list, list):
    """ Return (unrecognized services, recognized services) """
    errs = []
    if services_str.lower().startswith("all"):
        services = config.streaming_services
    else:
        service_strings = [ss.lower() for ss in services_str.split()]
        errs = [ss for ss in service_strings if ss not in config.streaming_services]
        services = [ss for ss in service_strings if ss in config.streaming_services]
    return errs, services


class FilmVandaagBot:

    def __init__(self, config: dict) -> None:
        self.updater = Updater(token=config["TG_FV_BOT_TOKEN"])#, defaults=Defaults(parse_mode=ParseMode.MARKDOWN_V2))
        self.updater.dispatcher.add_handler(CommandHandler(["best", "top", "beste"], self.top_movies))
        self.updater.dispatcher.add_handler(CommandHandler(["random", "kiesmaar"], self.random_movies))

        self.new_movie_conv_handler = ConversationHandler(
            entry_points=[CommandHandler(["new", "nieuw"], self.new_movies)],
            states={
                STREAMINGSERVICE: [MessageHandler(Filters.update & ~Filters.command, self.handle_input_services)]
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )

        self.updater.dispatcher.add_handler(self.new_movie_conv_handler)

        log.info("FilmVandaagBot initialized.")

    def start(self):
        self.updater.start_polling(poll_interval=POLL_INTERVAL)
        log.info("FilmVandaagBot started polling")

    def cancel(self, update: Update, context: CallbackContext) -> int:
        """Cancels and ends the conversation."""
        user = update.message.from_user
        log.info("User %s canceled the conversation.", user.first_name)
        update.message.reply_text(
            'Oke, dan niet.', reply_markup=ReplyKeyboardRemove()
        )

        return ConversationHandler.END

    def handle_input_services(self, update: Update, context: CallbackContext) -> int:
        """Store the selected services"""
        errs, services = parse_services_input(update.message.text)
        if errs:
            keys = config.streaming_services + ["any"]
            reply_keyboard = [keys]

            update.message.reply_text(
                f'Oeps, *{",".join(errs)}*? Probeer nog eens:', parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=ReplyKeyboardMarkup(
                    reply_keyboard, one_time_keyboard=True, input_field_placeholder='Streamingdienst'
                ),
            )
            return STREAMINGSERVICE

        else:
            context.user_data["services"] = services
            update.message.reply_text(
                f'Okido. Hier zijn de films voor {",".join(services)}:',
                reply_markup=ReplyKeyboardRemove(),
            )
            return ConversationHandler.END


    def new_movies(self, update: Update, context: CallbackContext) -> int:
        """Starts the conversation and asks user about streaming services"""
        keys = config.streaming_services + ["any"]
        reply_keyboard = [keys]

        update.message.reply_text(
            'Oke, laatste toegevoegde films dus. Welke streamingdienst?',
            reply_markup=ReplyKeyboardMarkup(
                reply_keyboard, one_time_keyboard=True, input_field_placeholder='Streamingdienst'
            ),
        )
        return STREAMINGSERVICE

    def top_movies(self, update: Update, context: CallbackContext) -> None:
        context.bot.sendMessage(chat_id=update.effective_chat.id, text="Hier zijn de beste films:")

    def random_movies(self, update: Update, context: CallbackContext) -> None:
        context.bot.sendMessage(chat_id=update.effective_chat.id, text="Hier heb je een film:")