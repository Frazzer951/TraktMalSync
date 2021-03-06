import configparser
import datetime
import json
import logging.handlers
import os
from collections import defaultdict

import trakt
from requests import request
from trakt.movies import Movie
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
        if not force_update:
            if show.slug in shows_dict["other"]:
                continue
            cached_date = shows_dict["anime"].get(show.slug, {}).get("last_updated", None)
            if cached_date:
                cached_date = datetime.datetime.strptime(cached_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                last_updated = datetime.datetime.strptime(show.last_updated_at, "%Y-%m-%dT%H:%M:%S.%fZ")
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


def get_anime_movies(movies, movies_cache, force_update=False):
    if movies_cache and not force_update:
        movies_dict = movies_cache
    else:
        movies_dict = {"anime": {}, "other": []}
    for movie in movies:
        if not force_update:
            if movie.slug in movies_dict["other"]:
                continue
            cached_date = movies_dict["anime"].get(movie.slug, {}).get("last_updated", None)
            if cached_date:
                cached_date = datetime.datetime.strptime(cached_date, "%Y-%m-%dT%H:%M:%S.%fZ")
                last_updated = datetime.datetime.strptime(movie.last_updated_at, "%Y-%m-%dT%H:%M:%S.%fZ")
                if cached_date >= last_updated:
                    continue
        logger.info(f"Checking movie: {movie.slug}")
        genres = Movie(movie.slug).genres
        if genres:
            if "anime" in genres:
                movie_obj = {
                    "title": movie.title,
                    "tmdb_id": movie.ids["ids"]["tmdb"],
                    "watched": movie.plays > 0,
                    "last_updated": movie.last_updated_at,
                }
                movies_dict["anime"][movie.slug] = movie_obj
            else:
                movies_dict["other"].append(movie.slug)
        else:
            logger.info(f"No genres found for {movie.title}")
    logger.info("Movies Filtered")
    return movies_dict


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

        tvdb_to_mal = defaultdict(list)
        tmdb_to_mal = defaultdict(list)

        for item in json_obj:
            if "mal_id" in item:
                if "thetvdb_id" in item:
                    tvdb_to_mal[item["thetvdb_id"]].append(str(item["mal_id"]))
                if "themoviedb_id" in item:
                    tmdb_to_mal[item["themoviedb_id"]].append(str(item["mal_id"]))

        ani_list["shows"] = tvdb_to_mal
        ani_list["movies"] = tmdb_to_mal

        with open(DATA_DIR + "/anime_list.json", "w") as f:
            json.dump(ani_list, f, indent=4)


def get_anime_list():
    with open(DATA_DIR + "/anime_list.json") as f:
        data = json.load(f)
    return data["shows"], data["movies"]


def verify_trakt():
    try:
        User(config["TRAKT"]["username"] or "frazzer951")
    except (trakt.errors.OAuthException, trakt.errors.ForbiddenException):
        logger.info("Trakt OAuth token invalid,re-authenticating")
        setup_trakt()


def load_show_cache():
    if os.path.isfile(DATA_DIR + "/shows_cache.json"):
        with open(DATA_DIR + "/shows_cache.json") as f:
            shows_cache = json.load(f)
    else:
        shows_cache = None
    return shows_cache


def save_json(data, filename):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)


def load_movie_cache():
    if os.path.isfile(DATA_DIR + "/movies_cache.json"):
        with open(DATA_DIR + "/movies_cache.json") as f:
            movies_cache = json.load(f)
    else:
        movies_cache = None
    return movies_cache


def load_conversion_dict():
    if os.path.isfile(DATA_DIR + "/conversion_dict.json"):
        with open(DATA_DIR + "/conversion_dict.json") as f:
            conversion_dict = json.load(f)
    else:
        conversion_dict = {}
    return conversion_dict if conversion_dict else {}


