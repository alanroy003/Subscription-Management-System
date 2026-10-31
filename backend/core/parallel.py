"""Run independent read-only database calls concurrently.

The Supabase pooler is a long round trip away, so a page that needs eight aggregates is eight round trips.
Running them on pooled connections in parallel turns that into one or two. SQLite (tests) runs sequentially.
"""
from concurrent.futures import ThreadPoolExecutor

from django.db import connection, connections

_executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="db-par")


def _wrap(fn):
    def run():
        try:
            return fn()
        finally:
            connections.close_all()  # return this thread's connection to the pool

    return run


def run_parallel(tasks: dict, parallel: bool | None = None) -> dict:
    if parallel is None:
        parallel = connection.vendor == "postgresql"
    if not parallel:
        return {name: fn() for name, fn in tasks.items()}
    futures = {name: _executor.submit(_wrap(fn)) for name, fn in tasks.items()}
    return {name: f.result() for name, f in futures.items()}


def map_parallel(fn, items, parallel: bool | None = None) -> list:
    if parallel is None:
        parallel = connection.vendor == "postgresql"
    if not parallel:
        return [fn(i) for i in items]
    wrapped = _wrap_arg(fn)
    return list(_executor.map(wrapped, items))


def _wrap_arg(fn):
    def run(item):
        try:
            return fn(item)
        finally:
            connections.close_all()

    return run
