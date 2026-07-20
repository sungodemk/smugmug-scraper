import os
import sys
import json
import re
import argparse
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from colored import fg, attr

REQUEST_TIMEOUT = 30


def load_input_config(input_path=None):
    default_path = Path(__file__).resolve().parent / "input.md"
    config_path = Path(input_path) if input_path else default_path

    if not config_path.exists():
        return {}

    config = {}
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip().strip('`"\'')
        if key in {"username", "user"}:
            config["user"] = value
        elif key in {"session", "smsess"}:
            config["session"] = value

    return config


def resolve_args(args, config):
    if not getattr(args, "user", None) and config.get("user"):
        args.user = config["user"]
    if not getattr(args, "session", None) and config.get("session"):
        args.session = config["session"]
    return args


def build_parser():
    parser = argparse.ArgumentParser(description="SmugMug Downloader")
    parser.add_argument("-s", "--session", help="session ID (required if user is password protected)")
    parser.add_argument("-u", "--user", help="username (from URL, USERNAME.smugmug.com)")
    parser.add_argument("-o", "--output", default="output/", help="output directory")
    parser.add_argument("--albums", help="specific album names to download, split by $.")
    parser.add_argument("--threads", type=int, default=8, help="number of concurrent downloads (default: 8)")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    config = load_input_config()
    args = resolve_args(args, config)

    if not args.user:
        parser.error("Missing username. Put it in input.md or pass -u/--user.")
    if not args.session:
        parser.error("Missing session. Put it in input.md or pass -s/--session.")

    endpoint = "https://www.smugmug.com"
    session = requests.Session()
    session.cookies.update({"SMSESS": args.session})

    if args.output[-1:] != "/" and args.output[-1:] != "\\":
        output_dir = args.output + "/"
    else:
        output_dir = args.output

    specific_albums = None
    if args.albums:
        specific_albums = [x.strip() for x in args.albums.split("$")]

    def get_json(url):
        num_retries = 5
        for i in range(num_retries):
            try:
                r = session.get(endpoint + url, timeout=REQUEST_TIMEOUT)
                soup = BeautifulSoup(r.text, "html.parser")
                pres = soup.find_all("pre")
                return json.loads(pres[-1].text)
            except (IndexError, requests.exceptions.RequestException):
                print("ERROR: JSON output not found for URL: %s" % url)
                if i + 1 < num_retries:
                    print("Retrying...")
                else:
                    print("ERROR: Retries unsuccessful. Skipping this request.")
                continue
        return None

    def download_image(image, album_path):
        image_path = album_path + "/" + re.sub(r"[^\w\-_\. ]", "_", image["FileName"])

        if os.path.isfile(image_path):
            return

        largest_media = "LargestVideo" if "LargestVideo" in image["Uris"] else "ImageDownload" if "ImageDownload" in image["Uris"] else "LargestImage"
        if largest_media in image["Uris"]:
            image_req = get_json(image["Uris"][largest_media]["Uri"])
            if image_req is None:
                print("ERROR: Could not retrieve image for %s" % image["Uris"][largest_media]["Uri"])
                return
            download_url = image_req["Response"][largest_media]["Url"]
        else:
            download_url = image["ArchivedUri"]

        try:
            r = session.get(download_url, timeout=REQUEST_TIMEOUT)
            with open(image_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
        except requests.exceptions.RequestException as ex:
            print("Could not fetch: " + str(ex))
        except UnicodeEncodeError as ex:
            print("Unicode Error: " + str(ex))
        except urllib.error.HTTPError as ex:
            print("HTTP Error: " + str(ex))

    print("Downloading album list...", end="")
    albums = get_json("/api/v2/folder/user/%s!albumlist" % args.user)
    if albums is None:
        print("ERROR: Could not retrieve album list.")
        sys.exit(1)
    print("done.")

    try:
        albums["Response"]["AlbumList"]
    except KeyError:
        sys.exit("No albums were found for the user %s. The user may not exist or may be password protected." % args.user)

    print("Creating output directories...", end="")
    for album in albums["Response"]["AlbumList"]:
        if specific_albums is not None and album["Name"].strip() not in specific_albums:
            continue
        directory = output_dir + album["UrlPath"][1:]
        if not os.path.exists(directory):
            os.makedirs(directory)
    print("done.")

    def format_label(s, width=24):
        return s[:width].ljust(width)

    bar_format = "{l_bar}{bar:-2}| {n_fmt:>3}/{total_fmt:<3}"

    for album in tqdm(albums["Response"]["AlbumList"], position=0, leave=True, bar_format=bar_format,
                      desc=f"{fg('yellow')}{attr('bold')}{format_label('All Albums')}{attr('reset')}"):
        if specific_albums is not None and album["Name"].strip() not in specific_albums:
            continue

        album_path = output_dir + album["UrlPath"][1:]
        images = get_json(album["Uri"] + "!images")
        if images is None:
            print("ERROR: Could not retrieve images for album %s (%s)" % (album["Name"], album["Uri"]))
            continue

        if "AlbumImage" in images["Response"]:
            next_images = images
            while "NextPage" in next_images["Response"]["Pages"]:
                next_images = get_json(next_images["Response"]["Pages"]["NextPage"])
                if next_images is None:
                    print("ERROR: Could not retrieve images page for album %s (%s)" % (album["Name"], album["Uri"]))
                    continue
                images["Response"]["AlbumImage"].extend(next_images["Response"]["AlbumImage"])

            album_images = images["Response"]["AlbumImage"]
            with ThreadPoolExecutor(max_workers=args.threads) as executor:
                futures = [executor.submit(download_image, image, album_path) for image in album_images]
                for _ in tqdm(as_completed(futures), total=len(futures), position=1, leave=True, bar_format=bar_format,
                              desc=f"{attr('bold')}{format_label(album['Name'])}{attr('reset')}"):
                    pass

    print("Completed.")


if __name__ == "__main__":
    main()
    