import json
import redis
from datetime import datetime

from app.database import SessionLocal
from app.models import Event
from app.queue import get_redis


def save_event(payload: dict) -> None:
    db = SessionLocal()
    try:
        event = Event(
            event_name=payload["event_name"],
            user_id=payload["user_id"],
            properties=payload["properties"],
            timestamp=datetime.fromisoformat(payload["timestamp"]),
        )
        db.add(event)
        db.commit()
        print(f"Procesado: {payload['event_name']} de user {payload['user_id']}")
    finally:
        db.close()


def run() -> None:
    r = get_redis()
    print("Worker iniciado. Esperando eventos...")
    while True:
        try:
            result = r.brpop("events_queue", timeout=5)
        except redis.exceptions.TimeoutError:
            continue
        if result is None:
            continue
        _, raw = result
        payload = json.loads(raw)
        save_event(payload)


if __name__ == "__main__":
    run()