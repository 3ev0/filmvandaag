import os
import pprint
import logging

from src.scraper import FilmVandaagScraper
import src.config

logging.basicConfig(level=logging.DEBUG)

config = {
    "SELENIUM_CONNSTR": os.getenv("SELENIUM_CONNSTR")
}

scraper = FilmVandaagScraper(config)

try:
    movies = scraper.search_movies(services=src.config.streaming_services,
                                   genres=["actie", "horror"],
                                   imdb_score=(8, 10),
                                   release_year=(2000, 2020))
    pprint.pprint(movies)
except Exception:
    scraper.driver.quit()
    raise
