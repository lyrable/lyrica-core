import os
import re
import requests
from pathlib import Path
from typing import Optional, Tuple

import lyricsgenius
from dotenv import load_dotenv 

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

GENIUS_ACCESS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")

def _clean_title(title: str) -> str:     #cleanup
    cleaned = title.strip()
    cleaned = re.sub(r"\s*[\(\[\{][^)\]\}]*?(remaster|live|version|edit|mix)[^)\]\}]*?[\)\]\}]\s*", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*-\s*(live|.*remaster(ed)?|radio edit|mono|stereo)\b.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def _search_song(genius: lyricsgenius.Genius, artist: str, title: str):
    song = genius.search_song(title, artist)
    if not song and "," in artist:
        song = genius.search_song(title, artist.split(",")[0].strip())
    return song

def fetch_song_data(artist: str, title: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    if not artist or not title:
        return None, None, None, None

    token = (GENIUS_ACCESS_TOKEN or "").strip()
    if not token:
        print("No Genius Token found! Make sure to setup the .env file correctly (as in the readme.py)")
        return None, None, None, None

    cleaned_title = _clean_title(title)

    try:
        genius = lyricsgenius.Genius(token)
        song = _search_song(genius, artist, cleaned_title)

        if not song:
            return None, None, None, None

        lyrics: Optional[str] = None
        if song.lyrics:
            lyrics = re.sub(r"^.*Lyrics", "", song.lyrics)
            lyrics = re.sub(r"\d*Embed$", "", lyrics).strip()

        cover_url = getattr(song, "song_art_image_url", None)
        album_data = getattr(song, "album", None)
        album_name = album_data["name"]
        release_date = album_data.get("release_date")
        return lyrics, cover_url, album_name, release_date
    except Exception as e:
        print(f"Genius API Error: {e}")
        return None, None, None, None

def download_cover_image(image_url: str, output_path: Path) -> Optional[Path]:
    if not image_url:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(image_url, timeout=20)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return output_path
    except Exception as e:
        print(f"Cover download error: {e}")
        return None

def fetch_lyrics(artist: str, title: str) -> Optional[str]:
    lyrics, _cover_url = fetch_song_data(artist, title)
    return lyrics