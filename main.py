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

PHOTO_DIR = os.environ["PHOTO_DIR"]
CAST_DEVICE_NAME = os.environ["CAST_DEVICE_NAME"]
LOCAL_IP = os.environ["LOCAL_IP"]
LISTENING_PORT = int(os.environ["LISTENING_PORT"])
BLACKLISTED_DIR_NAMES = os.environ["BLACKLISTED_DIR_NAMES"].split(";")
CAST_CHECK_INTERVAL_SECS = float(os.environ["CAST_CHECK_INTERVAL_SECS"])
NEXT_PHOTO_INTERVAL_SECS = float(os.environ["NEXT_PHOTO_INTERVAL_SECS"])
PHOTO_INDEX_INTERVAL_SECS = float(os.environ["PHOTO_INDEX_INTERVAL_SECS"])

NICOLAS_CAGE = [
    "https://images.wired.it/gallery/131607/Big/37493d96-2b60-4164-b730-cc0717c36f18.jpeg",
    "https://i0.wp.com/www.cinezapping.com/wp-content/uploads/2011/01/nicolas-cage_06.jpg",
    "https://3.bp.blogspot.com/-JQqV60o8x0A/Wzexrjx2UKI/AAAAAAAABE4/EwrkZFh0wQ4-LXassGyOZsiWFDgEY9brACLcBGAs/w1200-h630-p-k-no-nu/Nic-Cage.jpg",
    "https://live.staticflickr.com/3242/5818160547_9d1bb744d4.jpg",
    "https://live.staticflickr.com/1461/25524427682_c3757f7989_z.jpg",
    "https://c4.wallpaperflare.com/wallpaper/400/158/569/nicolas-cage-actor-man-face-wallpaper-preview.jpg",
    "https://4.bp.blogspot.com/_N91xwP-lKvw/TFjSKU-ETZI/AAAAAAAABlc/-mAlrcPNZeI/s400/nickcagevampkiss.jpg",
    "https://i1.wp.com/fortworthreport.org/wp-content/uploads/2021/07/PIG001.jpeg",
    "https://upload.wikimedia.org/wikipedia/commons/c/c0/Nicolas_Cage_Deauville_2013.jpg",
    "https://2.bp.blogspot.com/-FG5qhZYlA9c/UNcj6FBBEgI/AAAAAAAACGE/LYOKb7XmUkU/s1600/Nicolas-Cage.jpg",
    "https://www.abruzzo24ore.tv/img/3bcda8f2aed2c8f1fdea1c020dadcf39/w/1024/h/576/scale/160579.jpg",
    "https://3.bp.blogspot.com/--eU2d6DyULI/UOlsIric3dI/AAAAAAAALHE/8jxR5F7erbc/s1600/Nicolas-Cage-nicolas-cage-26969948-1989-1300.jpg",
    "https://live.staticflickr.com/1/131983774_7eb586770f_b.jpg",
    "https://images.uncyc.org/pt/1/11/Nicolascage_(14).jpg",
    "https://1.bp.blogspot.com/-uFkL5_XciyU/UOlsvnMBx4I/AAAAAAAALHU/vnRj0ehmGYg/s1600/tumblr_l31p8iOeC61qa06e2o1_500.jpg",
    "https://1.bp.blogspot.com/-nXhiQU_2DtA/Uaxya_RUJRI/AAAAAAAAGaU/M6fNyE12zeM/s1600/Stringy+Mullet.jpg",
    "https://www.internerdz.com.br/wp-content/uploads/2019/09/Nicolas-Cage-backgrounds-ultra-hd.png",
    "https://c4.wallpaperflare.com/wallpaper/46/357/191/movie-face-off-nicolas-cage-wallpaper-thumb.jpg",
    "https://i0.wp.com/www.cinezapping.com/wp-content/uploads/2010/08/Nicolas-Cage-ne-Lapprendista-stregone.jpg",
    "https://www.talkingdrugs.org/sites/default/files/images/cage-wicker-man.jpg",
    "https://c4.wallpaperflare.com/wallpaper/325/762/565/nicolas-cage-wallpaper-preview.jpg",
    "https://multiglom.files.wordpress.com/2015/01/wildcage01.jpg",
    "https://4.bp.blogspot.com/_N91xwP-lKvw/TFjR4YQU1tI/AAAAAAAABk8/0VBlXRL3VBk/s1600/the+rock.jpg",
    "https://i0.wp.com/www.cinezapping.com/wp-content/uploads/2010/08/Nicolas-Cage-in-Ghost-Rider.jpg",
    "https://cdn.pastemagazine.com/www/system/images/photo_albums/nicolas-cage/large/02-cage-valleygirl.jpg",
    "https://ll-media.tmz.com/2016/12/08/fast-times-memba-05-480w.jpg",
    "https://external-preview.redd.it/ACjjH16xtR9P1GBvLx-ykZdZ1W5RA8CSDInnSbBgwWk.jpg?auto=webp&s=ca4bd365e5dfebd9c8c3b7d7be0dc782702862e1",
    "https://www.slashfilm.com/img/gallery/nicolas-cage-couldnt-land-a-david-lynch-cameo-for-the-unbearable-weight-of-massive-talent/the-nicolas-cagedavid-lynch-reunion-we-deserved-1650027163.jpg",
    "https://i1.wp.com/film-book.com/wp-content/uploads/2017/04/nicolas-cage-windtalkers-01-600x350.jpg",
    "https://multiglom.files.wordpress.com/2015/01/the-rock-1996.jpg",
    "https://musingsfromus.com/wp-content/uploads/2012/09/Gone-In-60-Seconds-2000-ScreenShot-088.jpg",
    "https://assets.acasatv.ro/assets/acasatv/2010/05/07/image_galleries/2130/vampirii-fac-valva-la-hollywood-galerie-foto_12.jpg",
    "https://multiglom.files.wordpress.com/2015/01/birdy.png",
    "https://musingsfromus.com/wp-content/uploads/2012/07/National-Treasure-2004-ScreenShot-121.jpg",
    "https://3.bp.blogspot.com/-rng145WCKPQ/T6mi8M8Ho5I/AAAAAAAAAEc/CaZfH8dVLGA/s1600/WeatherMan06.jpg",
    "https://de.web.img3.acsta.net/r_1280_720/medias/nmedia/18/35/51/53/18458294.jpg",
    "https://www.episodi.fi/wp-content/uploads/nicolas-cage-world-trade-center.jpg",
    "https://1.bp.blogspot.com/-WZRyOwsfE-8/U1bVZbeMK9I/AAAAAAAAAMY/JEe1Ie4G5fE/s1600/nicolas-cage-fu-manchu-grindhouse.jpg",
    "https://multiglom.files.wordpress.com/2015/01/badlieu02.jpg",
    "https://2.bp.blogspot.com/-1LyVzMxNm7Q/W83_4TYmZKI/AAAAAAAAAIY/sjkzpcFyoFYVJ_ousNs2u5AGETVXhGLdwCLcBGAs/s1600/Nic%252BCage.png",
    "https://www.yam-mag.com/wp-content/uploads/2012/05/nicholas-cage-kick-ass.jpg",
]


