from sqlalchemy import func, text
from app.database import SessionLocal
from app.models import Event


def get_summary() -> dict:
    db = SessionLocal()
    try:
        total = db.query(func.count(Event.id)).scalar()
        unique_users = db.query(func.count(func.distinct(Event.user_id))).scalar()
        by_type = (
            db.query(Event.event_name, func.count(Event.id))
            .group_by(Event.event_name)
            .order_by(func.count(Event.id).desc())
            .all()
        )
        return {
            "total_events": total,
            "unique_users": unique_users,
            "events_by_type": {name: count for name, count in by_type},
        }
    finally:
        db.close()