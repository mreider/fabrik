"""
Chaos engineering patterns for fabrik Python services.
Replicates the chaos injection from the Java OrderController.java
"""
import os
import random
import time
import logging

logger = logging.getLogger(__name__)


def apply_slowdown(context: str = "request") -> bool:
    """
    Apply service slowdown based on SLOWDOWN_RATE and SLOWDOWN_DELAY env vars.
    Returns True if slowdown was applied.
    """
    rate_str = os.environ.get("SLOWDOWN_RATE")
    delay_str = os.environ.get("SLOWDOWN_DELAY")

    if rate_str and delay_str:
        try:
            rate = int(rate_str)
            delay_ms = int(delay_str)
            if random.random() * 100 < rate:
                logger.info(f"Service slowdown for {context} ({delay_ms}ms)")
                time.sleep(delay_ms / 1000.0)
                return True
        except ValueError:
            pass  # Ignore invalid config
    return False


def apply_db_slowdown(db_connection, context: str = "request") -> bool:
    """
    Apply database slowdown using heavy PostgreSQL query.
    Based on SLOWDOWN_RATE and DB_SLOWDOWN_DELAY env vars.

    The query uses generate_series() + md5() to consume CPU/time.
    Each iteration takes ~0.2ms, so iterations = delay_ms * 5000.
    """
    rate_str = os.environ.get("DB_SLOWDOWN_RATE")
    delay_str = os.environ.get("DB_SLOWDOWN_DELAY")

    if rate_str and delay_str and db_connection:
        try:
            rate = int(rate_str)
            delay_ms = int(delay_str)
            if random.random() * 100 < rate:
                iterations = delay_ms * 5000  # ~0.2ms per iteration
                logger.info(f"Executing heavy DB query for {context} ({iterations} iterations, ~{delay_ms}ms expected)")

                cursor = db_connection.cursor()
                cursor.execute(
                    f"SELECT count(*) FROM generate_series(1, {iterations}) s, "
                    f"LATERAL (SELECT md5(CAST(random() AS text))) x"
                )
                cursor.fetchone()
                cursor.close()
                logger.debug(f"DB query completed for {context}")
                return True
        except Exception as e:
            logger.error(f"Database operation failed for {context}: {e}")
            raise RuntimeError(f"Database query timeout - {context} could not be processed") from e
    return False


def apply_msg_slowdown(context: str = "message") -> bool:
    """
    Apply message processing slowdown based on MSG_SLOWDOWN_RATE and MSG_SLOWDOWN_DELAY env vars.
    Used during Kafka message consumption.
    Returns True if slowdown was applied.
    """
    rate_str = os.environ.get("MSG_SLOWDOWN_RATE")
    delay_str = os.environ.get("MSG_SLOWDOWN_DELAY")

    if rate_str and delay_str:
        try:
            rate = int(rate_str)
            delay_ms = int(delay_str)
            if random.random() * 100 < rate:
                logger.info(f"Message processing slowdown for {context} ({delay_ms}ms)")
                time.sleep(delay_ms / 1000.0)
                return True
        except ValueError:
            pass  # Ignore invalid config
    return False


def simulate_latency(min_ms: int, max_ms: int):
    """Simulate variable latency for realistic service behavior."""
    delay = min_ms + random.random() * (max_ms - min_ms)
    time.sleep(delay / 1000.0)
