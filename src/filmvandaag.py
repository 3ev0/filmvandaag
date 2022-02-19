import time
import os
import os.path
import logging
import pprint
import signal
import argparse

import telegram_alert

import bot

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
    config["SELENIUM_HOST"] = os.environ["SELENIUM_HOST"]
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
    alert_bot = telegram_alert.TelegramAlertBot(config["TG_ALERT_BOT_TOKEN"],
                                                config["TG_ALERT_CHANNEL"], "FilmVandaag")
    alert_bot.info("Program started.")
    try:
        fv_bot = bot.FilmVandaagBot(config)
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