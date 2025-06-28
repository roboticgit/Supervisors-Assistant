import os
import mysql.connector
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def test_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            port=3306
        )
        print('✅ Successfully connected to the database!')
        connection.close()
    except Exception as e:
        print(f'❌ Failed to connect to the database: {e}')

if __name__ == '__main__':
    test_db_connection()
