import os
import pprint
import logging

from src.scraper import FilmVandaagScraper
import src.config

logging.basicConfig(level=logging.INFO)

config = {
    "SELENIUM_CONNSTR": os.getenv("SELENIUM_CONNSTR")
}
scraper = FilmVandaagScraper(config)
try:
    for service in src.config.streaming_services:
        pprint.pprint(scraper.scrape_new_movies(service))
except Exception:
    scraper.driver.quit()
    raise
