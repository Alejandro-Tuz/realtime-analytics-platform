import asyncio
import json
import os
import random
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

import worker
from app.schemas import EventCreate
from app.queue import get_redis
from app.metrics import get_summary
from app.simulator import random_event


async def generar_trafico():
    while True:
        evento = random_event()
        get_redis().lpush("events_queue", json.dumps(evento))
        await asyncio.sleep(random.uniform(0.5, 2.5))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("DEMO_MODE") == "true":
        threading.Thread(target=worker.run, daemon=True).start()
        asyncio.create_task(generar_trafico())
    yield


app = FastAPI(title="Analytics en tiempo real", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    return RedirectResponse("/static/index.html")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/events", status_code=202)
def ingest_event(event: EventCreate):
    payload = event.model_dump(mode="json")
    get_redis().lpush("events_queue", json.dumps(payload))
    return {"status": "queued"}


@app.get("/metrics/summary")
def metrics_summary() -> dict:
    return get_summary()


@app.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await asyncio.to_thread(get_summary)
        await websocket.send_json(data)
        await asyncio.sleep(3)