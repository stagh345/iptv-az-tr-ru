import os
import re
import urllib.request
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit


# ============================================================
# SOURCES
# ============================================================

SOURCES = [
    # Azerbaijan
    ("Azerbaijan", "https://iptv-org.github.io/iptv/countries/az.m3u"),
    ("Azerbaijan", "https://iptv-org.github.io/iptv/languages/aze.m3u"),

    # Turkiye
    ("Turkiye", "https://iptv-org.github.io/iptv/countries/tr.m3u"),
    ("Turkiye", "https://iptv-org.github.io/iptv/languages/tur.m3u"),
    ("Turkiye", "https://itasli.github.io/TURKTV/index.m3u"),

    # Russia
    ("Russia", "https://iptv-org.github.io/iptv/countries/ru.m3u"),
    ("Russia", "https://iptv-org.github.io/iptv/languages/rus.m3u"),
]


# ============================================================
# OUTPUT FILES
# ============================================================

OUTPUT_M3U = "docs/index.m3u"
OUTPUT_M3U8 = "docs/index.m3u8"
TEST_OUTPUT = "docs/test.m3u8"


# ============================================================
# SETTINGS
# ============================================================

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36"
)

TIMEOUT = 30

ALLOWED_SCHEMES = (
    "http://",
    "https://",
    "rtmp://",
    "rtsp://",
    "rtp://",
    "udp://",
)

INVALID_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".bmp",
)

# Əgər bütün source-lar problemli olsa,
# köhnə playlist-in üstünə boş/natamam fayl yazılmasın.
MINIMUM_TOTAL_CHANNELS = 20


# ============================================================
# DOWNLOAD
# ============================================================

def download(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/vnd.apple.mpegurl,"
                "application/x-mpegURL,"
                "audio/mpegurl,"
                "text/plain,"
                "*/*"
            ),
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT,
    ) as response:
        data = response.read()

    return data.decode(
        "utf-8-sig",
        errors="replace",
    )


# ============================================================
# CHANNEL NAME PARSER
# ============================================================

def extract_channel_name(extinf_line):
    """
    #EXTINF sətrində kanal adını tapır.

    Vacib:
    split(",", 1) istifadə etmirik.

    Səbəb:
    attribute daxilində vergül ola bilər:

    http-user-agent="Mozilla/5.0 (..., like Gecko)"

    Biz yalnız quote xaricindəki vergülü separator hesab edirik.
    """

    in_quotes = False
    escaped = False

    for index, char in enumerate(extinf_line):

        if escaped:
            escaped = False
            continue

        if char == "\\":
            escaped = True
            continue

        if char == '"':
            in_quotes = not in_quotes
            continue

        if char == "," and not in_quotes:
            name = extinf_line[index + 1:].strip()

            if name:
                return clean_name(name)

            return None

    return None


# ============================================================
# CHANNEL NAME CLEANER
# ============================================================

def clean_name(name):

    # Control characters silinir
    name = re.sub(
        r"[\x00-\x1f\x7f]",
        "",
        name,
    )

    # HTML tipli whitespace-lər
    name = name.replace("\u00a0", " ")

    # Birdən çox boşluğu birləşdir
    name = re.sub(
        r"\s+",
        " ",
        name,
    )

    # Sadə OTTPlayer parser üçün kanal adında
    # vergülü "-" ilə əvəz edirik.
    name = name.replace(",", " - ")

    return name.strip()


# ============================================================
# SUSPICIOUS / BROKEN NAME CHECK
# ============================================================

def valid_channel_name(name):

    if not name:
        return False

    suspicious = (
        "http-user-agent=",
        "group-title=",
        "tvg-id=",
        "tvg-name=",
        "tvg-logo=",
        "#ext",
    )

    lower_name = name.lower()

    for item in suspicious:
        if item in lower_name:
            return False

    return True


# ============================================================
# STREAM URL VALIDATION
# ============================================================

def valid_stream_url(url):

    if not url:
        return False

    url = url.strip()

    lower_url = url.lower()

    # Yalnız dəstəklənən protokollar
    if not lower_url.startswith(ALLOWED_SCHEMES):
        return False

    # Control character varsa reject
    if re.search(r"[\x00-\x1f\x7f]", url):
        return False

    # OTTPlayer üçün inline header sintaksisini
    # playlist-ə daxil etmirik.
    #
    # example:
    # https://server/live.m3u8|User-Agent=...
    #
    # Belə URL-lər bəzi player-lərdə işləyir,
    # amma OTTPlayer import parserini poza bilər.
    if "|" in url:
        return False

    try:
        # http(s) üçün path yoxlaması
        if lower_url.startswith(("http://", "https://")):
            parsed = urlsplit(url)

            path = parsed.path.lower()

            if path.endswith(INVALID_EXTENSIONS):
                return False

    except Exception:
        return False

    return True


# ============================================================
# PLAYLIST PARSER
# ============================================================

def parse_playlist(content, country):

    content = content.replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    )

    lines = content.split("\n")

    channels = []

    current_name = None

    for raw_line in lines:

        line = raw_line.strip()

        if not line:
            continue

        # ---------------------------------------------
        # Yeni kanal
        # ---------------------------------------------

        if line.upper().startswith("#EXTINF:"):

            current_name = extract_channel_name(line)

            if not valid_channel_name(current_name):
                current_name = None

            continue

        # ---------------------------------------------
        # Digər metadata-ları IGNORE edirik
        #
        # #EXTVLCOPT
        # #KODIPROP
        # #EXTHTTP
        # #EXTGRP
        # və s.
        # ---------------------------------------------

        if line.startswith("#"):
            continue

        # ---------------------------------------------
        # Stream URL
        # ---------------------------------------------

        if current_name:

            if valid_stream_url(line):

                channels.append(
                    {
                        "name": current_name,
                        "group": country,
                        "url": line.strip(),
                    }
                )

            # EXTINF-dən sonra ilk non-comment sətri
            # işlədikdən sonra reset edirik.
            current_name = None

    return channels


