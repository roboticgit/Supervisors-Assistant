def format_message(message: str) -> str:
    """Formats a message for sending in Discord."""
    return message.strip()

def parse_time(time_str: str) -> int:
    """Parses a time string and returns the time in seconds."""
    # Example implementation: convert '10m' to 600 seconds
    if time_str.endswith('m'):
        return int(time_str[:-1]) * 60
    elif time_str.endswith('h'):
        return int(time_str[:-1]) * 3600
    elif time_str.endswith('s'):
        return int(time_str[:-1])
    else:
        raise ValueError("Invalid time format. Use '10m', '1h', or '30s'.")