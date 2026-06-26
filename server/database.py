from __future__ import annotations
import json
from datetime import date, datetime
from typing import Any
import asyncpg

_pool: asyncpg.Pool | None = None

async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )

async def get_pool(dsn: str) -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn, min_size=1, max_size=5, init=_init_connection
        )
    return _pool


def _row(r: asyncpg.Record | None) -> dict | None:
    return dict(r) if r else None


def _parse_release_date(value: str | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


# ── artists ──────────────────────────────────────────────────────────────────

async def upsert_artist(
    pool: asyncpg.Pool,
    name: str,
    *,
    country: str | None = None,
    avatar_url: str | None = None,
    external_links: dict | None = None,
) -> int:
    """Insert or update an artist row; returns its id."""
    from processor.data_cacher import slugify
    slug = slugify(name)
    row = await pool.fetchrow(
        """
        INSERT INTO artists (id, name, slug, country, avatar_url, external_links)
        VALUES (nextval('artists_id_seq'), $1, $2, $3, $4, $5)
        ON CONFLICT (slug) DO UPDATE
            SET country        = COALESCE(EXCLUDED.country,        artists.country),
                avatar_url  = COALESCE(EXCLUDED.avatar_url,  artists.avatar_url),
                external_links = COALESCE(EXCLUDED.external_links, artists.external_links)
        RETURNING id
        """,
        name, slug, country, avatar_url,
        json.dumps(external_links) if external_links else None,
    )
    return row["id"]


async def get_artist_by_slug(pool: asyncpg.Pool, slug: str) -> dict | None:
    return _row(await pool.fetchrow(
        "SELECT * FROM artists WHERE slug = $1", slug
    ))


# ── albums ───────────────────────────────────────────────────────────────────

async def upsert_album(
    pool: asyncpg.Pool,
    title: str,
    artist_id: int,
    *,
    cover_url: str | None = None,
    release_date: str | date | None = None,
    album_type: str = "album",
) -> int:
    """Upsert album + album_artists link in a single transaction."""
    release_date = _parse_release_date(release_date)
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO albums (id, title, cover_url, release_date, album_type)
                VALUES (nextval('albums_id_seq'), $1, $2, $3, $4)
                ON CONFLICT (title)  -- add UNIQUE(title) or adjust key as needed
                DO UPDATE SET
                    cover_url    = COALESCE(EXCLUDED.cover_url,    albums.cover_url),
                    release_date = COALESCE(EXCLUDED.release_date, albums.release_date)
                RETURNING id
                """,
                title, cover_url, release_date, album_type,
            )
            album_id = row["id"]
            await conn.execute(
                """
                INSERT INTO album_artists (album_id, artist_id, role)
                VALUES ($1, $2, 'primary')
                ON CONFLICT DO NOTHING
                """,
                album_id, artist_id,
            )
    return album_id


async def get_album(pool: asyncpg.Pool, album_id: int) -> dict | None:
    return _row(await pool.fetchrow(
        "SELECT * FROM albums WHERE id = $1", album_id
    ))


# ── tracks ───────────────────────────────────────────────────────────────────

async def upsert_track(pool: asyncpg.Pool, data: dict[str, Any]) -> int:
    row = await pool.fetchrow(
        """
        INSERT INTO tracks
            (id, title, album_id, slug, duration, bpm,
             track_number, is_explicit, licensed)
        VALUES
            (nextval('tracks_id_seq'),
             $1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (slug) DO UPDATE
            SET requests = tracks.requests + 1
        RETURNING id
        """,
        data["title"],
        data.get("album_id"),
        data["slug"],
        data.get("duration"),
        data.get("bpm"),
        data.get("track_number"),
        data.get("is_explicit", False),
        data.get("licensed", False),
    )
    return row["id"]


async def get_track(pool: asyncpg.Pool, slug: str) -> dict | None:
    return _row(await pool.fetchrow(
        "SELECT * FROM tracks WHERE slug = $1", slug
    ))


# ── sync_versions ─────────────────────────────────────────────────────────────

async def insert_sync(
    pool: asyncpg.Pool,
    track_id: int,
    json_data: dict,
    created_by: int | None = None,
) -> int:
    row = await pool.fetchrow(
        """
        INSERT INTO sync_versions (id, track_id, created_by, json_data)
        VALUES (
            (SELECT COALESCE(MAX(id), 0) + 1 FROM sync_versions),
            $1, $2, $3
        )
        RETURNING id
        """,
        track_id, created_by, json_data,
    )
    return row["id"]


async def get_sync(pool: asyncpg.Pool, track_id: int) -> dict | None:
    row = await pool.fetchrow(
        """
        SELECT * FROM sync_versions
        WHERE track_id = $1
        ORDER BY is_approved DESC, likes DESC
        LIMIT 1
        """,
        track_id,
    )
    if not row:
        return None
    r = dict(row)
    if isinstance(r["json_data"], str):
        r["json_data"] = json.loads(r["json_data"])
    return r