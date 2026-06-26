import redis

from app.config import settings


def get_redis() -> redis.Redis:
    return redis.Redis(host=settings.redis_host, port=settings.redis_port, db=0)