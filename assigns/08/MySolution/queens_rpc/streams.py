"""Process-local table of open event streams, keyed by unguessable IDs.

Lifecycle (see DESIGN.md, "Stream lifetime"):

* ``add`` stores a freshly opened, unforced stream under a UUID4 string.
* ``take`` forces up to ``limit`` events while holding that stream's lock,
  so concurrent ``queens.next`` calls on one ID are serialized and each
  request's update is atomic. Different streams proceed independently.
* When a stream yields ``done``, its solver state (the lazy cursor) is
  released at once. The ID stays as a lightweight tombstone, so repeated
  ``next`` calls keep answering ``[]`` / ``done: true`` until ``close`` or
  expiry.
* An entry not used for ``ttl_seconds`` expires. Expired entries are swept
  on every table operation, so no background thread is needed.
* At most ``max_streams`` entries exist at once. Expired entries are swept
  before that limit is enforced.

The clock and ID factory are injectable so expiry can be tested without
sleeping.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from .solver import Event, EventStream

DEFAULT_TTL_SECONDS = 300.0
DEFAULT_MAX_STREAMS = 64


class StreamNotFound(LookupError):
    """Unknown, closed, or expired stream ID."""


class TableFull(RuntimeError):
    """Too many open streams."""


@dataclass
class _Entry:
    stream: EventStream
    last_used: float
    lock: threading.Lock = field(default_factory=threading.Lock)


class StreamTable:
    def __init__(self, ttl_seconds: float = DEFAULT_TTL_SECONDS,
                 max_streams: int = DEFAULT_MAX_STREAMS,
                 clock: Callable[[], float] = time.monotonic,
                 id_factory: Callable[[], str] = lambda: str(uuid.uuid4())):
        self.ttl_seconds = ttl_seconds
        self.max_streams = max_streams
        self._clock = clock
        self._new_id = id_factory
        self._entries: dict[str, _Entry] = {}
        self._lock = threading.Lock()   # guards _entries only, never held while forcing

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def __contains__(self, stream_id: object) -> bool:
        with self._lock:
            return stream_id in self._entries

    def _sweep_locked(self, now: float) -> list[str]:
        expired = [sid for sid, e in self._entries.items() if now - e.last_used >= self.ttl_seconds]
        for sid in expired:
            del self._entries[sid]
        return expired

    def purge_expired(self) -> list[str]:
        with self._lock:
            return self._sweep_locked(self._clock())

    def add(self, stream: EventStream) -> str:
        with self._lock:
            now = self._clock()
            self._sweep_locked(now)
            if len(self._entries) >= self.max_streams:
                raise TableFull()
            stream_id = self._new_id()
            while stream_id in self._entries:  # vanishingly unlikely with UUID4
                stream_id = self._new_id()
            self._entries[stream_id] = _Entry(stream, now)
            return stream_id

    def _lookup(self, stream_id: str) -> _Entry:
        with self._lock:
            self._sweep_locked(self._clock())
            entry = self._entries.get(stream_id)
            if entry is None:
                raise StreamNotFound(stream_id)
            return entry

    def take(self, stream_id: str, limit: int) -> tuple[list[Event], bool]:
        entry = self._lookup(stream_id)
        with entry.lock:
            with self._lock:
                # Closed or swept while we waited for the stream lock.
                if self._entries.get(stream_id) is not entry:
                    raise StreamNotFound(stream_id)
            events, exhausted = entry.stream.take(limit)
            entry.last_used = self._clock()
            return events, exhausted

    def close(self, stream_id: str) -> None:
        with self._lock:
            self._sweep_locked(self._clock())
            if self._entries.pop(stream_id, None) is None:
                raise StreamNotFound(stream_id)
