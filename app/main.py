import json

from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Event
from app.schemas import EventCreate
from app.queue import get_redis

app = FastAPI(title="Analytics en tiempo real")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/events", status_code=202)
def ingest_event(event: EventCreate):
    payload = event.model_dump(mode="json")
    get_redis().lpush("events_queue", json.dumps(payload))
    return {"status": "queued"}