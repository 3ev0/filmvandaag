import time
import os
import os.path
import logging
import pprint
import signal
import argparse

import telegram_alert

import bot, scraper

config ={}


def signal_handler(signum, frame):
    raise OSError(f"Signal received: {signum}")


signal.signal(signal.SIGTERM, signal_handler)


def build_config() -> dict:
    """
    Check the environment variables and copy into a dict
    :return:
    """
    config["TG_FV_BOT_TOKEN"] = os.environ["TG_FV_BOT_TOKEN"]
    config["TG_ALERT_CHANNEL"] = os.environ["TG_ALERT_CHANNEL"]
    config["TG_ALERT_BOT_TOKEN"] = os.environ["TG_ALERT_BOT_TOKEN"]
    config["TG_ALERT_INSTANCE_NAME"] = os.environ.get("TG_ALERT_INSTANCE_NAME", "unknown")
    config["SELENIUM_CONNSTR"] = os.environ["SELENIUM_CONNSTR"]
    config["NEW_MOVIES_MIN_RATING"] = int(os.environ.get("NEW_MOVIES_MIN_RATING", 5))
    config["NEW_MOVIES_THRESHOLD_DAYS"] = int(os.environ.get("NEW_MOVIES_THRESHOLD_DAYS", 7))
    config["IMDB_VOTES_THRESHOLD"] = int(os.environ.get("IMDB_VOTES_THRESHOLD", 10000))
    return config


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="FilmVandaag. Voor uw selectie naar keuze.")
    argparser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging.")
    args = argparser.parse_args()

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=loglevel)
    build_config()
    logging.info("Program started with config:")
    logging.info(pprint.pformat(config))
    alert_bot = telegram_alert.TelegramAlertBot(config, "FilmVandaag")
    alert_bot.info("Program started.")
    try:
        fv_scraper = scraper.FilmVandaagScraper(config)
        fv_bot = bot.FilmVandaagBot(config, fv_scraper)
        fv_bot.start()
        while True:
            time.sleep(60)
            logging.info("I'm alive")
    except Exception as err:
        alert_bot.error(f"A fatal exception occurred: {str(err)}")
        logging.error(f"A fatal exception occurred: {str(err)}")
        raise
    finally:
        alert_bot.info("Program ended.")