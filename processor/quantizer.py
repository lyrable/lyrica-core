from __future__ import annotations

import sys
import json
import math
from pathlib import Path
from typing import Any

try:
    from config import GLOBAL_OFFSET_SECONDS, SNAP_TOLERANCE_RATIO
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from config import GLOBAL_OFFSET_SECONDS, SNAP_TOLERANCE_RATIO

from processor.syllabifier import syllabify_word


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value for {name}: {value!r}") from exc


def _subbeat_to_beat_id(subbeat_index: int) -> float:
    beat_number = (subbeat_index // 4) + 1
    subbeat_number = (subbeat_index % 4) + 1

    return round(beat_number + subbeat_number / 10, 1)


def quantize_alignment(
    alignment_path: str | Path,
    rhythm_path: str | Path,
    theme_path: str | Path,
    orig_name: str,
    orig_artist: str,
    album_id: str | None = None,
    global_offset_seconds: float = GLOBAL_OFFSET_SECONDS,
) -> Path:
    alignment_file = Path(alignment_path)

    alignment_data = _load_json(alignment_file)
    rhythm_data = _load_json(Path(rhythm_path))
    theme_data = _load_json(Path(theme_path))

    bpm = _safe_float(rhythm_data.get("bpm"), "bpm")
    beats = rhythm_data.get("beats") or []
    vibe = rhythm_data.get("vibe") or {}

    if bpm <= 0:
        raise ValueError(f"Invalid BPM: {bpm}")
    if not beats:
        raise ValueError("rhythm.json has no beats[]")

    beat_zero = _safe_float(beats[0], "beats[0]")
    seconds_per_subbeat = (60.0 / bpm) / 4.0

    words = []

    for item in alignment_data:
        word = str(item.get("word", "")).strip()
        if not word:
            continue

        shifted_start = _safe_float(item["start"], f"{word}.start") + global_offset_seconds
        shifted_end = _safe_float(item["end"],   f"{word}.end")   + global_offset_seconds

        start_f = (shifted_start - beat_zero) / seconds_per_subbeat
        nearest = int(round(start_f))
        snap = max(0, nearest if abs(nearest - start_f) <= SNAP_TOLERANCE_RATIO else int(math.floor(start_f)))

        end_f = (shifted_end - beat_zero) / seconds_per_subbeat
        snap_end = max(snap + 1, int(round(end_f)))
        duration = snap_end - snap

        beat_id = _subbeat_to_beat_id(snap)
        syllables = syllabify_word(word, duration)

        # format: [word, beat_id, duration, [syllables offsets]] or [word, beat_id, duration] if there is only one syllable
        entry: list = [word, beat_id, duration]
        if syllables:
            entry.append(syllables)
        words.append(entry)

    theme_data.pop("image_base64", None) # album cover is now taken from album_id in the database

    master: dict = {
        "d": {"n": orig_name, "a": orig_artist},
        "bpm": round(bpm, 2),
        "off": round(global_offset_seconds, 3),
        "vibe": vibe,
        "theme": theme_data,
        "words": words,
    }
    if album_id:
        master["album_id"] = album_id

    output_file = alignment_file.parent / "master_sync.json"
    output_file.write_text(
        json.dumps(master, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return output_file