from pathlib import Path

from yt_dlp import YoutubeDL

import imageio_ffmpeg
import sys

ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()  # path to bundled ffmpeg binary

try:
    from config import YT_COOKIES_LOCATION
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from config import YT_COOKIES_LOCATION

def download_audio(artist: str, title: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_base = output_path.with_suffix("")
    query = f"ytsearch1:{artist} - {title}"
    ydl_opts = {
    'format': 'bestaudio/best',
    'cookiefile': str(Path(YT_COOKIES_LOCATION)),
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
        }
    },
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    },
    'nocheckcertificate': True,
    "outtmpl": str(output_base) + ".%(ext)s",
    "quiet": True,
    "no_warnings": True,
    "ffmpeg_location": ffmpeg_path,
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }
    ],
}

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([query])

    return output_path