
import os

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()


def _connect():
    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [key for key in required if not os.getenv(key)]

    if missing:
        raise RuntimeError(
            "Missing database environment variables: " + ", ".join(missing)
        )

    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        sslmode="require",
        connect_timeout=5,
        row_factory=dict_row,
    )


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id BIGSERIAL PRIMARY KEY,
                source TEXT NOT NULL,
                destination TEXT NOT NULL,
                mode TEXT NOT NULL,
                travel_time TEXT,
                distance TEXT,
                fare NUMERIC(10, 2) NOT NULL,
                data_source TEXT,
                booked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def save_booking(source, destination, mode, details):
    with _connect() as conn:
        row = conn.execute(
            """
            INSERT INTO bookings
                (source, destination, mode, travel_time, distance, fare, data_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                source.title(),
                destination.title(),
                mode.title(),
                details.get("time", "N/A"),
                details.get("distance", "N/A"),
                details["fare"],
                details.get("source", "Static data"),
            ),
        ).fetchone()

    return row["id"]


def load_bookings():
    with _connect() as conn:
        return conn.execute(
            """
            SELECT id, source, destination, mode, travel_time,
                   distance, fare, data_source, booked_at
            FROM bookings
            ORDER BY booked_at DESC
            """
        ).fetchall()

