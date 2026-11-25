"""Download the UI fonts and the raw character artwork into assets/ (run once).

* Fonts: static TTF instances of Bricolage Grotesque 700, Inter 400/500/600 and
  JetBrains Mono 400/500 from Google Fonts (all SIL OFL). Static files are
  needed because pygame renders variable fonts at their default weight only.
* Artwork: the original, unprocessed images listed by the public
  dragonball-api.com character endpoint, saved to assets/avatars/source/.
  tools/prepare_avatars.py turns them into portraits.

    python tools/fetch_assets.py              # fonts + artwork
    python tools/fetch_assets.py --fonts-only
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "assets" / "fonts"
SOURCE_DIR = ROOT / "assets" / "avatars" / "source"
API = "https://dragonball-api.com/api/characters?limit=100"
# An old Android user agent makes Google Fonts answer with plain TTF files.
FONT_UA = (
    "Mozilla/5.0 (Linux; U; Android 2.2; en-us; Nexus One Build/FRF91) "
    "AppleWebKit/533.1 (KHTML, like Gecko) Version/4.0 Mobile Safari/533.1"
)
USER_AGENT = "griductive-asset-fetch/1.0"

# file name -> Google Fonts css2 family spec. Bricolage Grotesque is pinned to
# optical size 48: the display cut used for 20-30 px titles (the default
# opsz 14 text cut is wider and looser than the design reference).
FONTS = {
    "BricolageGrotesque-Bold.ttf": "Bricolage Grotesque:opsz,wght@48,700",
    "Inter-Regular.ttf": "Inter:wght@400",
    "Inter-Medium.ttf": "Inter:wght@500",
    "Inter-SemiBold.ttf": "Inter:wght@600",
    "JetBrainsMono-Regular.ttf": "JetBrains Mono:wght@400",
    "JetBrainsMono-Medium.ttf": "JetBrains Mono:wght@500",
}

# API (Spanish/alternate) names -> English slugs used by puzzles.
SLUGS = {
    "Freezer": "frieza",
    "Celula": "cell",
    "Tenshinhan": "tien",
    "Master Roshi": "roshi",
    "Bills": "beerus",
    "Mr. Satan": "mr-satan",
    "Android 20 (Dr. Gero)": "android-20",
    "Vegetto": "vegito",
    "Kaio del norte (Kaito)": "king-kai",
}


def slug(name: str) -> str:
    name = name.strip()
    return SLUGS.get(name) or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fetch(url: str, agent: str = USER_AGENT) -> bytes:
    parts = urllib.parse.urlsplit(url)
    target = urllib.parse.urlunsplit(
        parts._replace(path=urllib.parse.quote(parts.path))
    )
    request = urllib.request.Request(target, headers={"User-Agent": agent})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except urllib.error.URLError:
        # Some Windows Pythons miss CA certificates; curl uses the OS store.
        result = subprocess.run(
            ["curl", "-fsSL", "-m", "60", "-A", agent, target],
            capture_output=True,
            check=True,
        )
        return result.stdout


def fetch_fonts(force: bool = False) -> None:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, spec in FONTS.items():
        path = FONT_DIR / filename
        if path.exists() and not force:
            continue
        query = urllib.parse.urlencode({"family": spec})
        css = fetch(f"https://fonts.googleapis.com/css2?{query}", FONT_UA).decode()
        match = re.search(r"url\((https://[^)]+\.ttf)\)", css)
        if match is None:
            raise RuntimeError(f"no TTF found for {spec}")
        path.write_bytes(fetch(match.group(1)))
        print("font", filename)


def fetch_artwork() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(fetch(API))
    for item in data.get("items", data):
        url = item["image"]
        suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower() or ".png"
        path = SOURCE_DIR / f"{slug(item['name'])}{suffix}"
        if path.exists():
            continue
        try:
            path.write_bytes(fetch(url))
            print("art", path.name)
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"skip {item['name']}: {exc}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fonts-only", action="store_true")
    parser.add_argument(
        "--refresh-fonts", action="store_true", help="download fonts again"
    )
    args = parser.parse_args()
    fetch_fonts(force=args.refresh_fonts)
    if not args.fonts_only:
        fetch_artwork()


if __name__ == "__main__":
    main()
