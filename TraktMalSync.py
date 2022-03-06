import configparser
import os
import logging.handlers
import sys
from tracemalloc import stop
import trakt
from trakt.users import User
import tvdb_api

logger = logging.getLogger("TraktMalSync")


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
    with open("config.ini", "w") as configfile:
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
    config["TVDB"] = {"api_key": ""}

    if not os.path.isfile("config.ini"):
        logger.info("No config file found, creating one")
        save_config(config)

    config.read("config.ini")

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


def setup_tvdb():
    if not config["TVDB"]["api_key"]:
        config["TVDB"]["api_key"] = input("Please enter your TVDB API Key: ")

    tvdb = tvdb_api.Tvdb(apikey=config["TVDB"]["api_key"])

    save_config(config)
    return tvdb


def get_anime_shows(shows):
    anime_shows = []
    other_shows = []
    for show in shows:
        tvdb_id = show.tvdb
        tvdb_show = TVDB[tvdb_id]
        if "Anime" in tvdb_show.data["genre"]:
            anime_shows.append(show)
        else:
            other_shows.append(show)
    return anime_shows, other_shows


TVDB = setup_tvdb()
trakt.core.OAUTH_TOKEN = config["TRAKT"]["oauth_token"]
trakt.core.CLIENT_ID = config["TRAKT"]["client_id"]
trakt.core.CLIENT_SECRET = config["TRAKT"]["client_secret"]


def main():
    try:
        me = User(config["TRAKT"]["username"] or "frazzer951")
    except (trakt.errors.OAuthException, trakt.errors.ForbiddenException):
        logger.info("Trakt OAuth token invalid,re-authenticating")
        setup_trakt()

    setup_tvdb()

    me = User(config["TRAKT"]["username"])
    print(me)

    shows = me.watched_shows
    movies = me.watched_movies
    # print(shows)
    # print(movies)

    anime_shows, other = get_anime_shows(shows)

    print(anime_shows)
    print(other)


if __name__ == "__main__":
    main()
