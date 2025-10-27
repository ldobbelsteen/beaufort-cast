import math
import os
import logging
import pychromecast
import time
import requests
import random
from datetime import datetime
import re
from cachetools import LRUCache, cached, TTLCache
import functools


def retry_indefinitely(interval: int):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            while True:
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    logging.error(e)
                    logging.error(f"Retrying in {interval} seconds...")
                    time.sleep(interval)

        return wrapper

    return decorator


def year_progress():
    """Returns a float between 0 and 1 representing the progress through the current year."""
    now = datetime.now()
    start_of_year = datetime(now.year, 1, 1)
    end_of_year = datetime(now.year + 1, 1, 1)
    total_seconds_in_year = (end_of_year - start_of_year).total_seconds()
    seconds_elapsed = (now - start_of_year).total_seconds()
    return seconds_elapsed / total_seconds_in_year


def is_blacklisted(name: str, substr_blacklist: frozenset[str]) -> bool:
    """Returns whether the given name contains blacklisted substrings."""
    return any(banned.lower() in name.lower() for banned in substr_blacklist)


def year_from_album_name(name: str) -> int | None:
    """Extracts the year from the given album name."""
    match = re.fullmatch(r"\[(\d{4})[\]-].*", name)
    if match is None:
        return None
    return int(match.group(1))


@cached(cache=TTLCache(maxsize=1, ttl=7200))
def list_albums_by_year(
    immich_base_url: str,
    immich_api_key: str,
    album_substr_blacklist: frozenset[str],
):
    """List all album IDs and group them by year sorted increasingly."""
    resp = requests.get(
        f"{immich_base_url}/api/albums",
        headers={
            "Accept": "application/json",
            "x-api-key": immich_api_key,
        },
    )
    resp.raise_for_status()
    albums = resp.json()

    by_year: dict[int, list[str]] = {}
    for album in albums:
        id, name = album["id"], album["albumName"]
        assert isinstance(id, str)
        assert isinstance(name, str)

        if is_blacklisted(name, album_substr_blacklist):
            logging.info(f"ignoring blacklisted album '{name}'")
            continue

        year = year_from_album_name(name)
        if year is None:
            logging.warning(
                f"ignoring album for which year cannot be extracted '{name}'"
            )
            continue

        if year not in by_year:
            by_year[year] = []
        by_year[year].append(id)

    return [by_year[year] for year in sorted(by_year.keys())]


@cached(cache=LRUCache(maxsize=1))
def compute_year_weights(year_count: int, year_decay_factor: float) -> list[float]:
    assert year_decay_factor >= 1.0
    assert year_decay_factor <= 2.0

    # The weights grow exponentially (by the decay factor) with the year.
    result = [year_decay_factor**i for i in range(year_count)]

    # The last year should be weighted by the progress through the year.
    result[-1] *= year_progress()

    return result


def is_supported_image_format(content_type: str) -> bool:
    return content_type in [
        "image/apng",
        "image/bmp",
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
    ]  # based on https://developers.google.com/cast/docs/media#image_formats


@cached(cache=TTLCache(maxsize=math.inf, ttl=7200))
def list_album_assets(
    immich_base_url: str,
    immich_api_key: str,
    album_id: str,
) -> list[tuple[str, str]]:
    """List all image assets' IDs and content types in the given album."""
    resp = requests.get(
        f"{immich_base_url}/api/albums/{album_id}",
        headers={
            "Accept": "application/json",
            "x-api-key": immich_api_key,
        },
    )
    resp.raise_for_status()
    album = resp.json()

    result = []
    for asset in album["assets"]:
        id, content_type = asset["id"], asset["originalMimeType"]
        assert isinstance(id, str)
        assert isinstance(content_type, str)

        if is_supported_image_format(content_type):
            result.append((id, content_type))
        else:
            logging.debug(f"ignoring unsupported asset '{id}' ({content_type})")

    return result


def direct_asset_url(base_url: str, api_key: str, id: str) -> str:
    return f"{base_url}/api/assets/{id}/original?apiKey={api_key}"


