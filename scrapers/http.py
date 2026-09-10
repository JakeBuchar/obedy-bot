"""Retry restaurant requests that failed for a reason that may pass.

Scraping runs from a GitHub runner, and restaurant sites regularly go quiet
on that network for a stretch: on 2026-09-09 two Kolín runs half an hour
apart were identical except that the second could not connect to La Musica
or Arco, and on 2026-09-10 La Ventola refused three attempts spread over
50 seconds and was reachable again later. A short outage like that costs a
restaurant in the email and turns the run red for no reason on our side, so
each request keeps trying for a couple of minutes - the send runs once a day
and the job may take fifteen minutes, so waiting is nearly free.

Retried are connection failures, timeouts, and the status codes a site
returns when it is overloaded or rate-limiting rather than when it disagrees
with the request. A 404 is left alone - asking again cannot change it.
"""
from __future__ import annotations

import socket
import time
from typing import Callable, TypeVar
from urllib.parse import urlsplit

import requests
import urllib3.util.connection

ATTEMPTS = 5
BACKOFF_SECONDS = 4.0
MAX_BACKOFF_SECONDS = 30.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

T = TypeVar("T")


class SiteUnreachable(RuntimeError):
    """A site refused every attempt, so there is no menu to parse."""


def prefer_ipv4() -> None:
    """Ask only for IPv4 addresses while resolving a hostname.

    Several restaurants publish an AAAA record, and a runner without an IPv6
    route fails that address instantly with "network is unreachable". urllib3
    then reports that as the error even when the IPv4 attempt before it was
    the one that really timed out, which is how a plain connect timeout ended
    up looking like an IPv6 problem in the 2026-09-10 log.
    """
    urllib3.util.connection.allowed_gai_family = lambda: socket.AF_INET


prefer_ipv4()


def with_retries(send: Callable[[], T], description: str, attempts: int = ATTEMPTS) -> T:
    for attempt in range(1, attempts + 1):
        last_attempt = attempt == attempts
        try:
            response = send()
        except (requests.ConnectionError, requests.Timeout) as exc:
            if last_attempt:
                # The urllib3 original runs to several lines and ends up in
                # the email verbatim, so say it in one.
                raise SiteUnreachable(
                    f"{_host(description)} did not answer in {attempts} attempts "
                    f"({type(exc).__name__})"
                ) from exc
            _announce(description, type(exc).__name__, attempt, attempts)
        else:
            if last_attempt or getattr(response, "status_code", None) not in RETRY_STATUSES:
                return response
            _announce(description, f"HTTP {response.status_code}", attempt, attempts)
        time.sleep(min(BACKOFF_SECONDS * 2 ** (attempt - 1), MAX_BACKOFF_SECONDS))
    raise AssertionError("unreachable")


def _announce(description: str, reason: str, attempt: int, attempts: int) -> None:
    print(
        f"{description} did not answer ({reason}), attempt {attempt} of {attempts}; trying again.",
        flush=True,
    )


def _host(description: str) -> str:
    return urlsplit(description).netloc or description
