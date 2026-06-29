from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from config import WORKER_SECRET
import asyncio
import logging
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
pipeline_queue: asyncio.Queue = asyncio.Queue()


class ProcessRequest(BaseModel):
    artist: str
    title: str


@app.on_event("startup")
async def start_worker():
    asyncio.create_task(pipeline_worker())


async def pipeline_worker():
    from processor.data_cacher import get_song_data
    while True:
        artist, title = await pipeline_queue.get()
        logger.info("[PIPELINE] Processing: %s – %s", title, artist)
        try:
            await get_song_data(artist, title)
            logger.info("[PIPELINE] Done: %s – %s", title, artist)
        except Exception:
            logger.exception("[PIPELINE ERROR] %s – %s", title, artist)
        finally:
            pipeline_queue.task_done()


@app.post("/process")
async def process(body: ProcessRequest, x_worker_secret: str = Header()):
    if x_worker_secret != WORKER_SECRET:
        raise HTTPException(status_code=403)
    await pipeline_queue.put((body.artist, body.title))
    logger.info("[PIPELINE] Queued: %s – %s", body.title, body.artist)
    return {"status": "queued"}


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8001)