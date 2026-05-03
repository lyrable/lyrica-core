from __future__ import annotations

import sys
import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List

try:
    from config import GLOBAL_OFFSET_SECONDS, SNAP_TOLERANCE_RATIO
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from config import GLOBAL_OFFSET_SECONDS, SNAP_TOLERANCE_RATIO


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value for {name}: {value!r}") from exc


def _subbeat_to_beat_id(subbeat_index: int) -> str:
    beat_number = (subbeat_index // 4) + 1
    subbeat_number = (subbeat_index % 4) + 1
    return f"{beat_number}.{subbeat_number}"


def quantize_alignment(
    alignment_path: str | Path,
    rhythm_path: str | Path,
    theme_path: str | Path,
    orig_name: str,
    orig_artist: str,
    global_offset_seconds: float = GLOBAL_OFFSET_SECONDS,
) -> Path:
    alignment_file = Path(alignment_path)
    rhythm_file = Path(rhythm_path)
    theme_file = Path(theme_path)

    alignment_data = _load_json(alignment_file)
    rhythm_data = _load_json(rhythm_file)
    theme_data = _load_json(theme_file)

    current_time = time.strftime("%a, %d %b %Y %I:%M:%S %p %Z", time.gmtime())

    bpm = _safe_float(rhythm_data.get("bpm"), "bpm")
    vibe = rhythm_data.get("vibe") or []
    beats = rhythm_data.get("beats") or []
    if bpm <= 0:
        raise ValueError(f"Invalid BPM value: {bpm}")
    if not beats:
        raise ValueError("rhythm.json does not contain beats[0].")

    beat_zero = _safe_float(beats[0], "beats[0]")
    seconds_per_beat = 60.0 / bpm
    seconds_per_subbeat = seconds_per_beat / 4.0

    quantized_words: List[Dict[str, Any]] = []

    for item in alignment_data:
        word = str(item.get("word", "")).strip()
        if not word:
            continue

        raw_start = _safe_float(item.get("start"), f"{word}.start")
        raw_end = _safe_float(item.get("end"), f"{word}.end")

        shifted_start = raw_start + global_offset_seconds
        shifted_end = raw_end + global_offset_seconds

        start_subbeat_float = (shifted_start - beat_zero) / seconds_per_subbeat
        nearest = int(round(start_subbeat_float))
        snapped_start_subbeat = max(0, nearest if abs(nearest - start_subbeat_float) <= SNAP_TOLERANCE_RATIO else int(math.floor(start_subbeat_float)))

        if snapped_start_subbeat < 0:
            snapped_start_subbeat = 0

        end_subbeat_float = (shifted_end - beat_zero) / seconds_per_subbeat
        snapped_end_subbeat = int(round(end_subbeat_float))
        if snapped_end_subbeat <= snapped_start_subbeat:
            snapped_end_subbeat = snapped_start_subbeat + 1

        duration_subbeats = snapped_end_subbeat - snapped_start_subbeat

        quantized_words.append(
            {
                "word": word,
                "beat_id": _subbeat_to_beat_id(snapped_start_subbeat),
                "duration_beats": duration_subbeats,
            }
        )

    master_data: Dict[str, Any] = {
        "data": {
            "orig_name": orig_name,
            "orig_artist": orig_artist,
            "album": "placeholder",
            "release_date": "1970.01.01"
        },
        "metadata": {
            "added": current_time,
            "updated": current_time,
            "times_loaded": 1,
        },
        "bpm": bpm,
        "offset_seconds": global_offset_seconds,
        "vibe": vibe,
        "theme": theme_data,
        "words": quantized_words,
    }

    output_file = alignment_file.parent / "master_sync.json"
    
    output_file.write_text(
        json.dumps(master_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_file