def year_progress():
    """Returns a float between 0 and 1 representing the progress through the current year."""
    now = datetime.now()
    start_of_year = datetime(now.year, 1, 1)
    end_of_year = datetime(now.year + 1, 1, 1)
    total_seconds_in_year = (end_of_year - start_of_year).total_seconds()
    seconds_elapsed = (now - start_of_year).total_seconds()
    return seconds_elapsed / total_seconds_in_year


def is_not_blacklisted(dir_name: str) -> bool:
    return all(
        banned.lower() not in dir_name.lower() for banned in BLACKLISTED_DIR_NAMES
    )


def collect_photos_recursively(dir: str):
    result: list[tuple[str, str]] = []
    for entry in os.scandir(dir):
        if entry.is_file():
            content_type, _ = mimetypes.guess_type(entry.name)
            if content_type is not None:
                if content_type in [
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
                        f"ignoring file '{entry.path}' that is likely not an image or has unsupported format"
                    )
            else:
                logging.debug(
                    f"ignoring file '{entry.path}' for which content type could not be determined"
                )
        elif entry.is_dir():
            if is_not_blacklisted(entry.name):
                result.extend(collect_photos_recursively(entry.path))
            else:
                logging.debug(f"ignoring blacklisted directory '{entry.path}'")
    return result


