import configparser
import datetime
import json
import logging.handlers
import os

import trakt
from requests import request
from trakt.tv import TVShow
from trakt.users import User

logger = logging.getLogger("TraktMalSync")
DATA_DIR = "data"


def setup_logging():
    """Setup basic logging"""
    # Create the log folder if it does not exist
    if not os.path.isdir("logs"):
        os.makedirs("logs")

    logformat = "[%(asctime)s] %(levelname)s:%(name)s %(message)s"

    stream = logging.StreamHandler()
    stream.setLevel(logging.INFO)

    # Define the Logging config
    logging.basicConfig(
        format=logformat,
        level=logging.DEBUG,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.handlers.RotatingFileHandler(
                "logs/debug.log",
                maxBytes=(1048576 * 2),
                backupCount=7,
            ),
            stream,
        ],
    )


def save_config(config):
    logger.info("Saving config")
    with open(DATA_DIR + "/config.ini", "w") as configfile:
        config.write(configfile)


def get_config():
    logger.info("Loading config")
    config = configparser.ConfigParser()
    config["TRAKT"] = {
        "username": "",
        "client_id": "",
        "client_secret": "",
        "oauth_token": "",
    }

    if not os.path.isdir(DATA_DIR):
        os.mkdir(DATA_DIR)

    if not os.path.isfile(DATA_DIR + "/config.ini"):
        logger.info("No config file found, creating one")
        save_config(config)

    config.read(DATA_DIR + "/config.ini")

    return config


setup_logging()
config = get_config()


def setup_trakt():
    trakt.core.AUTH_METHOD = trakt.core.OAUTH_AUTH
    if not config["TRAKT"]["username"]:
        config["TRAKT"]["username"] = input("Please enter your Trakt username: ")
    if not config["TRAKT"]["client_id"]:
        trakt.init(config["TRAKT"]["username"])
    else:
        trakt.init(
            config["TRAKT"]["username"],
            client_id=config["TRAKT"]["client_id"],
            client_secret=config["TRAKT"]["client_secret"],
        )

    config["TRAKT"]["client_id"] = trakt.core.CLIENT_ID
    config["TRAKT"]["client_secret"] = trakt.core.CLIENT_SECRET
    config["TRAKT"]["oauth_token"] = trakt.core.OAUTH_TOKEN
    save_config(config)


def get_anime_shows(shows, shows_cache, force_update=False):
    if shows_cache and not force_update:
        shows_dict = shows_cache
    else:
        shows_dict = {"anime": {}, "other": []}
    for show in shows:
        if force_update == False:
            if show.slug in shows_dict["other"]:
                continue
            cached_date = (
                shows_dict["anime"].get(show.slug, {}).get("last_updated", None)
            )
            if cached_date:
                cached_date = datetime.datetime.strptime(
                    cached_date, "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                last_updated = datetime.datetime.strptime(
                    show.last_updated_at, "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                if cached_date >= last_updated:
                    continue
        logger.info(f"Checking show: {show.slug}")
        genres = TVShow(show.slug).genres
        if genres:
            if "anime" in genres:
                show_obj = {
                    "title": show.title,
                    "tvdb_id": show.tvdb,
                    "watched": {},
                    "last_updated": show.last_updated_at,
                }

                for season in show.seasons:
                    watched_eps = []
                    for ep in season["episodes"]:
                        if ep["plays"] > 0:
                            watched_eps.append(ep["number"])
                    if watched_eps:
                        show_obj["watched"][season["number"]] = watched_eps

                shows_dict["anime"][show.slug] = show_obj
            else:
                shows_dict["other"].append(show.slug)
        else:
            logger.info(f"No genres found for {show.title}")
    logger.info("Shows Filtered")
    return shows_dict


def get_anime_movies(movies):
    anime_movies = []
    other_movies = []
    for movie in movies:
        if movie.genres:
            print(movie.title, ":", movie.genres)
    logger.info("Movies Filtered")
    return anime_movies, other_movies


def verify_anime_list():
    obtain = False
    if not os.path.isfile(DATA_DIR + "/anime_list.json"):
        obtain = True
    else:
        with open(DATA_DIR + "/anime_list.json") as f:
            data = json.load(f)
        today = datetime.datetime.today()
        file_date = datetime.datetime.strptime(data["date"], "%Y-%m-%d")
        if today - file_date >= datetime.timedelta(days=7):
            obtain = True
    if obtain:
        logger.info("Obtaining anime list")
        file = request(
            "GET",
            url="https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-full.json",
        )
        file_contents = file.content.decode("utf-8")
        json_obj = json.loads(file_contents)
        ani_list = {}
        ani_list["date"] = datetime.date.today().strftime("%Y-%m-%d")
        ani_list["shows"] = json_obj
        with open(DATA_DIR + "/anime_list.json", "w") as f:
            json.dump(ani_list, f, indent=4)


trakt.core.OAUTH_TOKEN = config["TRAKT"]["oauth_token"]
trakt.core.CLIENT_ID = config["TRAKT"]["client_id"]
trakt.core.CLIENT_SECRET = config["TRAKT"]["client_secret"]


def main():
    try:
        me = User(config["TRAKT"]["username"] or "frazzer951")
    except (trakt.errors.OAuthException, trakt.errors.ForbiddenException):
        logger.info("Trakt OAuth token invalid,re-authenticating")
        setup_trakt()

    me = User(config["TRAKT"]["username"])

    if os.path.isfile(DATA_DIR + "/shows_cache.json"):
        with open(DATA_DIR + "/shows_cache.json") as f:
            shows_cache = json.load(f)
    else:
        shows_cache = None
    shows = me.watched_shows
    shows = get_anime_shows(shows, shows_cache)

    movies = me.watched_movies
    anime_movies, other_movies = get_anime_movies(movies)

    with open(DATA_DIR + "/shows_cache.json", "w") as outfile:
        json.dump(shows, outfile, indent=4)

    verify_anime_list()


if __name__ == "__main__":
    main()
