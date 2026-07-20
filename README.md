# SmugMug Downloader

A command-line tool that downloads every photo and video from a SmugMug user's albums, preserving the album folder structure. Works with public galleries and, if you supply your session cookie, password-protected ones too.

## Requirements

- Python 3
- pip

## Installation

```bash
git clone <this-repo-url>
cd smugmug-scraper
pip install -r requirements.txt
```

## Usage

### Basic (public galleries)

```bash
python smdl.py 
```

Downloaded files are saved to `output/` by default, organized by album, mirroring the site's folder structure.

### Password-protected galleries

If the galleries you're downloading are password-protected, you need to pass your session cookie so the script can authenticate as you:

1. Log in to the SmugMug site in your web browser.
2. Open your browser's developer tools and find the `SMSESS` cookie for the smugmug.com domain.
3. Fill in your values in input.md
4. Run script

```bash
python smdl.py 
```

### Using an `input.md` config file instead of flags 

Instead of passing `-u`/`-s` on the command line every time, you can create an `input.md` file next to `smdl.py` with your username and session cookie:
fill in your values:
```
username: your-smugmug-username
session: your-smsess-cookie-value
```

### Options

| Flag | Description |
| --- | --- |
| `-u`, `--user` | SmugMug username (from the URL, `USERNAME.smugmug.com`). Required unless set in `input.md`. |
| `-s`, `--session` | Session cookie (`SMSESS`), required for password-protected users. Can also be set in `input.md`. |
| `-o`, `--output` | Output directory. Defaults to `output/`. |
| `--albums` | Only download specific albums, given as titles separated by `$`. Wrap in single quotes to avoid shell substitution, e.g. `--albums 'Album 1$Album 2'`. Defaults to all albums. |
| `--threads` | Number of concurrent image/video downloads. Defaults to `8`. |


Command-line flags always take precedence over `input.md` if both are provided.

## Notes

- Re-running the script skips files that were already downloaded, so it's safe to resume an interrupted download.
- Video files download as the largest available version; images use the highest-resolution version SmugMug exposes (or the original archived file if no direct download link is available).
