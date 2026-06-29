import asyncio
import json

from fastapi import FastAPI, WebSocket

from app.schemas import EventCreate
from app.queue import get_redis
from app.metrics import get_summary

app = FastAPI(title="Analytics en tiempo real")


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