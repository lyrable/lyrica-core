# Lyrica Worker

Асинхронный микросервис для обработки музыкальных треков. Скачивает треки с YouTube, разделяет вокал от инструментала, выполняет выравнивание текста и создаёт синхронизированный JSON для фронтенда.

## Pipeline

<img width="1280" height="1063" alt="5336825447918018549" src="https://github.com/user-attachments/assets/75250c00-02fa-4bda-a320-b349aaa5d451" />


1. **Download (yt-dlp)** — скачивает MP3 по названию артиста и трека
2. **Separate (Demucs)** — разделяет вокал и инструментал
3. **Transcribe (Whisper)** — выравнивает текст с вокалом, выдаёт тайминги слов
4. **Quantize** — привязывает слова к битам трека (snap to grid)
5. **Syllabify (pyphen)** — разбивает слова на слоги, вычисляет смещения
6. **Save** — пишет готовый JSON в PostgreSQL

Server отправляет задачи в очередь, Worker обрабатывает асинхронно и шлёт статусы обратно в бд

## Требования

```
Python 3.10+
ffmpeg
CUDA (опционально, для GPU-ускорения Demucs, WhisperX)
```

## Установка

```bash
git clone https://github.com/username/lyrica-worker
cd lyrica-worker

pip install -r requirements.txt

# Загрузить модели
python -m demucs.separate --repo=facebook/demucs.official -n mdx_extra dummy.mp3
python -m whisper --model base --language ru dummy.mp3
```

## Запуск

```bash
python worker.py
```

Сервис слушает очередь и обрабатывает треки асинхронно.

## API с Server

### Запуск обработки

Server отправляет сообщение в очередь:

Worker обрабатывает трек и отсылает его обратно.

## Pipeline обработки

### 1. Download (yt-dlp)

```python
async def download_track(artist: str, title: str, temp_dir: Path) -> Path:
    """Скачивает трек с YouTube по названию артиста и песни"""
    query = f"{artist} {title}"
    # yt-dlp → MP3 → temp_dir
    return mp3_path
```

**Время:** 5-15 сек (зависит от интернета)

### 2. Separate (Demucs)

```python
async def separate_vocals(mp3_path: Path, output_dir: Path) -> tuple[Path, Path]:
    """Разделяет трек на вокал и инструментал"""
    # Demucs mdx_extra (Meta) → vocal.wav, instrumental.wav
    return vocal_path, instrumental_path
```

**Время:** 30-60 сек (GPU ускоряет в 3-5 раз)

### 3. Transcribe (Whisper)

```python
async def transcribe(vocal_path: Path, lang: str = "ru") -> list[dict]:
    """Выполняет выравнивание текста и вокала"""
    # Whisper с word_level_timestamps
    return [
        {"word": "Ванна", "start": 12.41, "end": 12.95},
        {"word": "красный", "start": 13.10, "end": 13.58},
        ...
    ]
```

**Время:** 30-90 сек (зависит от длины трека и модели)

**Вход:** текст из `lyrics.txt`, vocals.wav

### 4. Quantize

```python
async def quantize_alignment(
    alignment: list[dict],
    rhythm: dict,  # {"bpm": 160.0, "beats": [0.0, ...]}
    syllables: dict,  # {"word": ["syl", "la", "ble"], ...}
) -> list[list]:
    """Привязывает слова к битам, разбивает на слоги"""
    return [
        ["Ван|на", 69.3, 3, [0.0, 1.5]],
        ["красный", 70.3, 3],
        ...
    ]
```

**Время:** 0.1 сек

### 5. master_sync.json

```json
{
  "d": { "n": "название трека", "a": "артист" },
  "bpm": 161.5,
  "off": 0.0,
  "vibe": { "energy": 3.757, "brightness": 0.235, "roughness": 0.492 },
  "theme": { "color_pallete": { "primary": "#C2C2C2", "secondary": "#2A2A2A", "accent": "#5C5C5C" } },
  "words": [
    ["Ван|на,", 71.3, 3, [0.0, 1.5]],
    ["крас|ный", 72.3, 4, [0.0, 2.0]]
  ]
}
```

### 6. Save

```python
async def save_master_sync(
    master_data: dict,
    track_id: int,
    album_id: int,
) -> None:
    """Сохраняет JSON в PostgreSQL"""
    # INSERT INTO sync_versions
```

## Оптимизация

### GPU

На GPU Demucs работает в 3-5 раз быстрее. Если CUDA недоступна — падает на CPU (медленнее, но работает).

### Кэширование

Уже обработанные треки (по slug) пропускаются — берутся из БД напрямую.

## Разработка

### Отладка

```python
# В config.py
PIPELINE_DEBUG = True
```



https://github.com/username/lyrica-worker
