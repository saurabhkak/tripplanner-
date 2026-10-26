
from flask import Flask, render_template_string, request
from transport import get_options
from postgres_storage import init_db, save_booking, load_bookings

app = Flask(__name__)

PAGE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Trip Planner</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto; }
        input, button { padding: 10px; margin: 5px; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ccc; padding: 10px; text-align: left; }
    </style>
</head>
<body>
    <h1>Wayfarer — Trip Planner</h1>
    <p><a href="{{ url_for('bookings') }}">My bookings</a></p>

    <form method="post">
        <input type="hidden" name="action" value="search">
        <label>From:</label>
        <input name="source" required placeholder="e.g. Mumbai" value="{{ source_city }}">
        <label>To:</label>
        <input name="destination" required placeholder="e.g. Pune" value="{{ destination_city }}">
        <button type="submit">Find routes</button>
    </form>

    {% if message %}<p>{{ message }}</p>{% endif %}
    {% if error %}<p>{{ error }}</p>{% endif %}

    {% if options %}
        <h2>Options: {{ source_city }} → {{ destination_city }}</h2>
        <table>
            <tr><th>Transport</th><th>Time</th><th>Fare</th><th>Distance</th><th></th></tr>
            {% for mode, details in options.items() %}
            <tr>
                <td>{{ mode|title }}</td>
                <td>{{ details.get('time', 'N/A') }}</td>
                <td>₹{{ details.get('fare', 'N/A') }}</td>
                <td>{{ details.get('distance', 'N/A') }}</td>
                <td>
                    <form method="post">
                        <input type="hidden" name="action" value="book">
                        <input type="hidden" name="source" value="{{ source_city }}">
                        <input type="hidden" name="destination" value="{{ destination_city }}">
                        <input type="hidden" name="mode" value="{{ mode }}">
                        <button type="submit">Book</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </table>
    {% endif %}
</body>
</html>
"""

BOOKINGS_PAGE = """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>My Bookings</title></head>
<body>
    <h1>My bookings</h1>
    <p><a href="{{ url_for('home') }}">Back to trip planner</a></p>

    {% if error %}<p>{{ error }}</p>{% endif %}

    {% if rows %}
        <table border="1" cellpadding="8">
            <tr><th>ID</th><th>Route</th><th>Mode</th><th>Time</th><th>Fare</th><th>Booked at</th></tr>
            {% for booking in rows %}
            <tr>
                <td>{{ booking['id'] }}</td>
                <td>{{ booking['source'] }} → {{ booking['destination'] }}</td>
                <td>{{ booking['mode'] }}</td>
                <td>{{ booking['travel_time'] }}</td>
                <td>₹{{ booking['fare'] }}</td>
                <td>{{ booking['booked_at'] }}</td>
            </tr>
            {% endfor %}
        </table>
    {% elif not error %}
        <p>No bookings yet.</p>
    {% endif %}
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def home():
    source_city = ""
    destination_city = ""
    options = None
    message = ""
    error = ""

    if request.method == "POST":
        source_city = request.form.get("source", "").strip()
        destination_city = request.form.get("destination", "").strip()
        action = request.form.get("action", "search")

        if not source_city or not destination_city:
            error = "Enter both a source and destination."
        else:
            options = get_options(source_city, destination_city)

            if options is None:
                error = f"No routes found for {source_city} → {destination_city}."
            elif action == "book":
                mode = request.form.get("mode", "").lower()

                if mode not in options:
                    error = "That transport option is not available."
                else:
                    try:
                        init_db()
                        booking_id = save_booking(
                            source_city, destination_city, mode, options[mode]
                        )
                        message = f"Booking saved! Booking ID: #{booking_id}"
                    except Exception:
                        app.logger.exception("Could not save the booking")
                        error = "Could not save booking. Check the EC2-to-RDS connection."

    return render_template_string(
        PAGE,
        source_city=source_city,
        destination_city=destination_city,
        options=options,
        message=message,
        error=error,
    )


@app.route("/bookings")
def bookings():
    try:
        init_db()
        rows = load_bookings()
        error = ""
    except Exception:
        app.logger.exception("Could not load bookings")
        rows = []
        error = "Could not load bookings. Check the EC2-to-RDS connection."

    return render_template_string(BOOKINGS_PAGE, rows=rows, error=error)


if __name__ == "__main__":
    app.run(debug=True)

