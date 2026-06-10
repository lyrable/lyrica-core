from __future__ import annotations

import os
import sys
import shutil
import imageio_ffmpeg

import json
import re
from pathlib import Path
from typing import Dict, List

import whisperx
import torch
import gc
from lingua import Language, LanguageDetectorBuilder

import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pyannote.audio.core.io")
warnings.filterwarnings("ignore", category=UserWarning)
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

_LINGUA_TO_WHISPERX = {
    Language.ENGLISH: "en",
    Language.RUSSIAN: "ru",
}

_detector = LanguageDetectorBuilder.from_languages(*_LINGUA_TO_WHISPERX.keys()).build()


if sys.platform == 'win32': #костыль, увы
    venv_site_packages = os.path.join(os.path.dirname(sys.executable), "Lib", "site-packages")
    cuda_libs = [
        os.path.join(venv_site_packages, "nvidia", "cublas", "bin"),
        os.path.join(venv_site_packages, "nvidia", "cudnn", "bin"),
    ]
    for path in cuda_libs:
        if os.path.exists(path):
            os.add_dll_directory(path)
            print(f"Added DLL directory: {path}")

def _ensure_ffmpeg_on_path() -> None:
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)

    target = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    if not os.path.exists(target):
        shutil.copy2(ffmpeg_exe, target)

    if ffmpeg_dir not in os.environ["PATH"]:
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]

def _detect_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"

def _free_cuda_cache() -> None:
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()

def _clean_lyrics(raw_text: str) -> str:
    cleaned = re.sub(r"\[[^\]]*\]", "", raw_text)  # remove [Verse], [Chorus] etc
    cleaned = cleaned.replace("\\n", " ")
    cleaned = re.sub(r"\s*\n\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()

def _detect_language(text: str) -> str:
    lang = _detector.detect_language_of(text)
    code = _LINGUA_TO_WHISPERX.get(lang)
    if not code:
        raise RuntimeError(f"Unsupported language detected: {lang}")
    return code

def align_lyrics(audio_path: str | Path, text_path: str | Path) -> Path:
    try:
        audio_file = Path(audio_path)
        lyrics_file = Path(text_path)

        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")
        if not lyrics_file.exists():
            raise FileNotFoundError(f"Lyrics file not found: {lyrics_file}")

        output_path = audio_file.parent / "alignment.json"
        if output_path.exists():
            print("alignment.json already exists, skipping.")
            return output_path

        lyrics = _clean_lyrics(lyrics_file.read_text(encoding="utf-8"))
        if not lyrics:
            raise ValueError("Lyrics file is empty after cleaning, aborting.")

        _ensure_ffmpeg_on_path()
        audio = whisperx.load_audio(str(audio_file))
        total_duration = audio.shape[0] / 16000
        if total_duration >= 1500:
            print("file too large, aborting text alignment")
            return

        def _run_alignment(device: str, batch_size: int) -> Dict:
            language_code = _detect_language(lyrics)
            print(f"Detected language: {language_code}")

            full_segment = [{
                "text": lyrics,
                "start": 0.0,
                "end": total_duration,
            }]
            align_model, align_metadata = whisperx.load_align_model(
                language_code=language_code,
                device=device,
            )
            return whisperx.align(
                full_segment,
                align_model,
                align_metadata,
                audio,
                device,
                return_char_alignments=False,
            )

        device = _detect_device()
        aligned: Dict
        if device == "cuda":
            try:
                aligned = _run_alignment(device="cuda", batch_size=4) #lower batch size => lower load on cpu
            except torch.OutOfMemoryError:
                print("CUDA out of memory during alignment. Retrying on CPU.")
                _free_cuda_cache()
                gc.collect()
                aligned = _run_alignment(device="cpu", batch_size=4)
        else:
            aligned = _run_alignment(device="cpu", batch_size=4)

        words: List[Dict] = []
        for word_data in aligned.get("word_segments", []):
            word = word_data.get("word")
            start = word_data.get("start")
            end = word_data.get("end")
            if not word or start is None or end is None:
                continue
            words.append({"word": word, "start": float(start), "end": float(end)})

        output_path.write_text(
            json.dumps(words, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Saved {len(words)} word alignments to: {output_path}")
        return output_path
    finally:
        gc.collect()
        _free_cuda_cache()