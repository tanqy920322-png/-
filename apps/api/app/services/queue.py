import logging
import time

logger = logging.getLogger(__name__)

AI_QUEUE = "queue:ai"


class JobQueue:
    """Redis list queue. If Redis is down, callers still keep the job row in Postgres."""

    def __init__(self, url: str):
        self.url = url
        self._client = None

    def _connect(self):
        if not self.url:
            return None
        if self._client is not None:
            return self._client
        import redis

        client = redis.Redis.from_url(self.url, socket_connect_timeout=0.4, socket_timeout=2)
        client.ping()
        self._client = client
        return client

    def enqueue(self, job_id: str) -> bool:
        try:
            client = self._connect()
            if client is None:
                return False
            client.lpush(AI_QUEUE, job_id)
            return True
        except Exception as exc:
            logger.warning("Redis 入队失败，任务仍写在数据库中: %s", exc)
            self._client = None
            return False

    def blocking_pop(self, timeout: int = 5) -> str | None:
        try:
            client = self._connect()
        except Exception as exc:
            logger.warning("Redis 不可用: %s", exc)
            self._client = None
            client = None
        if client is None:
            time.sleep(min(timeout, 2))
            return None
        try:
            item = client.brpop(AI_QUEUE, timeout=timeout)
        except Exception as exc:
            logger.warning("Redis 出队失败: %s", exc)
            self._client = None
            return None
        if not item:
            return None
        payload = item[1]
        if isinstance(payload, bytes):
            return payload.decode()
        return str(payload)


def probe_redis(url: str) -> str:
    if not url:
        return "disabled"
    try:
        import redis

        client = redis.Redis.from_url(url, socket_connect_timeout=0.3, socket_timeout=0.3)
        client.ping()
        return "ok"
    except Exception:
        return "down"


_queue: JobQueue | None = None


def get_queue() -> JobQueue:
    global _queue
    if _queue is None:
        from app.config import get_settings

        _queue = JobQueue(get_settings().redis_url)
    return _queue
