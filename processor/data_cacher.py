import re
import os
import sys
from pathlib import Path
from typing import Optional, Tuple
from yt_dlp.utils import DownloadError
import anyascii
import json

from api.genius import download_cover_image, fetch_song_data
from api.youtube import download_audio
from processor.audio_separator import get_vocals
from processor.alignment_engine import align_lyrics, detect_language
from processor.audio_analyzer import analyze_audio
from processor.quantizer import quantize_alignment
from processor.color_analyzer import analyze_cover, image_to_base64
from server.database import get_pool, get_track, upsert_track, insert_sync, upsert_album, get_sync


try:
    from config import SERVER_MODE, PIPELINE_DEBUG_ACTIVE, CLEAR_PIPELINE_ON_NEW_SONG, KEEP_PIPELINE_FILES, DATABASE_URL
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from config import SERVER_MODE, PIPELINE_DEBUG_ACTIVE, CLEAR_PIPELINE_ON_NEW_SONG, KEEP_PIPELINE_FILES, DATABASE_URL

def _debug_print(*args: str, **kwargs: str):
    if PIPELINE_DEBUG_ACTIVE:
        print("[PIPELINE DEBUG]", *args, **kwargs)

def _clean_song_dir(directory: str, keep_files: list[str]):
    for file_path in directory.iterdir():
        if file_path.exists() and file_path not in keep_files:
            try:
                file_path.unlink()
            except Exception as e:
                _debug_print(f"Error deleting {file_path}: {e}")
        
def _slugify(value: str) -> str:
    normalized = anyascii.anyascii(value)
    normalized = normalized.strip().lower()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^a-z0-9_\-]", "", normalized)
    return normalized.strip("_")

async def get_song_data(artist: str, title: str) -> Tuple[str, Path]:
    if CLEAR_PIPELINE_ON_NEW_SONG and PIPELINE_DEBUG_ACTIVE:
        os.system('cls' if os.name == 'nt' else 'clear')

    _debug_print(f"Proceeding song: {title} by {artist}")
    pool = await get_pool(DATABASE_URL) # placeholder, will move to anpther script when moving away from windows.py root

    folder_name = _slugify(f"{artist} {title}")
    song_dir = Path("data") / folder_name
    lyrics_path = song_dir / "lyrics.txt"
    audio_path = song_dir / "song.mp3"
    instrumental_path = song_dir / "instrumental.wav"
    rhythm_path = song_dir / "rhythm.json"
    vocals_path = song_dir / "vocals.wav"
    alignment_path = song_dir / "alignment.json"
    master_sync_path = song_dir / "master_sync.json"
    cover_path = song_dir / "cover.jpg"
    theme_path = song_dir / "theme.json"

    song_dir.mkdir(parents=True, exist_ok=True)
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    lyrics: str = ""
    need_lyrics = not lyrics_path.exists()
    need_cover = not cover_path.exists()
    fetched_lyrics: Optional[str] = None
    cover_url: Optional[str] = None

    track_id = await get_track(pool, folder_name)
    if track_id:
        _debug_print("Found master_sync.json. proceeding...")
    else:
        _debug_print("Couldnt find master_sync.json, catching up the whole pipeline...")
        if need_lyrics or need_cover:
            fetched_lyrics, cover_url, album_name, release_date = fetch_song_data(artist, title)

        if lyrics_path.exists():
            _debug_print("Lyrics found.")
            lyrics = lyrics_path.read_text(encoding="utf-8")
        else:
            _debug_print("Lyrics not found, downloading...")
            lyrics = fetched_lyrics or ""
            lyrics_path.write_text(lyrics, encoding="utf-8")
        
        if lyrics_path.read_text(encoding="utf-8"):
            is_instrumental = False
        else:
            is_instrumental = True

        if cover_path.exists():
            _debug_print("Cover found.")
        else:
            _debug_print("Cover not found, downloading...")
            if cover_url:
                download_cover_image(cover_url, cover_path)
                analyze_cover(cover_path)
                _debug_print("Broke the cover down by primary colors...")
            else:
                _debug_print("Cover URL not found in Genius response.")

        if audio_path.exists():
            _debug_print("Audio found.")
        else:
            _debug_print("Audio not found, downloading...")
            try:
                audio_path = download_audio(artist, title, audio_path)
            except DownloadError as e:
                print(f"[LYRICA ERROR] Ошибка скачивания с YouTube: {e}")

        if instrumental_path.exists() and vocals_path.exists():
            _debug_print("Vocals and Instrumental (separated) exist.")
        elif is_instrumental:
            _debug_print("Song is already instrumental, skipping separation...")
        else:
            _debug_print("Vocals and instrumental not found, separating...")
            get_vocals(audio_path, song_dir)

        if rhythm_path.exists():
            _debug_print("rhythm file exists.")
        elif is_instrumental and audio_path.exists():
            _debug_print("breaking down rhythm patterns using original audio...")
            _, bpm, duration = analyze_audio(audio_path)
        else:
            _debug_print("breaking down rhythm patterns using instrumental...")
            _, bpm, duration = analyze_audio(instrumental_path)

        if alignment_path.exists():
            _debug_print("alignment.json exists.")
        elif is_instrumental:
            _debug_print("Couldnt find the lyrics, the song is instrumental/lyrics do not exist.")
        else:
            _debug_print("Couldnt find alignment.json, aligning...")
            align_lyrics(vocals_path, lyrics_path)

        if is_instrumental:
            _debug_print("lyrics do not exist, skipping creation of master_alignment.")
        else:
            _debug_print("parsing the alignment and rhythm to create master_sync.json...")
            language = detect_language(lyrics)
            quantize_alignment(alignment_path, rhythm_path, theme_path, title, artist, language)
        
        _debug_print("Filling up the database...")
        cover_base64 = image_to_base64(Path(cover_path))
        album_id = await upsert_album(pool, album_name, artist, cover_base64, release_date)
        track_id = await upsert_track(pool, {
            "title": title,
            "artist": artist,
            "slug": folder_name,
            "bpm": bpm,
            "album_id": album_id,
            "duration": duration
        })
        if master_sync_path.exists():
            with open(master_sync_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
                await insert_sync(pool, track_id, json_data, None)

        if not KEEP_PIPELINE_FILES:
                keep = [None]
                _clean_song_dir(song_dir, keep)
                _debug_print("Cleaned leftover pipeline files.")

    return master_sync_path