def get_anime_mappings(shows, movies):
    conversion_dict = load_conversion_dict()
    tvdb_to_mal, tmdb_to_mal = get_anime_list()
    for title in shows["anime"]:
        show = shows["anime"][title]
        if title in conversion_dict:
            ignored = conversion_dict[title].get("ignore", False)
            if ignored:
                logger.info(f"Ignoring {title}")
                continue
        id = str(show["tvdb_id"])
        if id in tvdb_to_mal:
            show_conversion = conversion_dict.get(title, {})
            show_conversion["title"] = show["title"]
            show_conversion["mal_ids"] = tvdb_to_mal[id]
            show_conversion["tvdb_id"] = id
            conversion_dict[title] = show_conversion
        else:
            logger.warning(f"No MAL ID found for {show['title']}")
            user_input = input("Would You like to manually specify a MAL ID? (y/n)")
            if user_input.lower()[0] == "y":
                mal_ids = input("Please enter the MAL IDs seperated by a comma: ")
                mal_ids = [x.strip() for x in mal_ids.split(",")]
                show_conversion = conversion_dict.get(title, {})
                show_conversion["title"] = show["title"]
                show_conversion["mal_ids"] = [mal_ids]
                show_conversion["tvdb_id"] = id
                conversion_dict[title] = show_conversion
            else:
                user_input = input("Would you like to ignore this show? (y/n)")
                if user_input.lower()[0] == "y":
                    show_conversion = conversion_dict.get(title, {})
                    show_conversion["title"] = show["title"]
                    show_conversion["ignore"] = True
                    conversion_dict[title] = show_conversion

                    continue
                else:
                    show_conversion = conversion_dict.get(title, {})
                    show_conversion["title"] = show["title"]
                    conversion_dict[title] = show_conversion

        conversion_dict[title]["seasons"] = list(set(show["watched"].keys()))

        mappings = conversion_dict[title].get("mappings", {})
        mal_ids = conversion_dict[title].get("mal_ids", [])
        mapped_seasons = []
        for mal_id in mappings:
            mapped_seasons.extend(mappings[mal_id])
        if mal_ids:
            mapped = list(set(mapped_seasons))
            unmapped = [] if "*" in mapped else list(set(show["watched"].keys()) - set(mapped))
            if unmapped:
                if len(mal_ids) > 1:
                    logger.warning(
                        f"{show['title']} has multiple MAL IDs please manually specify the seasons in conversion_dict.json"
                    )
                elif len(show["watched"]) > 1:
                    logger.warning(
                        f"{show['title']} has multiple seasons please manually specify the seasons MAL ID in conversion_dict.json"
                    )
                else:
                    mappings[mal_ids[0]] = list(show["watched"].keys())

        conversion_dict[title]["mappings"] = mappings

    for title in movies["anime"]:
        movie = movies["anime"][title]
        id = str(movie["tmdb_id"])
        if id in tmdb_to_mal:
            conversion_dict[title] = {
                "title": show["title"],
                "mal_ids": tmdb_to_mal[id],
                "tmdb_id": id,
            }
        else:
            logger.warning(f"No MAL ID found for {movie['title']}")
    return conversion_dict


trakt.core.OAUTH_TOKEN = config["TRAKT"]["oauth_token"]
trakt.core.CLIENT_ID = config["TRAKT"]["client_id"]
trakt.core.CLIENT_SECRET = config["TRAKT"]["client_secret"]


def main():
    verify_trakt()
    me = User(config["TRAKT"]["username"])

    show_cache = load_show_cache()
    shows = me.watched_shows
    shows = get_anime_shows(shows, show_cache)

    movie_cache = load_movie_cache()
    movies = me.watched_movies
    movies = get_anime_movies(movies, movie_cache)

    save_json(shows, DATA_DIR + "/shows_cache.json")
    save_json(movies, DATA_DIR + "/movies_cache.json")

    verify_anime_list()

    conversion_dict = get_anime_mappings(shows, movies)

    save_json(conversion_dict, DATA_DIR + "/conversion_dict.json")


if __name__ == "__main__":
    main()
