import os
import re
import urllib.request
from datetime import datetime, timezone

SOURCES = [
    # AZERBAIJAN
    (
        "Azerbaijan - Country",
        "https://iptv-org.github.io/iptv/countries/az.m3u"
    ),
    (
        "Azerbaijan - Language",
        "https://iptv-org.github.io/iptv/languages/aze.m3u"
    ),

    # TURKIYE
    (
        "Turkiye - Country",
        "https://iptv-org.github.io/iptv/countries/tr.m3u"
    ),
    (
        "Turkiye - Language",
        "https://iptv-org.github.io/iptv/languages/tur.m3u"
    ),
    (
        "Turkiye - TURKTV",
        "https://itasli.github.io/TURKTV/index.m3u"
    ),

    # RUSSIA
    (
        "Russia - Country",
        "https://iptv-org.github.io/iptv/countries/ru.m3u"
    ),
    (
        "Russia - Language",
        "https://iptv-org.github.io/iptv/languages/rus.m3u"
    ),
]

OUTPUT = "docs/index.m3u"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 Chrome/152 Safari/537.36"
)


def download(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def parse_m3u(content):
    lines = content.replace("\r\n", "\n").split("\n")

    entries = []
    current = []

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#EXTM3U"):
            continue

        if line.startswith("#EXTINF"):
            current = [line]
            continue

        if current:
            if line.startswith("#"):
                current.append(line)
                continue

            # first non-comment line after EXTINF = stream URL
            current.append(line)

            entries.append({
                "block": current.copy(),
                "url": line
            })

            current = []

    return entries


def normalize_url(url):
    return url.strip()


def main():
    all_entries = []
    seen_urls = set()

    print("=" * 70)
    print("AZ + TR + RU IPTV MERGER")
    print("=" * 70)

    for source_name, source_url in SOURCES:
        print(f"\nDownloading: {source_name}")

        try:
            content = download(source_url)
            entries = parse_m3u(content)

            added = 0
            duplicates = 0

            for entry in entries:
                key = normalize_url(entry["url"])

                if key in seen_urls:
                    duplicates += 1
                    continue

                seen_urls.add(key)
                all_entries.append(entry)
                added += 1

            print(f"Found      : {len(entries)}")
            print(f"Added      : {added}")
            print(f"Duplicates : {duplicates}")

        except Exception as e:
            print(f"ERROR: {source_name}")
            print(str(e))

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    output_lines = [
        '#EXTM3U',
        f'# Generated automatically: {generated}',
        f'# Total unique streams: {len(all_entries)}',
        '# Sources: public IPTV playlists',
        ''
    ]

    for entry in all_entries:
        output_lines.extend(entry["block"])
        output_lines.append("")

    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(output_lines))

    print("\n" + "=" * 70)
    print(f"TOTAL UNIQUE STREAMS: {len(all_entries)}")
    print(f"OUTPUT: {OUTPUT}")
    print("=" * 70)


if __name__ == "__main__":
    main()
