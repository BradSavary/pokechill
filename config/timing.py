"""
Server-Timing header: how long the server spent on a page, and in the database.

The browser shows it in its developer tools (Network tab, a request, then
"Timing"): e.g. "db 12 ms, 9 queries" and "app 48 ms". It tells at a glance
whether a slow page waits for the database, for Python, or for the network
(the rest of the time the browser waited).

Nothing secret is sent: durations and a number of queries, never their text.
"""

import time

from django.db import connection


class QueryTimer:
    """
    Counts the queries of a request and adds up their durations.

    Django calls it around every query through connection.execute_wrapper:
    it runs the query (execute), timing it on the way.
    """

    def __init__(self):
        self.count = 0
        self.seconds = 0.0

    def __call__(self, execute, sql, params, many, context):
        start = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            self.count += 1
            self.seconds += time.perf_counter() - start


class ServerTimingMiddleware:
    """Adds "Server-Timing: db;dur=..;desc=.., app;dur=.." to every response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        timer = QueryTimer()
        start = time.perf_counter()
        with connection.execute_wrapper(timer):
            response = self.get_response(request)
        total_ms = (time.perf_counter() - start) * 1000
        response["Server-Timing"] = (
            f'db;dur={timer.seconds * 1000:.1f};desc="{timer.count} queries", '
            f"app;dur={total_ms:.1f}"
        )
        return response