# ============================================================
# OUTPUT BUILDER
# ============================================================

def build_output(channels):

    output = [
        "#EXTM3U",
    ]

    for channel in channels:

        name = channel["name"]
        group = channel["group"]
        url = channel["url"]

        # Standard və sadə Extended M3U
        #
        # Yalnız iki sətir:
        #
        # #EXTINF:-1 group-title="Turkiye",TRT 1
        # https://...
        #
        # #EXTGRP və #EXTVLCOPT istifadə etmirik.

        output.append(
            f'#EXTINF:-1 group-title="{group}",{name}'
        )

        output.append(url)

    return "\n".join(output) + "\n"


# ============================================================
# SAFE FILE WRITE
# ============================================================

def safe_write(filename, content):

    temp_file = filename + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        file.write(content)

    os.replace(
        temp_file,
        filename,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("AZ + TR + RU OTTPLAYER PLAYLIST BUILDER")
    print("=" * 70)

    all_channels = []

    seen_urls = set()

    country_counts = {
        "Azerbaijan": 0,
        "Turkiye": 0,
        "Russia": 0,
    }

    successful_sources = 0
    failed_sources = 0

    # ========================================================
    # DOWNLOAD + PARSE
    # ========================================================

    for country, source_url in SOURCES:

        print()
        print("-" * 70)
        print(f"Country : {country}")
        print(f"Source  : {source_url}")

        try:

            content = download(source_url)

            channels = parse_playlist(
                content,
                country,
            )

            source_added = 0
            duplicates = 0

            for channel in channels:

                # Exact stream URL duplicate check
                url_key = channel["url"].strip()

                if url_key in seen_urls:
                    duplicates += 1
                    continue

                seen_urls.add(url_key)

                all_channels.append(channel)

                country_counts[country] += 1

                source_added += 1

            successful_sources += 1

            print(f"Parsed     : {len(channels)}")
            print(f"Added      : {source_added}")
            print(f"Duplicates : {duplicates}")
            print("Status     : OK")

        except HTTPError as error:

            failed_sources += 1

            print(
                f"Status     : HTTP ERROR {error.code}"
            )

        except URLError as error:

            failed_sources += 1

            print(
                f"Status     : URL ERROR - {error.reason}"
            )

        except Exception as error:

            failed_sources += 1

            print(
                f"Status     : ERROR - {error}"
            )

    # ========================================================
    # VALIDATION
    # ========================================================

    print()
    print("=" * 70)
    print("RESULT")
    print("=" * 70)

    print(
        f"Azerbaijan : "
        f"{country_counts['Azerbaijan']}"
    )

    print(
        f"Turkiye    : "
        f"{country_counts['Turkiye']}"
    )

    print(
        f"Russia     : "
        f"{country_counts['Russia']}"
    )

    print(
        f"TOTAL      : "
        f"{len(all_channels)}"
    )

    print(
        f"Sources OK : "
        f"{successful_sources}"
    )

    print(
        f"Sources ERR: "
        f"{failed_sources}"
    )

    # ---------------------------------------------
    # Playlist çox kiçikdirsə yazmırıq.
    # ---------------------------------------------

    if len(all_channels) < MINIMUM_TOTAL_CHANNELS:

        raise RuntimeError(
            "Too few channels were generated. "
            "Existing playlist will NOT be replaced."
        )

    # Hər üç ölkədən ən azı kanal olmalıdır
    for country, count in country_counts.items():

        if count == 0:

            raise RuntimeError(
                f"No channels found for {country}. "
                "Existing playlist will NOT be replaced."
            )

    # ========================================================
    # STABLE SORT
    # ========================================================

    all_channels.sort(
        key=lambda channel: (
            channel["group"],
            channel["name"].casefold(),
            channel["url"],
        )
    )

    # ========================================================
    # CREATE DOCS DIRECTORY
    # ========================================================

    os.makedirs(
        "docs",
        exist_ok=True,
    )

    # ========================================================
    # FULL PLAYLIST
    # ========================================================

    full_playlist = build_output(
        all_channels
    )

    safe_write(
        OUTPUT_M3U,
        full_playlist,
    )

    safe_write(
        OUTPUT_M3U8,
        full_playlist,
    )

    # ========================================================
    # TEST PLAYLIST
    #
    # Hər ölkədən ilk 3 kanal
    # ========================================================

    test_channels = []

    for country in (
        "Azerbaijan",
        "Turkiye",
        "Russia",
    ):

        selected = [
            channel
            for channel in all_channels
            if channel["group"] == country
        ][:3]

        test_channels.extend(selected)

    test_playlist = build_output(
        test_channels
    )

    safe_write(
        TEST_OUTPUT,
        test_playlist,
    )

    # ========================================================
    # FINISHED
    # ========================================================

    print()
    print("=" * 70)
    print("FILES CREATED SUCCESSFULLY")
    print("=" * 70)

    print(OUTPUT_M3U)
    print(OUTPUT_M3U8)
    print(TEST_OUTPUT)

    print()
    print(
        f"Test playlist channels: "
        f"{len(test_channels)}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
