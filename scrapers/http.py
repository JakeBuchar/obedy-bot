"""Retry restaurant requests that failed for a reason that may pass.

Scraping runs from a GitHub runner, and some sites intermittently refuse to
answer that network at all: on 2026-09-09 two Kolín runs half an hour apart
were identical except that the second one could not open a connection to
La Musica or Arco, and both sites answered in under two seconds when asked
again. A dropped connection therefore costs a restaurant in the email and
turns the run red, for no reason on our side or theirs.

Retried are connection failures, timeouts, and the status codes a site
returns when it is overloaded or rate-limiting rather than when it disagrees
with the request. A 404 is left alone - asking again cannot change it.
"""
from __future__ import annotations

import time
from typing import Callable, TypeVar

import requests

ATTEMPTS = 3
BACKOFF_SECONDS = 3.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

T = TypeVar("T")


def with_retries(send: Callable[[], T], description: str, attempts: int = ATTEMPTS) -> T:
    for attempt in range(1, attempts + 1):
        last_attempt = attempt == attempts
        try:
            response = send()
        except (requests.ConnectionError, requests.Timeout) as exc:
            if last_attempt:
                raise
            _announce(description, type(exc).__name__, attempt, attempts)
        else:
            if last_attempt or getattr(response, "status_code", None) not in RETRY_STATUSES:
                return response
            _announce(description, f"HTTP {response.status_code}", attempt, attempts)
        time.sleep(BACKOFF_SECONDS * attempt)
    raise AssertionError("unreachable")


def _announce(description: str, reason: str, attempt: int, attempts: int) -> None:
    print(
        f"{description} did not answer ({reason}), attempt {attempt} of {attempts}; trying again.",
        flush=True,
    )
