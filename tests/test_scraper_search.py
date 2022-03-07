import os
import pprint
import logging

from src.scraper import FilmVandaagScraper
import src.config

logging.basicConfig(level=logging.DEBUG)
config = {}

scraper = FilmVandaagScraper(config)

try:
    browser_url = scraper.get_search_movies_browser_url(services=src.config.streaming_services,
                                   genres=["actie", "horror", "documentaire"],
                                   imdb_score=(8, 10),
                                   release_year=(2000, 2020))
    generator = scraper.search_movies(services=src.config.streaming_services,
                                   genres=["actie", "horror", "documentaire"],
                                   imdb_score=(8, 10),
                                   release_year=(2000, 2020))

    try:
        while True:
            for c in range(30):
                print(next(generator)["title"])
            input()
    except StopIteration:
        print("end")
        print(browser_url)

except Exception:
    scraper.driver.quit()
    raise
