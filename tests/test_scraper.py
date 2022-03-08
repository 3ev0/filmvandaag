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
for m in scraper.scrape_new_movies(src.config.streaming_services, added_days_ago=3):
    print(m)

