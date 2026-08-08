"""
Kafka trace producer — emits agent decision events to Kafka for observability.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class KafkaTraceProducer:
    """
    Publishes agent decision-trace events to Kafka.

    Each event represents a node transition in the LangGraph state machine,
    creating a queryable audit trail of every agent decision.
    """

    def __init__(self):
        self._producer = None
        self._enabled = True

    def _get_producer(self):
        """Lazy-initialize the Kafka producer."""
        if self._producer is None:
            try:
                from confluent_kafka import Producer

                self._producer = Producer(
                    {
                        "bootstrap.servers": settings.kafka_bootstrap_servers,
                        "client.id": "repopilot-agent-core",
                        "acks": "all",
                    }
                )
                logger.info(
                    f"Kafka producer connected: {settings.kafka_bootstrap_servers}"
                )
            except Exception as e:
                logger.warning(
                    f"Kafka producer init failed (traces will be skipped): {e}"
                )
                self._enabled = False
        return self._producer

    def _delivery_callback(self, err, msg):
        """Kafka delivery callback for async produces."""
        if err:
            logger.error(f"Kafka delivery failed: {err}")
        else:
            logger.debug(
                f"Kafka event delivered: topic={msg.topic()}, "
                f"partition={msg.partition()}, offset={msg.offset()}"
            )

    def emit_event(
        self,
        session_id: str,
        node_name: str,
        event_type: str,
        payload: Optional[dict[str, Any]] = None,
    ):
        """
        Emit a trace event to Kafka.

        Args:
            session_id: Unique ID for this agent run.
            node_name: The LangGraph node that produced this event.
            event_type: The type of event (e.g., retrieve.started, grade.scored).
            payload: Additional data for the event.
        """
        if not self._enabled:
            return

        event = {
            "session_id": session_id,
            "node": node_name,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload or {},
        }

        try:
            producer = self._get_producer()
            if producer:
                producer.produce(
                    topic=settings.kafka_trace_topic,
                    key=session_id.encode("utf-8"),
                    value=json.dumps(event, default=str).encode("utf-8"),
                    callback=self._delivery_callback,
                )
                producer.poll(0)  # Trigger delivery callbacks
        except Exception as e:
            logger.warning(f"Failed to emit Kafka event: {e}")

    def flush(self, timeout: float = 5.0):
        """Flush any pending events."""
        if self._producer:
            self._producer.flush(timeout)


# Singleton producer instance
trace_producer = KafkaTraceProducer()
