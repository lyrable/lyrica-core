import asyncio
import json
import re
from pathlib import Path
from typing import Any

import anyascii
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

#from processor.data_cacher import get_song_data
#from server.database import get_track
from tuna import start_server

app = FastAPI(title="Syllable Visualizer")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PROCESSING_STATUSES = ("downloading_lyrics", "downloading_mp3", "separating", "investigating", "aligning")
STATUS_INTERVAL_SECONDS = 2

MOCK_MASTER_SYNC: dict[str, Any] = {
    "data": {"orig_name": "Mock Track", "orig_artist": "Mock Artist"},
    "metadata": {"mock": True},
    "bpm": 160.0,
    "offset_seconds": 0.0,
    "words": [
        {"word": "Hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.4, "end": 0.9},
    ],
}

start_server()

def _slugify(value: str) -> str:
    normalized = anyascii.anyascii(value).strip().lower()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^a-z0-9_\-]", "", normalized)
    return normalized.strip("_")


def _load_master_sync(artist: str, title: str) -> dict[str, Any] | None:
    path = DATA_DIR / _slugify(f"{artist} {title}") / "master_sync.json"
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@app.websocket("/ws/visualizer")
async def visualizer_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            try:
                message = json.loads(await websocket.receive_text())
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps(
                    {"status": "error", "message": "Invalid JSON"}
                ))
                continue

            action = message.get("action")
            artist = message.get("artist")
            title = message.get("title")

            if action != "get_track":
                await websocket.send_text(json.dumps(
                    {"status": "error", "message": f"Unknown action: {action!r}"}
                ))
                continue

            if not artist or not title:
                await websocket.send_text(json.dumps(
                    {"status": "error", "message": "Missing required fields: artist, title"}
                ))
                continue

            master_sync = _load_master_sync(artist, title)
            if master_sync is not None:
                await websocket.send_text(json.dumps(
                    {"status": "ready", "data": master_sync}
                ))
                continue

            for status in PROCESSING_STATUSES:
                await asyncio.sleep(STATUS_INTERVAL_SECONDS)
                await websocket.send_text(json.dumps({"status": status}))
            await websocket.send_text(json.dumps(
                {"status": "ready", "data": MOCK_MASTER_SYNC}
            ))

    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    except Exception:
        pass