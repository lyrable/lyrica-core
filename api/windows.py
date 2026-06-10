import asyncio
import sys
from pathlib import Path
import time

from typing import Any, Dict, Optional

from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager

try:
    from config import POLL_INTERVAL, WIN_DEBUG_ACTIVE, VISUALISE_LYRICS
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from config import POLL_INTERVAL, WIN_DEBUG_ACTIVE, VISUALISE_LYRICS

from processor.data_cacher import get_song_data
from frontend.console_visualiser import stop_visualiser, visualise


async def get_media_info() -> Optional[Dict[str, str]]:
    try:
        manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        if manager is None:
            return None

        session = manager.get_current_session()
        if session is None:
            return None

        media_properties = await session.try_get_media_properties_async()
        playback_info = session.get_playback_info()
        status_value: Any = getattr(playback_info, "playback_status", None)

        status_name = getattr(status_value, "name", str(status_value))
        if status_name not in {"Playing", "Paused"}:
            status_name = "Paused" if "paused" in status_name.lower() else "Playing" if "playing" in status_name.lower() else status_name

        title = (media_properties.title or "").strip()
        artist = (media_properties.artist or "").strip()

        if title and artist:
            return {
                "title": title,
                "artist": artist,
                "playback_status": status_name,
            }
    except Exception:
        return None


async def watch_media_changes(poll_interval: float = POLL_INTERVAL, debug: bool = WIN_DEBUG_ACTIVE) -> None:
    previous_signature: Optional[tuple[str, str, str]] = None
    had_session = True

    while True:
        media_info = await get_media_info()

        if media_info is None:
            if had_session:
                print("No active media session.")
                if VISUALISE_LYRICS:
                    stop_visualiser()
                had_session = False
                previous_signature = None
        else:
            start_time = time.time()
            had_session = True
            current_signature = (
                media_info["title"],
                media_info["artist"],
                media_info["playback_status"],
            )
            if current_signature != previous_signature and media_info["playback_status"] == 'Playing':
                aligned_path = get_song_data(
                    artist=media_info["artist"],
                    title=media_info["title"],
                )
                if aligned_path:
                    entry_point = time.time() - start_time
                    track_key = (media_info["title"], media_info["artist"])
                    if VISUALISE_LYRICS:
                        visualise(aligned_path, entry_point, track_key)
                    
                    if debug:
                        print(
                            f'Currently playing: {media_info["title"]} '
                            f'by {media_info["artist"]}. '
                            f'Status: {media_info["playback_status"]}'
                        )
                else:
                    print("Oops! the song is instrumental! we cannot handle this one, yet...")
                previous_signature = current_signature

        await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    try:
        print("Started Windows listener...")
        asyncio.run(watch_media_changes())
    except KeyboardInterrupt:
        print("Stopped media watcher.")