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
CONV_TIMEOUT = 30.0
MOVIE_SEARCH_BATCH_SIZE = 20


STREAMINGSERVICE, GENRES, IMDB_SCORE, RELEASE_YEAR, SHOW_MOVIES = range(5)
RESP_TO_IMDB_SCORE, RESP_QUIT, RESP_MORE = [f"sc_{n}" for n in range(3)]


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
                SHOW_MOVIES: [
                    CallbackQueryHandler(self.cancel, pattern='^' + str(RESP_QUIT) + '$'),
                    CallbackQueryHandler(self.show_more_movies)
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
        cancel_button = InlineKeyboardButton("Stop maar", callback_data=RESP_QUIT)
        keyboard = [[InlineKeyboardButton(b, callback_data=str(b))] for b in button_texts]
        keyboard += [[cancel_button]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Oke, ik ga films zoeken. Welke genres?", reply_markup=reply_markup)
        return GENRES

    def handle_input_genres(self, update: Update, context: CallbackContext) -> int:
        if "selected_genres" not in context.user_data:
            context.user_data["selected_genres"] = []
        cancel_button = InlineKeyboardButton("Stop maar", callback_data=RESP_QUIT)
        query = update.callback_query
        resp = query.data
        query.answer()
        keyboard = [[InlineKeyboardButton("boeiend", callback_data=str(0))]]
        context.user_data["selected_genres"].append(resp)
        log.info(f"Added genre selection {resp}")
        keyboard.append([InlineKeyboardButton(f"{n}+", callback_data=str(n)) for n in [5, 6, 7, 8]])
        keyboard.append([cancel_button])
        reply_markup = InlineKeyboardMarkup(keyboard)
        genre_text = f"*{context.user_data['selected_genres']}*"
        query.edit_message_text(
            text=f"Genre: {genre_text}\.\nWat moet de IMDB\-score zijn?",
            reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2
        )
        return IMDB_SCORE

    def handle_input_imdb_score(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        resp = query.data
        log.info(f"callback handle_input_imdb_score with query data: {resp}")
        cancel_button = InlineKeyboardButton("Stop maar", callback_data=RESP_QUIT)
        context.user_data["min_imdb_score"] = resp
        query.answer()
        cur_year = datetime.datetime.today().year
        keyboard = [[InlineKeyboardButton("boeiend", callback_data=str(1900))]]
        keyboard += [[InlineKeyboardButton(f"> {n}", callback_data=str(n))] for n in [cur_year-20, cur_year-5, cur_year-2]]
        keyboard += [[InlineKeyboardButton(str(cur_year), callback_data=str(cur_year))]]
        keyboard.append([cancel_button])
        reply_markup = InlineKeyboardMarkup(keyboard)
        genre_text = f"*{context.user_data['selected_genres']}*"
        imdb_score_text = "*" + resp + "\+*"
        query.edit_message_text(
            text=f"Genres: {genre_text}\.\nIMDB\-score: {imdb_score_text}\nHoe recent moet de film zijn?",
            reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2
        )
        return RELEASE_YEAR

    def handle_input_release_year(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        resp = query.data
        log.info(f"callback handle_input_release_year with query data: {resp}")
        context.user_data["min_release_year"] = resp
        query.answer()

        movies_generator = self.scraper.search_movies(services=config.streaming_services,
                                            genres=context.user_data["selected_genres"],
                                            imdb_score=(context.user_data["min_imdb_score"], None),
                                            release_year=(context.user_data["min_release_year"], None),
                                            votes_threshold=self.config["IMDB_VOTES_THRESHOLD"])
        context.user_data["movies_generator"] = movies_generator
        context.user_data["search_url"] = self.scraper.get_search_movies_browser_url(services=config.streaming_services,
                                            genres=context.user_data["selected_genres"],
                                            imdb_score=(context.user_data["min_imdb_score"], None),
                                            release_year=(context.user_data["min_release_year"], None))
        genres_text = "Genres: " + ', '.join("*" + sg + "*" for sg in context.user_data['selected_genres'])
        imdb_score_text = "IMDB\-score: *" + context.user_data["min_imdb_score"] + "\+*"
        release_year_text = f"Uitgekomen na: *{resp}*"
        search_url_text = f"[Filmvandaag\.nl]({context.user_data['search_url']})"
        reply_text = f"{genres_text}\n{imdb_score_text}\n{release_year_text}\n{search_url_text}"
        log.debug(reply_text)
        query.edit_message_text(
            text=reply_text,
            reply_markup=None,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True
        )

        return self.show_more_movies(update, context)


    def show_more_movies(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        resp = query.data
        log.info(f"callback show_more_movies with query data: {resp}")


        movielines = []
        thereismore = True
        try:
            for i in range(MOVIE_SEARCH_BATCH_SIZE):
                movie = next(context.user_data["movies_generator"])
                movie_line = f"[*{escape_markdown(movie['title'], version=2)}*]({movie['url']})"
                movie_line += f" \({movie['release_year']}\)"
                movie_line += f" imdb *{escape_markdown(str(movie['rating']), version=2)}*"
                movielines.append(movie_line)
        except StopIteration: # out of movies
            thereismore = False
        finally:
            movies_text = "\n".join(movielines)
        query.answer()
        if "previous_movies_text" in context.user_data:
            query.edit_message_text(
                text=context.user_data["previous_movies_text"],
                reply_markup=None,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True
            )
        if not thereismore:
            query.message.reply_text(text=f"{movies_text}\n\ndat was het\.",
                                     parse_mode=ParseMode.MARKDOWN_V2,
                                     disable_web_page_preview=True)
            return ConversationHandler.END
        else:
            keyboard = [[InlineKeyboardButton("meer", callback_data=str(1900))]]
            keyboard_markup = InlineKeyboardMarkup(keyboard)
            context.user_data["previous_movies_text"] = movies_text
            query.message.reply_text(text=movies_text,
                                     reply_markup=keyboard_markup,
                                     parse_mode=ParseMode.MARKDOWN_V2,
                                     disable_web_page_preview=True)
            return SHOW_MOVIES

    def handle_timeout(self,  update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        resp = query.data
        user = query.from_user
        log.info(f"callback timeout with query data: {resp}")
        query.message.edit_reply_markup(reply_markup=None)
        query.message.reply_text(text=f"Duurt laaaaang\.",
                                 parse_mode=ParseMode.MARKDOWN_V2
                                 )
        context.user_data.clear()
        return ConversationHandler.END

    def cancel(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        resp = query.data
        user = query.from_user
        log.info(f"callback cancel with query data: {resp}")
        log.info("User %s canceled the conversation.", user.first_name)
        query.message.edit_reply_markup(reply_markup=None)
        query.message.reply_text(text=f"Oke\, dan niet\.",
                                 parse_mode=ParseMode.MARKDOWN_V2
                                 )
        context.user_data.clear()
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

    def random_movies(self, update: Update, context: CallbackContext) -> None:
        context.bot.sendMessage(chat_id=update.effective_chat.id, text="Hier heb je een film:")