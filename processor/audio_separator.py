from __future__ import annotations

import os
import shutil
import subprocess
import time
import sys
from pathlib import Path
from typing import Tuple

import imageio_ffmpeg

python_exe = sys.executable

def _ensure_ffmpeg_on_path() -> None:
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)

    target = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    if not os.path.exists(target):
        shutil.copy2(ffmpeg_exe, target)

    if ffmpeg_dir not in os.environ["PATH"]:
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]


def get_vocals(input_path: str | Path, output_dir: str | Path) -> Tuple[Path, Path]:
    source = Path(input_path)
    cache_dir = Path(output_dir)
    vocals_target = cache_dir / "vocals.wav"
    instrumental_target = cache_dir / "instrumental.wav"

    if not source.exists():
        raise FileNotFoundError(f"Input audio file does not exist: {source}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    _ensure_ffmpeg_on_path()

    start_time = time.perf_counter()
    
    cmd = [
        str(python_exe),
        "-m", "demucs",
        "--two-stems", "vocals",
        "-n", "htdemucs",
        "-d", "cuda",
        "-o", str(cache_dir),
        str(source),
    ]
    
    subprocess.run(
        cmd,
        check=True,
    )
    
    elapsed_seconds = time.perf_counter() - start_time
    print(f"Separation completed in {elapsed_seconds:.2f} seconds.")

    stem_dir = cache_dir / "htdemucs" / source.stem
    vocals_out = stem_dir / "vocals.wav"
    instrumental_out = stem_dir / "no_vocals.wav"

    if not vocals_out.exists() or not instrumental_out.exists():
        raise RuntimeError(
            f"Demucs finished but expected files are missing in {stem_dir}. "
            f"Contents: {list(stem_dir.iterdir()) if stem_dir.exists() else 'directory not found'}"
        )

    vocals_out.rename(vocals_target)
    instrumental_out.rename(instrumental_target)

    return vocals_target, instrumental_target