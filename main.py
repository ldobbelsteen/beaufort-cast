import mimetypes
import random
import sys
import threading
import os
import logging
import time
import uuid
from datetime import datetime
from bottle import static_file, request, abort, run, route
import pychromecast


def collect_photos_recursively(dir: str, blacklisted_dir_names: list[str]):
    """Collect all photos in a directory and its subdirectories. Returns a list of tuples where
    the first element is the relative path to the photo and the second element is the content type."""
    result: list[tuple[str, str]] = []
    for entry in os.scandir(dir):
        if entry.is_file():
            content_type, _ = mimetypes.guess_type(entry.name)
            if content_type is not None:
                if content_type not in [
                    "image/apng",
                    "image/bmp",
                    "image/gif",
                    "image/jpeg",
                    "image/png",
                    "image/webp",
                ]:  # based on https://developers.google.com/cast/docs/media
                    result.append((entry.path, content_type))
                else:
                    logging.debug(
                        f"file '{entry.path}' is likely not an image or has unsupported format, ignoring"
                    )
            else:
                logging.debug(
                    f"could not determine content type for '{entry.path}', ignoring"
                )
        elif entry.is_dir():
            if all(
                banned.lower() not in entry.name.lower()
                for banned in blacklisted_dir_names
            ):
                result.extend(
                    collect_photos_recursively(entry.path, blacklisted_dir_names)
                )
    return result


def run_photo_server(photo_dir: str, local_ip: str, listening_port: int, key: str):
    """Spawn a Bottle server to serve photos."""

    @route("/<path:path>")
    def send_photo(path: str):
        if request.query.key == key:
            return static_file(path, photo_dir)
        else:
            abort(401, "unauthorized")

    run(
        host=local_ip,
        port=listening_port,
        quiet=True,
    )


def main(
    photo_dir: str,
    cast_device_name: str,
    local_ip: str,
    listening_port: int,
    blacklisted_dir_names: list[str],
    cast_check_interval_secs: float,
    next_photo_interval_secs: float,
    photo_index_interval_secs: float,
):
    # Create random key for image server.
    key = str(uuid.uuid4())
    logging.debug(f"key: {key}")

    # Start the image server.
    thread = threading.Thread(
        target=run_photo_server,
        args=(photo_dir, local_ip, listening_port, key),
    )
    thread.daemon = True
    thread.start()

    def index_photos():
        """Get list of photos of each subdirectory associated with a year in the directory.
        The list is sorted from oldest to newest year. The lists are nonempty."""
        logging.info("indexing photos...")

        result: list[list[tuple[str, str]]] = []
        for entry in sorted(os.scandir(photo_dir), key=lambda x: x.name):
            if entry.is_dir():
                if entry.name.isnumeric():  # is a year
                    year_photos = collect_photos_recursively(
                        entry.path, blacklisted_dir_names
                    )
                    if len(year_photos) > 0:
                        result.append(
                            [
                                (os.path.relpath(path, photo_dir), content_type)
                                for path, content_type in year_photos
                            ]
                        )

        logging.info("indexing complete")
        return result

    # Index photos on disk.
    photos = index_photos()
    last_index = datetime.now()

    def check_index_update():
        """Check if the photo index needs to be updated and do so if true."""
        nonlocal photos
        nonlocal last_index
        logging.debug("checking index update...")
        index_elapsed = (datetime.now() - last_index).total_seconds()
        if index_elapsed > photo_index_interval_secs:
            photos = index_photos()
            last_index = datetime.now()

    def pick_random_photo() -> tuple[str, str]:
        """Pick a random photo from the indexed photos."""
        weights = [2**i for i in range(len(photos))]
        weights[-1] = -(weights[-1] // -4)
        year_photos = random.choices(photos, weights=weights, k=1)[0]
        return random.choice(year_photos)

    def path_to_url(path: str) -> str:
        return f"http://{local_ip}:{listening_port}/{path}?key={key}"

    casts, _ = pychromecast.get_listed_chromecasts(friendly_names=[cast_device_name])
    if len(casts) == 0:
        logging.error(f"chromecast '{cast_device_name}' not found")
        sys.exit(1)
    elif len(casts) > 1:
        logging.error(f"multiple chromecasts found with name '{cast_device_name}'")
        sys.exit(1)
    cast = casts[0]

    while True:
        check_index_update()
        cast.wait()

        # We *should* now have the status.
        if cast.status is not None:
            # If the cast is idle, start casting.
            if (
                cast.status.display_name
                == "Backdrop"  # default chromecast ambient mode, which we can override
                or cast.status.display_name
                == "Default Media Receiver"  # continue previous session (in case of this script crashing or restarting)
            ):
                logging.info("casting...")
                mc = cast.media_controller

                # Cast photos while we still have control.
                while True:
                    check_index_update()
                    path, content_type = pick_random_photo()
                    mc.play_media(path_to_url(path), content_type)

                    time.sleep(next_photo_interval_secs)
                    if cast.status.display_name != "Default Media Receiver":
                        break

                logging.info("finished casting")
            else:
                logging.debug("chromecast not idle")
        else:
            logging.warning("chromecast status unknown")

        time.sleep(cast_check_interval_secs)


if __name__ == "__main__":
    photo_dir = os.getenv("PHOTO_DIR", "/photos")
    cast_device_name = os.getenv("CAST_DEVICE_NAME", "Huishok TV")
    local_ip = os.getenv("LOCAL_IP", "192.168.1.44")
    listening_port = int(os.getenv("LISTENING_PORT", 1774))
    blacklisted_dir_names = os.getenv(
        "BLACKLISTED_DIR_NAMES",
        "@eaDir;zucht;instorm;voorjaarsweekend;vraagdatum;tilburg;stormenboek;zware;overlege;overlegé",
    ).split(";")
    cast_check_interval_secs = float(os.getenv("CAST_CHECK_INTERVAL_SECS", 20))
    next_photo_interval_secs = float(os.getenv("NEXT_PHOTO_INTERVAL_SECS", 20))
    photo_index_interval_secs = float(
        os.getenv("PHOTO_INDEX_INTERVAL_SECS", 2 * 60 * 60)
    )
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    main(
        photo_dir,
        cast_device_name,
        local_ip,
        listening_port,
        blacklisted_dir_names,
        cast_check_interval_secs,
        next_photo_interval_secs,
        photo_index_interval_secs,
    )
