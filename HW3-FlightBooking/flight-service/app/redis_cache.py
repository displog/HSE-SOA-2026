import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

TTL_FLIGHT = 300  # 5 min
TTL_SEARCH = 300  # 5 min


def _get_redis_client():
    use_sentinel = os.environ.get("REDIS_USE_SENTINEL", "true").lower() == "true"
    if use_sentinel:
        sentinel_hosts = os.environ.get("REDIS_SENTINEL_HOSTS", "localhost:26379")
        service_name = os.environ.get("REDIS_SENTINEL_SERVICE_NAME", "mymaster")
        hosts = [(h.strip().split(":")[0], int(h.strip().split(":")[1])) for h in sentinel_hosts.split(",") if ":" in h]
        from redis.sentinel import Sentinel
        sentinel = Sentinel(hosts, socket_timeout=5)
        return sentinel.master_for(service_name, socket_timeout=5)
    else:
        url = os.environ.get("REDIS_STANDALONE_URL", "redis://localhost:6379")
        import redis
        return redis.from_url(url)


_client = None


def get_redis():
    global _client
    if _client is None:
        _client = _get_redis_client()
    return _client


def flight_key(flight_id: str) -> str:
    return f"flight:{flight_id}"


def search_key(origin: str, destination: str, date: str) -> str:
    return f"search:{origin}:{destination}:{date}"


def get_cached_flight(flight_id: str) -> Optional[dict]:
    r = get_redis()
    key = flight_key(flight_id)
    data = r.get(key)
    if data:
        logger.info("cache hit for %s", key)
        return json.loads(data)
    logger.info("cache miss for %s", key)
    return None


def set_cached_flight(flight_id: str, data: dict, ttl: int = TTL_FLIGHT) -> None:
    r = get_redis()
    key = flight_key(flight_id)
    r.setex(key, ttl, json.dumps(data))
    logger.debug("cached %s", key)


def invalidate_flight(flight_id: str) -> None:
    r = get_redis()
    key = flight_key(flight_id)
    r.delete(key)
    logger.debug("invalidated %s", key)


def get_cached_search(origin: str, destination: str, date: str) -> Optional[list]:
    r = get_redis()
    key = search_key(origin, destination, date)
    data = r.get(key)
    if data:
        logger.info("cache hit for %s", key)
        return json.loads(data)
    logger.info("cache miss for %s", key)
    return None


def set_cached_search(origin: str, destination: str, date: str, flights: list, ttl: int = TTL_SEARCH) -> None:
    r = get_redis()
    key = search_key(origin, destination, date)
    r.setex(key, ttl, json.dumps(flights))
    logger.debug("cached %s", key)


def invalidate_search(origin: str, destination: str, date: str) -> None:
    r = get_redis()
    key = search_key(origin, destination, date)
    r.delete(key)
    logger.debug("invalidated %s", key)


def invalidate_flight_and_search(flight_id: str, origin: str, destination: str, date: str) -> None:
    invalidate_flight(flight_id)
    invalidate_search(origin, destination, date)
