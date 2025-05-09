import datetime

def parse_time(time_str):
    # Example helper function to parse time strings
    return datetime.datetime.strptime(time_str, "%H:%M")