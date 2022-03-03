import logging
import time
import datetime
import re
import urllib.parse

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
        self.driver = None
        self.config = config
        log.info("FilmVandaagScraper instance initialized.")

    def scrape_new_movies(self, service: str, added_days_ago: int) -> bool:
        if not self.driver:
            self.driver = get_chrome_driver(self.config["SELENIUM_CONNSTR"])
        url = NEW_MOVIES_URLS[service]
        time_threshold = datetime.datetime.now() - datetime.timedelta(days=added_days_ago)
        log.info(f"Scraping movies from {url}...")
        self.driver.get(url)
        title_els = self.driver.find_elements(By.CSS_SELECTOR, "h3.is-list-heading")
        list_els = self.driver.find_elements(By.CSS_SELECTOR, "ul.item-list")
        movies = []
        for i in range(len(title_els)):
            title = title_els[i].text
            if "vandaag" in title.lower():
                dt = dateparser.parse("vandaag")
            else:
                dt = dateparser.parse(title)
            if dt < time_threshold: # the next movies are added too long ago
                log.info(f"Reached time threshold ({dt}. Stopped scraping.")
                break
            rating_els = list_els[i].find_elements(By.CSS_SELECTOR, "div.rating span")
            movie_title_els = list_els[i].find_elements(By.CSS_SELECTOR, "div.item-content h4 a")
            content_els = list_els[i].find_elements(By.CSS_SELECTOR, "div.item-content")
            sub_els = list_els[i].find_elements(By.CSS_SELECTOR, "div.sub")
            for j in range(len(rating_els)):
                gdinfo = content_els[j].find_elements(By.CSS_SELECTOR, "div")[0].text.split("•")
                if len(gdinfo) < 2:
                    director = None
                else:
                    director = gdinfo[1].strip()
                genres = [g.strip() for g in gdinfo[0].split("/")]
                movie = {"rating": float(rating_els[j].text.strip()),
                         "num_votes": int(rating_els[j].get_attribute("title").split()[0].replace(".", "")),
                         "date": dt,
                         "title": movie_title_els[j].text,
                         "genres": genres,
                         "director": director,
                         "sub": sub_els[j].text,
                         "service": service}
                log.info(f"Movie found: {movie}")
                movies.append(movie)
        return movies

    def search_movies(self, services: list = None,
                      genres: list = None,
                      imdb_score: (float, float) = None,
                      release_year: (int, int) = None,
                      page: int = 0,
                      votes_threshold: int = 10000
                      ) -> dict:
        """

        :return:
        """
        log.info(f"scrape_search_movies()")
        movies = []
        params = {"categorie": "films", "sorteer[]": "imdb-score", "genre-filter": "of", "page": page}
        humanfriendly_params = {"categorie": "films", "sorteer": "imdb-score", "genre-filter": "of"}
        if services:
            params["vod[]"] = services
            humanfriendly_params["vod"] = ",".join(services)
        if imdb_score:
            if not imdb_score[1]:
                imdb_score = imdb_score[0], 10
            params["imdb-score[]"] = [str(e) for e in imdb_score]
            humanfriendly_params["imdb-score"] = ",".join([str(e) for e in imdb_score])
        if genres:
            params["genre[]"] = genres
            humanfriendly_params["genre"] = ",".join(genres)
        if release_year:
            if not release_year[1]:
                release_year = release_year[0], datetime.datetime.today().year + 2
            params["jaar[]"] = [str(e) for e in release_year]
            humanfriendly_params["jaar"] = ",".join([str(e) for e in release_year])
        log.info(f"Params: {params}")
        hf_search_url = HF_SEARCH_MOVIE_URL + "?" + urllib.parse.urlencode(humanfriendly_params)
        log.info(f"Human-friendly search URL: {hf_search_url}")
        log.info(f"fetching URL: {SEARCH_MOVIE_URL}")
        resp = requests.get(SEARCH_MOVIE_URL, params=params)
        resp.raise_for_status()
        result = resp.json()
        total_movies = result["total"]
        if not result["results"]:
            log.info(f"Results empty. No more results available on this page ({page}).")
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
            m = re.match(r"^(?P<title>.+) \((?P<year>[0-9]{4})\)$", title_el.text)
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
                movies.append(movie)
        return {"total": total_movies, "movies": movies, "page": page, "search_url": hf_search_url}
