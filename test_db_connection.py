import os
import mysql.connector
from dotenv import load_dotenv

print('Loading .env...')
load_dotenv()

print('Environment variables:')
print('DB_HOST:', os.getenv('DB_HOST'))
print('DB_USER:', os.getenv('DB_USER'))
print('DB_PASSWORD:', os.getenv('DB_PASSWORD'))
print('DB_NAME:', os.getenv('DB_NAME'))

def test_db_connection():
    print('Attempting to connect to the database...')
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
