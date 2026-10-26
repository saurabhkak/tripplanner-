"""Save and load bookings using Amazon DynamoDB."""

import os
from datetime import datetime, timezone
from uuid import uuid4


TABLE_NAME = os.getenv("DYNAMODB_TABLE", "TripBookings")


def _get_bookings_table():
    """Return the configured DynamoDB table using the standard AWS credential chain."""
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError(
            "DynamoDB storage requires boto3. Install it with: python -m pip install boto3"
        ) from exc

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    return dynamodb.Table(TABLE_NAME)


def load_bookings():
    """Load all booking records from DynamoDB."""
    table = _get_bookings_table()
    bookings = []
    scan_kwargs = {}

    while True:
        response = table.scan(**scan_kwargs)
        bookings.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    return sorted(bookings, key=lambda booking: booking.get("booked_at", ""))


def save_booking(source, destination, mode, details):
    """Save a new booking as a DynamoDB item."""
    booking_id = str(uuid4())
    new_booking = {
        "booking_id": booking_id,
        "id": booking_id,
        "source": source.title(),
        "destination": destination.title(),
        "mode": mode.title(),
        "time": details["time"],
        "distance": details.get("distance", "N/A"),
        "fare": details["fare"],
        "data_source": details.get("source", "Static data"),
        "booked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    _get_bookings_table().put_item(Item=new_booking)
    print(f"\nBooking saved! Your Booking ID: #{booking_id}")


def view_all_bookings():
    """Display all bookings currently stored in DynamoDB."""
    bookings = load_bookings()

    if not bookings:
        print("\nNo bookings found.")
        return

    print(f"\n{'=' * 72}")
    print("  All Bookings")
    print(f"{'=' * 72}")

    for booking in bookings:
        booking_id = booking.get("id", booking.get("booking_id", "?"))
        print(
            f"ID #{booking_id} | "
            f"{booking['source']} -> {booking['destination']}"
        )
        print(
            f"         Mode: {booking['mode']} | "
            f"Distance: {booking.get('distance', 'N/A')} | "
            f"Fare: Rs.{booking['fare']}"
        )
        print(
            f"         Source: {booking.get('data_source', 'Static data')} | "
            f"{booking['booked_at']}"
        )
        print(f"{'-' * 72}")
