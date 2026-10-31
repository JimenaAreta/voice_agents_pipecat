"""Persistent demo availability and reservations: one slot per date and time."""

import calendar
from datetime import date
from contextlib import closing
import os
from pathlib import Path
import sqlite3


TIMES = ("18:00", "19:00", "20:00", "21:00", "22:00")
# Reproducible demo pattern: free days, full days, and different occupied hours.
_FREE_HOURS = (
    TIMES,
    (),
    ("18:00", "20:00", "22:00"),
    ("19:00", "21:00"),
    ("18:00", "21:00"),
    ("18:00", "19:00", "22:00"),
    ("19:00", "20:00", "22:00"),
)


class SlotUnavailableError(Exception):
    """Another reservation or the initial configuration blocks the requested slot."""


def _connect() -> sqlite3.Connection:
    path = Path(os.getenv("RESERVATIONS_DB_PATH", "data/reservations.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path, timeout=2)


def _initialize(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS reservations (
            id TEXT PRIMARY KEY,
            reservation_date TEXT NOT NULL,
            party_size INTEGER NOT NULL,
            reservation_time TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS reservation_schedule (
            time TEXT PRIMARY KEY, enabled INTEGER NOT NULL CHECK(enabled IN (0, 1))
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS reservation_calendar (
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            enabled INTEGER NOT NULL CHECK(enabled IN (0, 1)),
            PRIMARY KEY(date, time)
        )"""
    )
    # INSERT OR IGNORE preserves later edits and does not reset availability.
    connection.executemany(
        "INSERT OR IGNORE INTO reservation_schedule(time, enabled) VALUES (?, ?)",
        [("18:00", 1), ("19:00", 1), ("20:00", 0), ("21:00", 0), ("22:00", 1)],
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS reservation_slot ON reservations(reservation_date, reservation_time)"
    )


def _seed_calendar(connection: sqlite3.Connection, year: int, month: int) -> None:
    rows = []
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        free = _FREE_HOURS[day % len(_FREE_HOURS)]
        rows.extend((date(year, month, day).isoformat(), time, int(time in free)) for time in TIMES)
    connection.executemany(
        "INSERT OR IGNORE INTO reservation_calendar(date, time, enabled) VALUES (?, ?, ?)", rows
    )


def initialize_calendar(year: int, month: int) -> None:
    """Creates the full month without overwriting existing slots or reservations."""
    with closing(_connect()) as connection, connection:
        _initialize(connection)
        _seed_calendar(connection, year, month)


def _schedule(connection: sqlite3.Connection, reservation_date: str) -> dict[str, bool]:
    try:
        requested_date = date.fromisoformat(reservation_date)
    except ValueError:
        # Backward compatibility with textual dates from the previous example.
        return dict(connection.execute("SELECT time, enabled FROM reservation_schedule"))
    _seed_calendar(connection, requested_date.year, requested_date.month)
    return dict(connection.execute(
        "SELECT time, enabled FROM reservation_calendar WHERE date = ?", (reservation_date,)
    ))


def available_times(reservation_date: str) -> list[str]:
    """Reads available time slots for a date, including past call reservations."""
    with closing(_connect()) as connection, connection:
        _initialize(connection)
        schedule = _schedule(connection, reservation_date)
        occupied = {row[0] for row in connection.execute(
            "SELECT reservation_time FROM reservations WHERE reservation_date = ?", (reservation_date,)
        )}
        return sorted(time for time, enabled in schedule.items() if enabled and time not in occupied)


def save_reservation(reservation_id: str, details: dict) -> None:
    """Checks and claims the slot in a transaction; retries are idempotent."""
    with closing(_connect()) as connection, connection:
        # Serializes the check and write across connections/processes.
        connection.execute("BEGIN IMMEDIATE")
        _initialize(connection)
        enabled = _schedule(connection, details["reservation_date"]).get(details["reservation_time"], False)
        occupied = connection.execute(
            """SELECT 1 FROM reservations
                WHERE reservation_date = ? AND reservation_time = ? AND id != ?""",
            (details["reservation_date"], details["reservation_time"], reservation_id),
        ).fetchone()
        if not enabled or occupied:
            raise SlotUnavailableError()
        connection.execute(
            """INSERT INTO reservations
                (id, reservation_date, party_size, reservation_time, customer_name, phone_number)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    reservation_date=excluded.reservation_date,
                    party_size=excluded.party_size,
                    reservation_time=excluded.reservation_time,
                    customer_name=excluded.customer_name,
                    phone_number=excluded.phone_number""",
            (reservation_id, details["reservation_date"], details["party_size"],
             details["reservation_time"], details["customer_name"], details["phone_number"]),
        )
