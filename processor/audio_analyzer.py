from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import librosa
import numpy as np


def _to_float(value: Any) -> float:
    if isinstance(value, (np.ndarray, np.float32, np.float64)):
        return float(np.mean(value))
    return float(value)


def _to_float_list(values: np.ndarray) -> List[float]:
    return [float(v) for v in values.tolist()]


def analyze_audio(audio_path: str | Path) -> Path:
    audio_file = Path(audio_path)
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    y, sr = librosa.load(str(audio_file), sr=22050, mono=True)

    # Ритм
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    # Onsets
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units="frames")
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    # Насколько трек "громкий" и мощный
    rms = librosa.feature.rms(y=y)
    energy = _to_float(np.max(rms))

    # Преобладание высоких или низких частот
    # Чем выше значение, тем "тоньше" и "звонче" звук
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    brightness = _to_float(centroid) / (sr / 2) # Нормализация относительно частоты Найквиста

    # Помогает понять, насколько спектр забит звуком (шумный рок vs чистый эмбиент)
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)
    roughness = _to_float(rolloff) / (sr / 2)

    rhythm_data: Dict[str, Any] = {
        "bpm": _to_float(tempo),
        "vibe": {
            "energy": round(energy * 10, 3),
            "brightness": round(brightness, 3),
            "roughness": round(roughness, 3),
        },
        "beats": _to_float_list(beat_times),
        "onsets": _to_float_list(onset_times),
    }

    output_path = audio_file.parent / "rhythm.json"
    output_path.write_text(
        json.dumps(rhythm_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path