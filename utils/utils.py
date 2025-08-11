from datetime import datetime
import pytz

def user_input_to_utc_unix(date_str: str, time_str: str, user_tz_str: str) -> int:
    """
    Converts a user's local date/time into a UTC Unix timestamp.

    Args:
        date_str: Date in YYYY-MM-DD format.
        time_str: Time in HH:MM 24-hour format.
        user_tz_str: User's timezone string (e.g., 'America/New_York').

    Returns:
        int: UTC Unix timestamp.
    """
    try:
        # Parse date/time
        local_dt = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M")

        # Localize timezone
        user_tz = pytz.timezone(user_tz_str)
        local_dt = user_tz.localize(local_dt)

        # Convert to UTC
        utc_dt = local_dt.astimezone(pytz.utc)

        # Get Unix timestamp
        return int(utc_dt.timestamp())

    except Exception as e:
        raise ValueError(f"Invalid date/time/timezone: {e}")
