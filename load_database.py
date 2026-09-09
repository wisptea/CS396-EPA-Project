import os
import pandas as pd
import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password=os.getenv("DB_PASSWORD"),
    database="epadata"
)

cursor = conn.cursor()

print("Connected to MySQL!")