@retry_indefinitely(interval=22)
def pick_random_photo(
    immich_base_url: str,
    immich_api_key: str,
    album_substr_blacklist: frozenset[str],
    year_decay_factor: float,
) -> tuple[str, str]:
    albums_by_year = list_albums_by_year(
        immich_base_url,
        immich_api_key,
        album_substr_blacklist,
    )

    year_weights = compute_year_weights(len(albums_by_year), year_decay_factor)
    year = random.choices(albums_by_year, weights=year_weights, k=1)[0]
    album = random.choice(year)

    assets = list_album_assets(immich_base_url, immich_api_key, album)
    if len(assets) > 0:
        return random.choice(assets)

    # Retry if the album has no (valid) assets.
    logging.warning(f"album '{album}' has no valid assets")
    return pick_random_photo(
        immich_base_url, immich_api_key, album_substr_blacklist, year_decay_factor
    )


@retry_indefinitely(interval=22)
def get_chromecast(name: str) -> pychromecast.Chromecast:
    casts, _ = pychromecast.get_listed_chromecasts(friendly_names=[name])
    if len(casts) == 0:
        raise Exception(f"chromecast '{name}' not found")
    elif len(casts) > 1:
        raise Exception(f"multiple chromecasts found with name '{name}'")
    return casts[0]


def request_url_void(url: str, chunk_size: int = 1024):
    """Request a URL and efficiently ignore the response."""
    with requests.get(url, stream=True) as resp:
        resp.raise_for_status()
        for _ in resp.iter_content(chunk_size=chunk_size):
            pass


def main(
    chromecast_name: str,
    immich_base_url: str,
    immich_api_key: str,
    album_substr_blacklist: frozenset[str],
    year_decay_factor: float,
    photo_interval_secs: int,
):
    cast = get_chromecast(chromecast_name)
    cast_backoff_secs = 27

    while True:
        # Request the status of the Chromecast.
        cast.wait()

        # Retry later if the request failed.
        if cast.status is None:
            logging.warning("chromecast status unknown")
            time.sleep(cast_backoff_secs)
            continue

        mc = cast.media_controller

        # Determine if the Chromecast is fully idle.
        is_idle = cast.status.display_name == "Backdrop"

        # Determine if the Chromecast is already casting Immich content.
        # We can resume casting if so, since we may have lost control of the cast.
        is_casting_immich = (
            cast.status.display_name == "Default Media Receiver"
            and mc.status.content_id is not None
            and immich_base_url in mc.status.content_id
        )

        # Retry later if the Chromecast is not idle nor resumable.
        if not is_idle and not is_casting_immich:
            logging.debug(f"chromecast busy: {cast.status.display_name}")
            time.sleep(cast_backoff_secs)
            continue

        # Cast an initial photo.
        id, content_type = pick_random_photo(
            immich_base_url,
            immich_api_key,
            album_substr_blacklist,
            year_decay_factor,
        )
        logging.info("casting...")
        logging.debug(f"casting initial photo {id} ({content_type})")
        url = direct_asset_url(immich_base_url, immich_api_key, id)
        mc.play_media(url, content_type)

        # Keep casting new photos while we still have control.
        while True:
            id, content_type = pick_random_photo(
                immich_base_url,
                immich_api_key,
                album_substr_blacklist,
                year_decay_factor,
            )

            url = direct_asset_url(immich_base_url, immich_api_key, id)

            # Make the system load the photo by requesting it. This causes the photo to be
            # cached in the system's memory. On subsequent requests, the photo is already
            # cached, so the Chromecast's request will be served from the cache.
            logging.debug(f"warming-up new photo {id} ({content_type})")
            try:
                request_url_void(url)
            except Exception:
                pass

            # Let the previous image display for the configured interval.
            time.sleep(photo_interval_secs)

            # Stop if we lost control of the cast.
            if cast.status.display_name != "Default Media Receiver":
                break

            # Actually cast the new photo.
            logging.debug(f"casting new photo {id} ({content_type})")
            mc.play_media(url, content_type)

        logging.info("finished casting")
        time.sleep(cast_backoff_secs)


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    main(
        os.environ["CHROMECAST_NAME"],
        os.environ["IMMICH_BASE_URL"],
        os.environ["IMMICH_API_KEY"],
        frozenset(os.environ["ALBUM_SUBSTR_BLACKLIST"].split(";")),
        float(os.environ["YEAR_DECAY_FACTOR"]),
        int(os.environ["PHOTO_INTERVAL_SECS"]),
    )
