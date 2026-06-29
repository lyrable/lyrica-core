from __future__ import annotations
import re
import os
import sys
import json
from pathlib import Path
from typing import Optional

import anyascii
from yt_dlp.utils import DownloadError

from api.genius import download_cover_image, fetch_song_data
from api.youtube import download_audio
from config import WORKER_SECRET, SERVER_URL
from processor.audio_separator import get_vocals
from processor.alignment_engine import align_lyrics, detect_language
from processor.audio_analyzer import analyze_audio
from processor.quantizer import quantize_alignment
from processor.color_analyzer import analyze_cover, image_to_base64
from server.database import (
    get_pool, get_track, link_track_artists, upsert_artist, upsert_album, upsert_track,
    insert_sync, get_sync, upload_track_audio
)

try:
    from config import (
        PIPELINE_DEBUG_ACTIVE, CLEAR_PIPELINE_ON_NEW_SONG,
        KEEP_PIPELINE_FILES, DATABASE_URL,
    )
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from config import (
        PIPELINE_DEBUG_ACTIVE, CLEAR_PIPELINE_ON_NEW_SONG,
        KEEP_PIPELINE_FILES, DATABASE_URL,
    )


def _debug_print(*args, **kwargs):
    if PIPELINE_DEBUG_ACTIVE:
        print("[PIPELINE DEBUG]", *args, **kwargs)


def slugify(value: str) -> str:
    s = anyascii.anyascii(value).strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_\-]", "", s)
    return s.strip("_")


def _clean_song_dir(directory: Path, keep_files: list[Path]) -> None:
    for file_path in directory.iterdir():
        if file_path not in keep_files:
            try:
                file_path.unlink()
            except Exception as e:
                _debug_print(f"Error deleting {file_path}: {e}")


async def get_song_data(artist: str, title: str) -> Path:
    if CLEAR_PIPELINE_ON_NEW_SONG and PIPELINE_DEBUG_ACTIVE:
        os.system("cls" if os.name == "nt" else "clear")

    _debug_print(f"Processing: {title} by {artist}")

    pool = await get_pool(DATABASE_URL)
    slug = slugify(f"{artist} {title}")
    song_dir = Path("data") / slug
    song_dir.mkdir(parents=True, exist_ok=True)

    # paths
    lyrics_path       = song_dir / "lyrics.txt"
    audio_path        = song_dir / "song.mp3"
    instrumental_path = song_dir / "instrumental.wav"
    vocals_path       = song_dir / "vocals.wav"
    rhythm_path       = song_dir / "rhythm.json"
    alignment_path    = song_dir / "alignment.json"
    master_sync_path  = song_dir / "master_sync.json"
    cover_path        = song_dir / "cover.jpg"
    theme_path        = song_dir / "theme.json"

    # early exit if already processed
    existing = await get_track(pool, slug)
    if existing:
        _debug_print("Track found in DB, skipping pipeline.")
        return master_sync_path

    # fetch metadata from Genius (one network call)
    fetched_lyrics: Optional[str] = None
    cover_url: Optional[str] = None
    album_name: Optional[str] = None
    release_date: Optional[str] = None

    if not lyrics_path.exists() or not cover_path.exists():
        fetched_lyrics, cover_url, album_name, release_date = fetch_song_data(artist, title)

    # lyrics
    if lyrics_path.exists():
        _debug_print("Lyrics found.")
        lyrics = lyrics_path.read_text(encoding="utf-8")
    else:
        _debug_print("Downloading lyrics…")
        lyrics = fetched_lyrics or ""
        lyrics_path.write_text(lyrics, encoding="utf-8")

    is_instrumental = not lyrics.strip()

    # cover
    if not cover_path.exists():
        if cover_url:
            _debug_print("Downloading cover…")
            download_cover_image(cover_url, cover_path)
        else:
            _debug_print("No cover URL from Genius.")

    if cover_path.exists():
        _, primary_color = analyze_cover(cover_path)
        _debug_print("Cover colors analyzed.")

    # audio
    if not audio_path.exists():
        _debug_print("Downloading audio…")
        try:
            audio_path = download_audio(artist, title, audio_path)
        except DownloadError as e:
            print(f"[LYRICA ERROR] YouTube download failed: {e}")

    # source separation
    if not is_instrumental:
        if instrumental_path.exists() and vocals_path.exists():
            _debug_print("Separated audio exists.")
        else:
            _debug_print("Separating vocals…")
            get_vocals(audio_path, song_dir)

    # rhythm analysis
    bpm: Optional[float] = None
    duration: Optional[float] = None

    if not rhythm_path.exists():
        source = audio_path if is_instrumental else instrumental_path
        if source.exists():
            _debug_print(f"Analyzing rhythm from {source.name}…")
            _, bpm, duration = analyze_audio(source)
    else:
        _debug_print("Rhythm file exists.")

    # alignment
    if not is_instrumental:
        if not alignment_path.exists():
            _debug_print("Aligning lyrics…")
            align_lyrics(vocals_path, lyrics_path)
        else:
            _debug_print("Alignment exists.")

        _debug_print("Building master_sync…")
        language = detect_language(lyrics)
        quantize_alignment(alignment_path, rhythm_path, theme_path, lyrics_path, title, artist, language)

    # write to DB (minimal round-trips)
    _debug_print("Writing to DB…")

    artist_id = await upsert_artist(pool, artist)

    album_id: Optional[int] = None
    if album_name:
        album_id = await upsert_album(
            pool, album_name, artist_id,
            cover_url=cover_url,
            release_date=release_date,
            primary_color=primary_color
        )

    track_id = await upsert_track(pool, {
        "title":    title,
        "slug":     slug,
        "album_id": album_id,
        "bpm":      bpm,
        "duration": duration
    })

    await link_track_artists(pool, track_id, [artist_id])
    """await upload_track_audio(
        mp3_path=audio_path,
        slug=slug,
        track_id=track_id,
        server_url=SERVER_URL,
        worker_secret=WORKER_SECRET,
        bitrate=None,
        sample_rate=None,
        duration=duration,
    )"""

    if master_sync_path.exists():
        with open(master_sync_path, encoding="utf-8") as f:
            json_data = json.load(f)
        await insert_sync(pool, track_id, json_data, created_by=None)

    # cleanup
    if not KEEP_PIPELINE_FILES:
        keep = [master_sync_path]
        _clean_song_dir(song_dir, keep)
        _debug_print("Cleaned pipeline files.")

    return master_sync_path