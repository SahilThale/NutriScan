import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",       # change if you set a different MySQL user
        password="admin",
        database="nutriscan"
    )
