import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            database='gym_buscador',
            user='root',
            password=''
        )
        return conn
    except Error as e:
        print(f"Error conectando a MySQL: {e}")
        return None