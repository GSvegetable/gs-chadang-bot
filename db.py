import sqlite3
import os

DB_PATH = 'chadang.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance REAL DEFAULT 0.0
        )
    ''')
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0.0

def add_balance(user_id, amount):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO users (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?", (user_id, amount, amount))
    conn.commit()
    conn.close()

def deduct_balance(user_id, amount):
    conn = get_db()
    cur = conn.cursor()
    current = get_balance(user_id)
    if current >= amount:
        cur.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False
