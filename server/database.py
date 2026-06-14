from __future__ import annotations
import json
from typing import Any
import asyncpg

_pool: asyncpg.Pool | None = None


async def get_pool(dsn: str) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    return _pool


def _row(r: asyncpg.Record | None) -> dict | None:
    return dict(r) if r else None


# albums

async def upsert_album(pool: asyncpg.Pool, title: str, artist: str,
                       cover_base64: str | None = None,
                       release_date: str | None = None) -> int:
    row = await pool.fetchrow(
        "INSERT INTO albums (title,artist,cover_base64,release_date) "
        "VALUES ($1,$2,$3,$4) "
        "ON CONFLICT (title,artist) DO UPDATE SET title=EXCLUDED.title "
        "RETURNING id",
        title, artist, cover_base64, release_date,
    )
    return row["id"]


async def get_album(pool: asyncpg.Pool, album_id: int) -> dict | None:
    return _row(await pool.fetchrow("SELECT * FROM albums WHERE id=$1", album_id))


# tracks 

async def upsert_track(pool: asyncpg.Pool, data: dict[str, Any]) -> int:
    row = await pool.fetchrow(
        "INSERT INTO tracks (title,artist,slug,duration,bpm,licenced,album_id) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7) "
        "ON CONFLICT (slug) DO UPDATE SET requests=tracks.requests+1 "
        "RETURNING id",
        data["title"], data["artist"], data["slug"],
        data.get("duration"), data.get("bpm"),
        data.get("licenced", False), data.get("album_id"),
    )
    return row["id"]


async def get_track(pool: asyncpg.Pool, slug: str) -> dict | None:
    return _row(await pool.fetchrow("SELECT * FROM tracks WHERE slug=$1", slug))


# sync_versions

async def insert_sync(pool: asyncpg.Pool, track_id: int,
                      json_data: dict, created_by: int | None = None) -> int:
    row = await pool.fetchrow(
        "INSERT INTO sync_versions (track_id,created_by,json_data) "
        "VALUES ($1,$2,$3) RETURNING id",
        track_id, created_by, json.dumps(json_data, ensure_ascii=False),
    )
    return row["id"]


