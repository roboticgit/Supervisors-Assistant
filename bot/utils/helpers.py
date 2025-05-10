import datetime
import mysql.connector
from datetime import datetime
import pytz
import os

def parse_time(time_str):
    # Example helper function to parse time strings
    return datetime.datetime.strptime(time_str, "%H:%M")

# Database connection
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

# Convert user input date and time to UNIX timestamp based on their timezone
def convert_to_unix(date_str, time_str, user_timezone):
    user_tz = pytz.timezone(user_timezone)
    naive_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    localized_datetime = user_tz.localize(naive_datetime)
    return int(localized_datetime.timestamp() * 1000)  # ClickUp expects milliseconds

# Convert UNIX timestamp to BST/GMT for task title
def convert_to_bst_gmt(unix_timestamp):
    utc_time = datetime.utcfromtimestamp(unix_timestamp / 1000)
    bst_gmt_tz = pytz.timezone('Europe/London')
    return utc_time.astimezone(bst_gmt_tz).strftime("%Y-%m-%d %H:%M")