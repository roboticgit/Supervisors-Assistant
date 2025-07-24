import mariadb
import os

DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

def get_db_connection():
    return mariadb.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

def fetch_all_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

def fetch_valid_users():
    users = fetch_all_users()
    return [u for u in users if all(u.get(field) not in (None, 'Not set') for field in [
        'roblox_username', 'discord_id', 'clickup_email', 'primary_department', 'timezone', 'reminder_preferences'])]

def fetch_user_by_query(query):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE clickup_email = %s OR roblox_username = %s", (query, query))
    user = cursor.fetchone()
    conn.close()
    return user
