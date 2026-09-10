import os
import re
import urllib.request
from datetime import datetime, timezone

SOURCES = [
    ("Azerbaijan", "https://iptv-org.github.io/iptv/countries/az.m3u"),
    ("Azerbaijan", "https://iptv-org.github.io/iptv/languages/aze.m3u"),

    ("Turkiye", "https://iptv-org.github.io/iptv/countries/tr.m3u"),
    ("Turkiye", "https://iptv-org.github.io/iptv/languages/tur.m3u"),
    ("Turkiye", "https://itasli.github.io/TURKTV/index.m3u"),

    ("Russia", "https://iptv-org.github.io/iptv/countries/ru.m3u"),
    ("Russia", "https://iptv-org.github.io/iptv/languages/rus.m3u"),
]

OUTPUT_M3U = "docs/index.m3u"
OUTPUT_M3U8 = "docs/index.m3u8"
TEST_OUTPUT = "docs/test.m3u8"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/152 Safari/537.36"
)

INVALID_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif",
    ".webp", ".svg", ".ico"
)


def download(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT}
    )

    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8-sig", errors="ignore")


def valid_stream_url(url):
    url_lower = url.lower().split("?")[0]

    if url_lower.endswith(INVALID_EXTENSIONS):
        return False

    allowed = (
        "http://",
        "https://",
        "rtmp://",
        "rtsp://",
        "rtp://",
        "udp://",
    )

    return url.lower().startswith(allowed)


def clean_name(name):
    # control characters
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)

    # OTTPlayer parserini sadələşdirmək üçün
    name = name.replace(",", " - ")

    return name.strip()


def parse_playlist(content, country):
    lines = content.replace("\r\n", "\n").split("\n")

    channels = []

    current_name = None

    for raw in lines:
        line = raw.strip()

        if not line:
            continue

        # Kanal adı
        if line.startswith("#EXTINF"):
            if "," not in line:
                current_name = None
                continue

            current_name = clean_name(
                line.split(",", 1)[1]
            )
            continue

        # Bütün #EXTVLCOPT, #KODIPROP və s. ignore edilir
        if line.startswith("#"):
            continue

        # EXTINF-dən sonra gələn ilk real URL
        if current_name and valid_stream_url(line):
            channels.append({
                "name": current_name,
                "group": country,
                "url": line.strip(),
            })

            current_name = None

    return channels


def build_output(channels):
    output = ["#EXTM3U"]

    for ch in channels:
        output.append(f'#EXTINF:0,{ch["name"]}')
        output.append(f'#EXTGRP:{ch["group"]}')
        output.append(ch["url"])

    return "\n".join(output) + "\n"


def main():

    all_channels = []
    seen_urls = set()

    print("=" * 60)
    print("OTTPLAYER AZ + TR + RU PLAYLIST BUILDER")
    print("=" * 60)

    for country, url in SOURCES:

        print(f"\nDownloading: {country}")
        print(url)

        try:
            content = download(url)
            channels = parse_playlist(content, country)

            added = 0
            duplicate = 0

            for ch in channels:

                url_key = ch["url"].strip()

                if url_key in seen_urls:
                    duplicate += 1
                    continue

                seen_urls.add(url_key)

                all_channels.append(ch)

                added += 1

            print(f"Found      : {len(channels)}")
            print(f"Added      : {added}")
            print(f"Duplicates : {duplicate}")

        except Exception as e:
            print(f"ERROR: {e}")

    os.makedirs("docs", exist_ok=True)

    playlist = build_output(all_channels)

    with open(
        OUTPUT_M3U,
        "w",
        encoding="utf-8",
        newline="\n"
    ) as f:
        f.write(playlist)

    with open(
        OUTPUT_M3U8,
        "w",
        encoding="utf-8",
        newline="\n"
    ) as f:
        f.write(playlist)

    # OTTPlayer test üçün hər ölkədən ilk 3 kanal
    test_channels = []

    for country in ["Azerbaijan", "Turkiye", "Russia"]:

        found = [
            x for x in all_channels
            if x["group"] == country
        ][:3]

        test_channels.extend(found)

    with open(
        TEST_OUTPUT,
        "w",
        encoding="utf-8",
        newline="\n"
    ) as f:
        f.write(build_output(test_channels))

    print("\n" + "=" * 60)
    print(f"TOTAL: {len(all_channels)}")
    print("Created:")
    print(OUTPUT_M3U)
    print(OUTPUT_M3U8)
    print(TEST_OUTPUT)
    print("=" * 60)


if __name__ == "__main__":
    main()
