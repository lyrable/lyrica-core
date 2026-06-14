import json
import shutil
from pathlib import Path

import pytest

from processor.quantizer import quantize_alignment

FIXTURES = Path(__file__).parent / "fixtures" / "sample"


@pytest.fixture
def pipeline_dir(tmp_path: Path) -> Path:
    work_dir = tmp_path / "song"
    work_dir.mkdir()
    for name in ("alignment.json", "rhythm.json", "theme.json"):
        shutil.copy(FIXTURES / name, work_dir / name)
    return work_dir


def test_quantize_alignment_builds_master_sync(pipeline_dir: Path):
    output = quantize_alignment(
        pipeline_dir / "alignment.json",
        pipeline_dir / "rhythm.json",
        pipeline_dir / "theme.json",
        orig_name="Test Track",
        orig_artist="Test Artist",
        lang="en",
        album_id="album-123",
    )

    assert output == pipeline_dir / "master_sync.json"
    assert output.is_file()

    master = json.loads(output.read_text(encoding="utf-8"))
    assert master["d"] == {"n": "Test Track", "a": "Test Artist"}
    assert master["bpm"] == 120.0
    assert master["album_id"] == "album-123"
    assert master["theme"]["primary"] == "#1A2B3C"
    assert "image_base64" not in master["theme"]
    assert len(master["words"]) == 3

    for entry in master["words"]:
        assert isinstance(entry[0], str)
        assert isinstance(entry[1], float)
        assert isinstance(entry[2], int)
        assert entry[2] >= 1


def test_quantize_alignment_rejects_invalid_bpm(pipeline_dir: Path):
    rhythm_path = pipeline_dir / "rhythm.json"
    rhythm = json.loads(rhythm_path.read_text(encoding="utf-8"))
    rhythm["bpm"] = 0
    rhythm_path.write_text(json.dumps(rhythm), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid BPM"):
        quantize_alignment(
            pipeline_dir / "alignment.json",
            rhythm_path,
            pipeline_dir / "theme.json",
            orig_name="Test Track",
            orig_artist="Test Artist",
            lang="en",
        )
