"""
Memory — память пользователей и статистика.
SQLite база данных.
"""

import sqlite3
import os
from datetime import datetime, timedelta

DB_FILE = 'lexaz.db'

# ═══════════════════════════════════════════════════════════════
# ИНИЦИАЛИЗАЦИЯ
# ══════════════════════════════════════════════════════════════

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            first_seen TEXT,
            last_seen TEXT,
            messages_count INTEGER DEFAULT 0,
            custom_name TEXT,
            communication_style TEXT DEFAULT 'formal',
            use_name INTEGER DEFAULT 0,
            use_emoji INTEGER DEFAULT 1
        )
    """)
    
    # Миграция: добавляем новые колонки, если их нет
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN use_name INTEGER DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN use_emoji INTEGER DEFAULT 1")
    except:
        pass
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            review_text TEXT,
            timestamp TEXT
        )
    """)
    
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════════════════════
# ПОЛЬЗОВАТЕЛИ
# ═══════════════════════════════════════════════════════════════

def register_user(user_id: int, username: str = None, first_name: str = None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone():
        cursor.execute("""
            UPDATE users 
            SET last_seen = ?, username = ?, first_name = ?, messages_count = messages_count + 1
            WHERE user_id = ?
        """, (now, username, first_name, user_id))
    else:
        cursor.execute("""
            INSERT INTO users (user_id, username, first_name, first_seen, last_seen, messages_count, use_name, use_emoji)
            VALUES (?, ?, ?, ?, ?, 1, 0, 1)
        """, (user_id, username, first_name, now, now))
    
    conn.commit()
    conn.close()

def get_user(user_id: int) -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, first_name, first_seen, last_seen, 
               messages_count, custom_name, communication_style, use_name, use_emoji
        FROM users WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        'user_id': row[0], 'username': row[1], 'first_name': row[2],
        'first_seen': row[3], 'last_seen': row[4], 'messages_count': row[5],
        'custom_name': row[6], 'communication_style': row[7],
        'use_name': bool(row[8]), 'use_emoji': bool(row[9])
    }

def set_custom_name(user_id: int, name: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET custom_name = ? WHERE user_id = ?", (name, user_id))
    conn.commit()
    conn.close()

def set_communication_style(user_id: int, style: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET communication_style = ? WHERE user_id = ?", (style, user_id))
    conn.commit()
    conn.close()

def set_use_name(user_id: int, use: bool):
    """Устанавливает, обращаться ли к пользователю по имени"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET use_name = ? WHERE user_id = ?", (1 if use else 0, user_id))
    conn.commit()
    conn.close()

def set_use_emoji(user_id: int, use: bool):
    """Устанавливает, использовать ли эмодзи в ответах"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET use_emoji = ? WHERE user_id = ?", (1 if use else 0, user_id))
    conn.commit()
    conn.close()

def get_all_user_ids() -> list:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return ids

# ═══════════════════════════════════════════════════════════════
# ИСТОРИЯ
# ═══════════════════════════════════════════════════════════════

def add_to_history(user_id: int, role: str, content: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO history (user_id, role, content, timestamp)
        VALUES (?, ?, ?, ?)
    """, (user_id, role, content, now))
    conn.commit()
    conn.close()

def get_history(user_id: int, limit: int = 10) -> list:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content FROM history
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [{'role': row[0], 'content': row[1]} for row in reversed(rows)]

def clear_history(user_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════════════════════
# ОТЗЫВЫ
# ═══════════════════════════════════════════════════════════════

def add_review(user_id: int, username: str, first_name: str, review_text: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO reviews (user_id, username, first_name, review_text, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, username, first_name, review_text, now))
    conn.commit()
    conn.close()

def get_reviews(limit: int = 20) -> list:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, first_name, review_text, timestamp
        FROM reviews ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {'user_id': r[0], 'username': r[1], 'first_name': r[2],
         'review_text': r[3], 'timestamp': r[4]}
        for r in rows
    ]

# ═══════════════════════════════════════════════════════════════
# СТАТИСТИКА
# ═══════════════════════════════════════════════════════════════

def get_stats() -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(messages_count) FROM users")
    total_messages = cursor.fetchone()[0] or 0
    
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    cursor.execute("SELECT COUNT(*) FROM users WHERE last_seen >= ?", (yesterday,))
    active_24h = cursor.fetchone()[0]
    
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    cursor.execute("SELECT COUNT(*) FROM users WHERE last_seen >= ?", (week_ago,))
    active_7d = cursor.fetchone()[0]
    
    month_ago = (datetime.now() - timedelta(days=30)).isoformat()
    cursor.execute("SELECT COUNT(*) FROM users WHERE last_seen >= ?", (month_ago,))
    active_30d = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reviews")
    total_reviews = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT user_id, first_name, username, messages_count, last_seen
        FROM users ORDER BY messages_count DESC LIMIT 10
    """)
    top_users = cursor.fetchall()
    
    conn.close()
    
    return {
        'total_users': total_users,
        'total_messages': total_messages,
        'active_24h': active_24h,
        'active_7d': active_7d,
        'active_30d': active_30d,
        'total_reviews': total_reviews,
        'top_users': top_users
    }

# Инициализация при импорте
init_db()