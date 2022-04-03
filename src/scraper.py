import logging
import time
import datetime
import re
import urllib.parse
import typing

import requests

from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
import selenium.webdriver.chrome.options
import dateparser
from bs4 import BeautifulSoup

NEW_MOVIES_URLS = {"netflix": "https://www.filmvandaag.nl/video-on-demand/netflix/nieuwe-films",
                   "pathe": "https://www.filmvandaag.nl/video-on-demand/pathe-thuis/nieuw-op-pathe-thuis",
                   "amazon": "https://www.filmvandaag.nl/video-on-demand/amazon-prime-video/nieuwe-films",
                   "disney": "https://www.filmvandaag.nl/video-on-demand/disney-plus/nieuwe-films"
                   }

FILMVANDAAG_HOST = "https://www.filmvandaag.nl"
SEARCH_MOVIE_URL = f"{FILMVANDAAG_HOST}/api/search"
HF_SEARCH_MOVIE_URL = f"{FILMVANDAAG_HOST}/zoek"

log = logging.getLogger(__name__)


def get_chrome_driver(connstr) -> WebDriver:
    """
    Get the remote chrome_driver
    Build Chrome options. This configuration is required for chromedriver to function properly in a docker container.
    :return:
    """
    chrome_options = webdriver.chrome.options.Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    for i in range(10):
        try:
            log.info(f"Connecting to selenium Chrome instance @{connstr}...")
            driver = webdriver.Remote(f"http://{connstr}/wd/hub", options=chrome_options)
        except Exception as err:
            log.error(f"Error connecting to Selenium driver: {err}")
            log.error("Retrying in 3 seconds..")
            time.sleep(3)
            continue
        break
    logging.info("Connection established.")
    return driver


