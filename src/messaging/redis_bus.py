"""Redis-backed message bus for cross-process publish/subscribe."""

import logging
import threading
from typing import Callable

from src.messaging.base import MessageBusBase, Subscriber
from src.messaging.events import Event, EventType

logger = logging.getLogger(__name__)


class RedisMessageBus(MessageBusBase):
    """Message bus backed by Redis pub/sub for cross-process communication.

    **Local-dispatch-first**: ``publish()`` calls in-process subscribers
    synchronously *before* publishing to Redis.  This preserves the
    synchronous semantics that ``ContextPackBuilder`` and
    ``MarketDataOrchestrator`` depend on.

    A background listener thread receives messages from Redis and dispatches
    them to local subscribers (skipping duplicates from self-published events).
    """

    def __init__(self) -> None:
        from config.settings import get_settings

        settings = get_settings()
        self._channel_prefix = settings.redis.channel_prefix
        self._source_id = f"python-{threading.get_ident()}"

        # Local subscriber registry (same as InMemoryMessageBus)
        self._subscribers: dict[EventType, list[Subscriber]] = {}
        self._lock = threading.Lock()

        # Redis connections
        self._pool = self._create_pool(settings)
        self._pub_conn = self._get_connection()

        # Background listener
        self._listener_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()
        self._subscribed_channels: set[str] = set()

        # Track correlation_ids we published to avoid re-dispatching our own messages
        self._self_published: set[str] = set()
        self._self_published_lock = threading.Lock()
        self._max_self_published = 10_000

        self._start_listener()

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def subscribe(self, event_type: EventType, callback: Subscriber) -> None:
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(callback)
        logger.info("Subscribed %s to %s", callback, event_type.value)

    def unsubscribe(self, event_type: EventType, callback: Subscriber) -> None:
        with self._lock:
            callbacks = self._subscribers.get(event_type, [])
            try:
                callbacks.remove(callback)
                logger.debug("Unsubscribed %s from %s", callback, event_type.value)
            except ValueError:
                pass

    def publish(self, event: Event) -> None:
        """Dispatch to local subscribers first, then publish to Redis."""
        # 1) Local dispatch (synchronous)
        self._dispatch_local(event)

        # 2) Redis publish (cross-process)
        try:
            from src.messaging.serialization import event_to_json

            channel = self._channel_for(event.event_type)
            message = event_to_json(event)

            # Track so listener thread skips re-dispatch
            with self._self_published_lock:
                self._self_published.add(event.correlation_id)
                if len(self._self_published) > self._max_self_published:
                    # Evict oldest half
                    to_keep = list(self._self_published)[self._max_self_published // 2:]
                    self._self_published = set(to_keep)

            self._pub_conn.publish(channel, message)
            logger.debug(
                "Published %s to Redis channel %s (correlation_id=%s)",
                event.event_type.value,
                channel,
                event.correlation_id,
            )
        except Exception:
            logger.warning(
                "Failed to publish %s to Redis (correlation_id=%s). "
                "Local subscribers were still notified.",
                event.event_type.value,
                event.correlation_id,
                exc_info=True,
            )

    def publish_and_wait(
        self,
        request: Event,
        response_type: EventType,
        *,
        timeout: float = 30.0,
    ) -> Event | None:
        """Publish *request* and block until a matching response arrives.

        Uses a temporary subscriber with correlation_id matching.
        Works for both in-process and cross-process responses.
        """
        result: list[Event] = []
        done = threading.Event()

        def _waiter(event: Event) -> None:
            if event.correlation_id == request.correlation_id:
                result.append(event)
                done.set()

        self.subscribe(response_type, _waiter)
        try:
            self.publish(request)
            done.wait(timeout=timeout)
        finally:
            self.unsubscribe(response_type, _waiter)

        if result:
            return result[0]

        logger.warning(
            "publish_and_wait timed out after %.1fs for %s (correlation_id=%s)",
            timeout,
            response_type.value,
            request.correlation_id,
        )
        return None

    def health_check(self) -> bool:
        """Check if Redis is reachable."""
        try:
            return self._pub_conn.ping()
        except Exception:
            return False

    def shutdown(self) -> None:
        """Stop the listener thread and close Redis connections."""
        logger.info("Shutting down RedisMessageBus")
        self._shutdown_event.set()
        if self._listener_thread and self._listener_thread.is_alive():
            self._listener_thread.join(timeout=5.0)
        try:
            self._pool.disconnect()
        except Exception:
            pass

    # -------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------

    def _create_pool(self, settings):
        """Create a Redis connection pool from settings."""
        import redis

        return redis.ConnectionPool(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
            password=settings.redis.password or None,
            max_connections=settings.redis.pool_size,
            socket_timeout=settings.redis.socket_timeout,
            retry_on_timeout=settings.redis.retry_on_timeout,
            decode_responses=True,
        )

    def _get_connection(self):
        """Get a Redis client from the pool."""
        import redis
        return redis.Redis(connection_pool=self._pool)

    def _channel_for(self, event_type: EventType) -> str:
        """Map an EventType to a Redis channel name."""
        return f"{self._channel_prefix}:{event_type.value}"

    def _dispatch_local(self, event: Event) -> None:
        """Call in-process subscribers synchronously."""
        import asyncio

        with self._lock:
            callbacks = list(self._subscribers.get(event.event_type, []))

        if not callbacks:
            logger.debug(
                "No local subscribers for %s (correlation_id=%s)",
                event.event_type.value,
                event.correlation_id,
            )
            return

        logger.info(
            "Local dispatch %s to %d subscriber(s) (correlation_id=%s, source=%s)",
            event.event_type.value,
            len(callbacks),
            event.correlation_id,
            event.source,
        )

        for callback in callbacks:
            try:
                result = callback(event)
                if asyncio.iscoroutine(result):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)
                    except RuntimeError:
                        asyncio.run(result)
            except Exception:
                logger.exception(
                    "Subscriber %s failed for %s (correlation_id=%s)",
                    callback,
                    event.event_type.value,
                    event.correlation_id,
                )

    def _start_listener(self) -> None:
        """Start the background Redis subscription listener thread."""
        self._listener_thread = threading.Thread(
            target=self._listen_loop,
            name="RedisMessageBus-listener",
            daemon=True,
        )
        self._listener_thread.start()
        logger.info("RedisMessageBus listener thread started")

    def _listen_loop(self) -> None:
        """Background loop: subscribe to all event channels and dispatch."""
        import redis as redis_lib

        reconnect_attempts = 0
        try:
            conn = self._get_connection()
            pubsub = conn.pubsub()

            # Subscribe to all EventType channels
            channels = {self._channel_for(et): et for et in EventType}
            pubsub.subscribe(*channels.keys())
            logger.info("Redis listener subscribed to channels: %s", list(channels.keys()))

            while not self._shutdown_event.is_set():
                try:
                    message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                    if message is None:
                        continue

                    if message["type"] != "message":
                        continue

                    self._handle_redis_message(message)

                except redis_lib.ConnectionError:
                    if self._shutdown_event.is_set():
                        break
                    backoff = min(1.0 * (2 ** reconnect_attempts), 30.0)
                    reconnect_attempts += 1
                    logger.warning(
                        "Redis connection lost, reconnecting in %.1fs (attempt %d)...",
                        backoff,
                        reconnect_attempts,
                    )
                    self._shutdown_event.wait(backoff)
                    try:
                        pubsub = conn.pubsub()
                        pubsub.subscribe(*channels.keys())
                        reconnect_attempts = 0  # Reset on successful reconnect
                        logger.info("Redis reconnected successfully")
                    except Exception:
                        logger.warning("Redis reconnect failed", exc_info=True)

        except Exception:
            if not self._shutdown_event.is_set():
                logger.exception("Redis listener thread crashed")

    def _handle_redis_message(self, message: dict) -> None:
        """Deserialize and dispatch a message received from Redis."""
        from src.messaging.serialization import event_from_json

        try:
            raw = message["data"]
            event = event_from_json(raw)

            # Skip self-published messages (already dispatched locally)
            with self._self_published_lock:
                if event.correlation_id in self._self_published:
                    self._self_published.discard(event.correlation_id)
                    return

            # Dispatch to local subscribers
            logger.debug(
                "Received %s from Redis (correlation_id=%s, source=%s)",
                event.event_type.value,
                event.correlation_id,
                event.source,
            )
            self._dispatch_local(event)

        except Exception:
            logger.exception("Failed to handle Redis message: %s", message)