class PhotoIndex:
    # First layer represents years, second layer represents subdirectories within years,
    # third layer represents photos within subdirectories.
    year_photos: list[list[list[tuple[str, str]]]]

    # Weights for each year, used for random selection.
    year_weights: list[float]

    # The time this index was created.
    time: datetime

    def __init__(self):
        logging.info("indexing photos...")

        year_entries: list[os.DirEntry[str]] = []
        for entry in os.scandir(PHOTO_DIR):
            if entry.is_dir():
                if entry.name.isnumeric():
                    if is_not_blacklisted(entry.name):
                        year_entries.append(entry)
                    else:
                        logging.debug(
                            f"ignoring blacklisted year directory '{entry.path}'"
                        )
                else:
                    logging.warning(
                        f"ignoring non-year directory found in root of photo directory '{entry.path}'"
                    )
            else:
                logging.warning(
                    f"ignoring non-directory found in root of photo directory '{entry.path}'"
                )

        year_entries.sort(key=lambda x: x.name)
        year_photos: list[list[list[tuple[str, str]]]] = []

        for entry in year_entries:
            subdir_entries: list[os.DirEntry[str]] = []
            for subentry in os.scandir(entry.path):
                if subentry.is_dir():
                    if is_not_blacklisted(subentry.name):
                        subdir_entries.append(subentry)
                    else:
                        logging.debug(
                            f"ignoring blacklisted year subdirectory '{subentry.path}'"
                        )
                else:
                    logging.warning(
                        f"ignoring non-directory found in year subdirectory '{subentry.path}'"
                    )

            subdir_entries.sort(key=lambda x: x.name)
            subdir_photos = []

            for subentry in subdir_entries:
                photos = collect_photos_recursively(subentry.path)
                if len(photos) > 0:
                    subdir_photos.append(
                        [
                            (os.path.relpath(path, PHOTO_DIR), content_type)
                            for path, content_type in photos
                        ]
                    )

            year_photos.append(subdir_photos)

        logging.info("indexing complete")

        self.year_photos = year_photos

        # First year gets 1, second 2, third 4, fourth 8, fifth 16, etc.
        self.year_weights = [2**i for i in range(len(year_photos))]

        # If there are photos for the current year, make the weight for the current year
        # proportional to the progress through the year to prevent the same photos from being
        # shown too often.
        latest_year = int(year_entries[-1].name)
        current_year = datetime.now().year
        if latest_year == current_year:
            self.year_weights[-1] = int(round(year_progress() * self.year_weights[-1]))

        self.time = datetime.now()

    def get_random_photo(self) -> tuple[str, str]:
        year = random.choices(self.year_photos, weights=self.year_weights, k=1)[0]
        subdir = random.choice(year)
        return random.choice(subdir)

    def is_outdated(self) -> bool:
        return (datetime.now() - self.time).total_seconds() > PHOTO_INDEX_INTERVAL_SECS


def run_photo_server(key: str):
    """Spawn a Bottle server to serve photos."""

    @route("/<path:path>")
    def send_photo(path: str):
        if request.query.key == key:
            return static_file(path, PHOTO_DIR)
        else:
            abort(401, "unauthorized")

    run(
        host=LOCAL_IP,
        port=LISTENING_PORT,
        quiet=True,
    )


def main():
    # Create random key for image server to prevent unauthorized access.
    key = str(uuid.uuid4())
    logging.debug(f"key: {key}")

    # Start the image server.
    thread = threading.Thread(target=run_photo_server, args=[key])
    thread.daemon = True
    thread.start()

    index = PhotoIndex()

    def path_to_url(path: str) -> str:
        return f"http://{LOCAL_IP}:{LISTENING_PORT}/{path}?key={key}"

    casts, _ = pychromecast.get_listed_chromecasts(friendly_names=[CAST_DEVICE_NAME])
    if len(casts) == 0:
        logging.error(f"chromecast '{CAST_DEVICE_NAME}' not found")
        sys.exit(1)
    elif len(casts) > 1:
        logging.error(f"multiple chromecasts found with name '{CAST_DEVICE_NAME}'")
        sys.exit(1)
    cast = casts[0]

    while True:
        if index.is_outdated():
            index = PhotoIndex()
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
                    if index.is_outdated():
                        index = PhotoIndex()

                    nic_url = random.choice(NICOLAS_CAGE)
                    content_type = "image/png" if ".png" in nic_url else "image/jpeg"
                    mc.play_media(nic_url, content_type)

                    time.sleep(NEXT_PHOTO_INTERVAL_SECS)
                    if cast.status.display_name != "Default Media Receiver":
                        break

                logging.info("finished casting")
            else:
                logging.debug("chromecast not idle")
        else:
            logging.warning("chromecast status unknown")

        time.sleep(CAST_CHECK_INTERVAL_SECS)


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    main()
