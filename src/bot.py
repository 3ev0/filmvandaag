import datetime
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
CONV_TIMEOUT=30.0

STREAMINGSERVICE, GENRES, IMDB_SCORE, RELEASE_YEAR = range(4)
RESP_TO_IMDB_SCORE, RESP_QUIT = [f"sc_{n}" for n in range(2)]


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
                GENRES: [
                    CallbackQueryHandler(self.cancel, pattern='^' + str(RESP_QUIT) + '$'),
                    CallbackQueryHandler(self.handle_input_genres)
                ],
                IMDB_SCORE: [
                    CallbackQueryHandler(self.cancel, pattern='^' + str(RESP_QUIT) + '$'),
                    CallbackQueryHandler(self.handle_input_imdb_score)
                ],
                RELEASE_YEAR: [
                    CallbackQueryHandler(self.cancel, pattern='^' + str(RESP_QUIT) + '$'),
                    CallbackQueryHandler(self.handle_input_release_year)
                ],
                ConversationHandler.TIMEOUT: [
                    CallbackQueryHandler(self.handle_timeout)
                ]

            },
            fallbacks=[CommandHandler('cancel', self.cancel)],
            conversation_timeout=CONV_TIMEOUT
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
        button_texts = config.genres + ["overig"]
        next_button = InlineKeyboardButton("volgende >", callback_data=str(RESP_TO_IMDB_SCORE))
        cancel_button = InlineKeyboardButton("Stop maar", callback_data=RESP_QUIT)
        keyboard = [[next_button]] + [[InlineKeyboardButton(b, callback_data=str(b))] for b in button_texts]
        keyboard += [[cancel_button]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Oke, ik ga films zoeken. Welke genres?", reply_markup=reply_markup)
        return GENRES

    def handle_input_genres(self, update: Update, context: CallbackContext) -> int:
        if "selected_genres" not in context.user_data:
            context.user_data["selected_genres"] = []
        next_button = InlineKeyboardButton("volgende >", callback_data=str(RESP_TO_IMDB_SCORE))
        cancel_button = InlineKeyboardButton("Stop maar", callback_data=RESP_QUIT)
        query = update.callback_query
        resp = query.data
        query.answer()
        if resp == str(RESP_TO_IMDB_SCORE):
            keyboard = []
            keyboard.append([InlineKeyboardButton(f"> {n}", callback_data=str(n)) for n in [0, 5, 6, 7, 8]])
            keyboard.append([cancel_button])
            reply_markup = InlineKeyboardMarkup(keyboard)
            genres_text = ', '.join("*" + sg + "*" for sg in context.user_data['selected_genres'])
            query.edit_message_text(
                text=f"Genres: {genres_text}\.\nWat moet de IMDB\-score zijn?",
                reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2
            )
            return IMDB_SCORE
        else: # genre selected
            context.user_data["selected_genres"].append(resp)
            log.info(f"Added genre selection {resp}")
            button_texts = [t for t in config.genres if t not in (context.user_data["selected_genres"]+ ["overig"])]
            keyboard = [[next_button]] + [[InlineKeyboardButton(b, callback_data=str(b))] for b in button_texts]
            reply_markup = InlineKeyboardMarkup(keyboard)
            genres_text = ', '.join("*" + sg + "*" for sg in context.user_data['selected_genres'])
            query.edit_message_text(
                text=f"Genres: {genres_text}\. Nog meer?",
                                     reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2
            )
            return GENRES

    def handle_input_imdb_score(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        resp = query.data
        log.info(f"callback handle_input_imdb_score with query data: {resp}")
        cancel_button = InlineKeyboardButton("Stop maar", callback_data=RESP_QUIT)
        context.user_data["min_imdb_score"] = resp
        query.answer()
        cur_year = datetime.datetime.today().year
        keyboard = [[InlineKeyboardButton("boeit niet", callback_data=str(1900))]]
        keyboard += [[InlineKeyboardButton(f"> {n}", callback_data=str(n))] for n in [cur_year-20, cur_year-5, cur_year-2]]
        keyboard += [[InlineKeyboardButton(str(cur_year), callback_data=str(cur_year))]]
        keyboard.append([cancel_button])
        reply_markup = InlineKeyboardMarkup(keyboard)
        genres_text = ', '.join("*" + sg + "*" for sg in context.user_data['selected_genres'])
        imdb_score_text = "* \> " + resp + "*"
        query.edit_message_text(
            text=f"Genres: {genres_text}\.\nIMDB\-score: {imdb_score_text}\nHoe recent moet de film zijn?",
            reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2
        )
        return RELEASE_YEAR

    def handle_input_release_year(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        resp = query.data
        log.info(f"callback handle_input_release_year with query data: {resp}")
        context.user_data["min_release_year"] = resp
        query.answer()
        genres_text = "Genres: " + ', '.join("*" + sg + "*" for sg in context.user_data['selected_genres'])
        imdb_score_text = "IMDB\-score: * \> " + context.user_data["min_imdb_score"] + "*"
        release_year_text = f"Uitgekomen na: *{resp}*"
        query.edit_message_text(
            text=f"{genres_text}\n{imdb_score_text}\n{release_year_text}\nIk ben aan het zoeken\.\.\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        movies = {}
        movies_text = ""
        query.edit_message_text(
            text=f"{genres_text}\n{imdb_score_text}\n{release_year_text}\nDeze heb ik gevonden:",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END

    def handle_timeout(self,  update: Update, context: CallbackContext) -> int:
        resp = update.callback_query.data
        log.info(f"callback timeout with query data: {resp}")
        update.message.reply_text(
            'Duurt te lang...', reply_markup=ReplyKeyboardRemove()
        )

        return ConversationHandler.END


    def cancel(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        resp = query.data
        user = query.from_user
        log.info(f"callback cancel with query data: {resp}")
        log.info("User %s canceled the conversation.", user.first_name)
        query.edit_message_text(
            'Oke, dan niet.'
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