import logging
import time
import datetime

from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
import selenium.webdriver.chrome.options
import dateparser

NEW_MOVIES_URLS = {"netflix": "https://www.filmvandaag.nl/video-on-demand/netflix/nieuwe-films",
                   "pathe": "https://www.filmvandaag.nl/video-on-demand/pathe-thuis/nieuw-op-pathe-thuis",
                   "prime": "https://www.filmvandaag.nl/video-on-demand/amazon-prime-video/nieuwe-films",
                   "disney": "https://www.filmvandaag.nl/video-on-demand/disney-plus/nieuwe-films"
                   }

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
        self.driver = get_chrome_driver(config["SELENIUM_CONNSTR"])
        log.info("FilmVandaagScraper instance initialized.")

    def scrape_new_movies(self, service: str, added_days_ago: int) -> bool:
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

    def scrape_search_movies(self, services: list = None,
                             genres: list = None,
                             imdb_score: (float, float) = None,
                             release_year: (int, int) = None
                             ) -> dict:
        """
        https://www.filmvandaag.nl/zoek?
        categorie=films&
        vod=netflix%2Camazon%2Cpathe%2Cdisney&
        genre=actie%2Canimatie&
        imdb-score=2%2C9&
        speelduur=85%2C260&
        jaar=1954%2C2002
        :return:
        """