class FilmVandaagScraper:

    def __init__(self, config):
        self.config = config
        log.info("FilmVandaagScraper instance initialized.")

    def scrape_new_movies(self, services: list[str],
                          added_days_ago: int,
                          votes_threshold: int = 10000,
                          rating_threshold: int = 0
                          ) -> typing.Generator[dict, None, None]:
        for service in services:
            url = NEW_MOVIES_URLS[service]
            log.info(f"Scraping movies from {url}...")
            time_threshold = datetime.datetime.now() - datetime.timedelta(days=added_days_ago)
            resp = requests.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            title_els = soup.find_all("h3", class_="is-list-heading")
            list_els = soup.find_all("ul", class_="item-list")
            for i in range(len(title_els)):
                title = title_els[i].string
                if "vandaag" in title.lower():
                    dt = dateparser.parse("vandaag")
                else:
                    dt = dateparser.parse(title)
                if dt < time_threshold:  # the next movies are added too long ago
                    log.info(f"Reached time threshold ({dt}. Stopped scraping.")
                    break
                rating_els = list_els[i].select("div.rating span")
                movie_title_els = list_els[i].select("div.item-content h4 a")
                content_els = list_els[i].select("div.item-content")
                sub_els = list_els[i].select("div.sub")
                for j in range(len(rating_els)):
                    gdinfo = content_els[j].find("div").text.split("•")
                    if len(gdinfo) < 2:
                        director = None
                    else:
                        director = gdinfo[1].strip()
                    genres = [g.strip() for g in gdinfo[0].split("/")]
                    title_el = movie_title_els[j]
                    m = re.match(r"^(?P<title>.+?)( \((?P<year>[0-9]{4})\))?$", str(title_el.text))
                    movie = {"rating": float(rating_els[j].text.strip()),
                             "num_votes": int(rating_els[j]["title"].split()[0].replace(".", "")),
                             "date": dt,
                             "release_year": str(m.group("year")),
                             "title": str(m.group("title")),
                             "genres": genres,
                             "director": director,
                             "service": service,
                             "url": f"{FILMVANDAAG_HOST}{title_el['href']}"}
                    if movie["num_votes"] < votes_threshold:
                        log.info(f"Number of votes {movie['num_votes']} below threshold {votes_threshold}. Discarded.")
                    elif movie["rating"] < rating_threshold:
                        log.info(f"Rating {movie['rating']} below threshold {rating_threshold}. Discarded.")
                    else:
                        yield movie

    def get_search_movies_browser_url(self, services: list = None,
                      genres: list = None,
                      imdb_score: (float, float) = None,
                      release_year: (int, int) = None
                      ) -> str:
        humanfriendly_params = {"categorie": "films", "sorteer": "imdb-score", "genre-filter": "of"}
        if services:
            humanfriendly_params["vod"] = ",".join(services)
        if imdb_score:
            if not imdb_score[1]:
                imdb_score = imdb_score[0], 10
            humanfriendly_params["imdb-score"] = ",".join([str(e) for e in imdb_score])
        if genres:
            humanfriendly_params["genre"] = ",".join(genres)
        if release_year:
            if not release_year[1]:
                release_year = release_year[0], datetime.datetime.today().year + 2
            humanfriendly_params["jaar"] = ",".join([str(e) for e in release_year])
        hf_search_url = HF_SEARCH_MOVIE_URL + "?" + urllib.parse.urlencode(humanfriendly_params)
        log.info(f"Browser search URL: {hf_search_url}")
        return hf_search_url

    def search_movies(self, services: list = None,
                      genres: list = None,
                      imdb_score: (float, float) = None,
                      release_year: (int, int) = None,
                      votes_threshold: int = 10000
                      ) -> typing.Generator[dict, None, None]:
        """
        Generator function. Yields movies.
        :return: generator
        """
        log.info(f"search_movies()")
        params = {"categorie": "films", "sorteer[]": "imdb-score", "genre-filter": "of"}

        if services:
            params["vod[]"] = services
        if imdb_score:
            if not imdb_score[1]:
                imdb_score = imdb_score[0], 10
            params["imdb-score[]"] = [str(e) for e in imdb_score]
        if genres:
            params["genre[]"] = genres
        if release_year:
            if not release_year[1]:
                release_year = release_year[0], datetime.datetime.today().year + 2
            params["jaar[]"] = [str(e) for e in release_year]
        log.info(f"Params: {params}")

        params["page"] = 0
        while True:
            log.info(f"fetching URL: {SEARCH_MOVIE_URL}")
            resp = requests.get(SEARCH_MOVIE_URL, params=params)
            resp.raise_for_status()
            result = resp.json()
            if not result["results"]:
                log.info(f"Results empty. No more results available on this page ({params['page']}).")
                break
            result_html = result["results"]
            soup = BeautifulSoup(result_html, 'html.parser')
            list_items = soup.find_all("li", class_="is-movie")
            for li in list_items:
                log.debug(li)
                gdinfo = li.find("div", class_="item-content").find("div").text.split("•")
                if len(gdinfo) < 2:
                    director = None
                else:
                    director = gdinfo[1].strip()
                    genres = [g.strip() for g in gdinfo[0].split("/")]
                rating_el = li.find("div", class_="rating").span
                title_el = li.find("a", class_="title")
                m = re.match(r"^(?P<title>.+?)( \((?P<year>[0-9]{4})\))?$", title_el.text)
                movie = {"rating": float(rating_el.text.strip()),
                         "num_votes": int(rating_el["title"].split()[0].replace(".", "")),
                         "release_year": str(m.group("year")),
                         "title": m.group("title"),
                         "genres": genres,
                         "director": director,
                         "url": f"{FILMVANDAAG_HOST}{title_el['href']}"}
                log.info(f"Movie found: {movie}")
                if movie["num_votes"] < votes_threshold:
                    log.info(f"Number of votes {movie['num_votes']} below threshold {votes_threshold}. Discarded.")
                else:
                    yield movie
            params["page"] += 1
        return True
