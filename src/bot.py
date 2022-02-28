import logging

from telegram import Update, InlineKeyboardMarkup, ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, ParseMode, Bot, TelegramError, InlineKeyboardButton
from telegram.utils.helpers import escape_markdown
from telegram.ext import Updater, CommandHandler, CallbackContext, \
    ConversationHandler, MessageHandler, Filters, Defaults, CallbackQueryHandler

import config
import scraper

log = logging.getLogger(__name__)

POLL_INTERVAL = 2.0

STREAMINGSERVICE, GENRES, MINSCORE, RELEASEYEAR = range(4)


def parse_services_input(services_str: str) -> (list, list):
    """ Return (unrecognized services, recognized services) """
    errs = []
    if services_str.lower() in ["all", "any"]:
        services = config.streaming_services
    else:
        service_strings = [ss.lower() for ss in services_str.split()]
        errs = [ss for ss in service_strings if ss not in config.streaming_services]
        services = [ss for ss in service_strings if ss in config.streaming_services]
    return errs, services


def handle_bot_exception(u: object, context: CallbackContext) -> None:
    raise context.error


class FilmVandaagBot:

    def __init__(self, config: dict, scraper: scraper.FilmVandaagScraper) -> None:
        self.updater = Updater(token=config["TG_FV_BOT_TOKEN"])
        self.updater.dispatcher.add_error_handler(handle_bot_exception)
        self.scraper = scraper
        self.search_movie_conv_handler = ConversationHandler(
            entry_points=[CommandHandler(["zoek"], self.search_movies)],
            states={
                GENRES: [CallbackQueryHandler(self.handle_input_genres)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
        )
        self.new_movie_conv_handler = ConversationHandler(
            entry_points=[CommandHandler(["new", "nieuw"], self.new_movies)],
            states={
                STREAMINGSERVICE: [MessageHandler(Filters.update & ~Filters.command, self.handle_input_services)],
            },
            fallbacks=[CommandHandler('cancel', self.cancel)]
        )
        self.config = config
        self.updater.dispatcher.add_handler(self.new_movie_conv_handler)
        self.updater.dispatcher.add_handler(self.search_movie_conv_handler)
        log.info("FilmVandaagBot initialized.")

    def start(self):
        self.updater.start_polling(poll_interval=POLL_INTERVAL)
        log.info("FilmVandaagBot started polling")

    def search_movies(self, update: Update, context: CallbackContext) -> int:
        """Starts the conversation and asks user about streaming services"""
        log.info(f"Search_movies conversation started by user {update.message.from_user}.")
        buttons = config.genres + ["overig"]
        keyboard = [[InlineKeyboardButton(b, callback_data=str(b))] for b in buttons]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Oke, we gaan een film zoeken. Welke genres?", reply_markup=reply_markup)
        return GENRES

    def handle_input_genres(self, update: Update, context: CallbackContext) -> int:
        pass

    def handle_input_min_score(self, update: Update, context: CallbackContext) -> int:
        pass

    def handle_input_release_year(self, update: Update, context: CallbackContext) -> int:
        pass

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
            movies = []
            update.message.reply_text(
                f'Okido. Momentje. Ik haal de films op voor {",".join(services)}...',
                reply_markup=ReplyKeyboardRemove(),
            )
            for service in services:
                movies += self.scraper.scrape_new_movies(service, self.config["NEW_MOVIES_THRESHOLD_DAYS"])
            movies = [m for m in sorted(movies, key=lambda movie: movie["rating"], reverse=True)
                      if m["rating"] >= self.config["NEW_MOVIES_MIN_RATING"]]
            update.message.reply_text(
                f'Deze films zijn de laatste {self.config["NEW_MOVIES_THRESHOLD_DAYS"]} dagen toegevoegd '
                f'en hebben een score van {self.config["NEW_MOVIES_MIN_RATING"]} of hoger.',
                reply_markup=ReplyKeyboardRemove(),
            )
            reply = ""
            for m in movies:
                reply += f"*{escape_markdown(m['title'], version=2)}* on {m['service']} " \
                         f"imdb:*{escape_markdown(str(m['rating']), version=2)}*\n"
            if not reply:
                reply = f"Geen nieuwe films gevonden in afgelopen {self.config['NEW_MOVIES_THRESHOLD_DAYS']} dagen."

            update.message.reply_text(reply, reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.MARKDOWN_V2)
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