from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Event
from app.schemas import EventCreate

app = FastAPI(title="Analytics en tiempo real")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/events")
def ingest_event(event: EventCreate, db: Session = Depends(get_db)):
    nuevo_evento = Event(
        event_name=event.event_name,
        user_id=event.user_id,
        properties=event.properties,
        timestamp=event.timestamp,
    )
    db.add(nuevo_evento)
    db.commit()
    db.refresh(nuevo_evento)
    return {"status": "saved", "id": nuevo_evento.id}