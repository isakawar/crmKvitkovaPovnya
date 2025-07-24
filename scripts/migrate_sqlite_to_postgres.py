#!/usr/bin/env python3
"""
Скрипт для міграції даних з SQLite в PostgreSQL
"""

import os
import sys
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Завантажуємо змінні середовища
load_dotenv()

def get_sqlite_connection():
    """Підключення до SQLite бази даних"""
    sqlite_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'kvitkova_crm.db')
    if not os.path.exists(sqlite_path):
        print(f"❌ SQLite файл не знайдено: {sqlite_path}")
        return None
    
    return sqlite3.connect(sqlite_path)

def get_postgres_connection():
    """Підключення до PostgreSQL бази даних"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL не встановлено в змінних середовища")
        return None
    
    try:
        return psycopg2.connect(database_url)
    except Exception as e:
        print(f"❌ Помилка підключення до PostgreSQL: {e}")
        return None

def migrate_table(sqlite_conn, postgres_conn, table_name, columns):
    """Міграція таблиці з SQLite в PostgreSQL"""
    print(f"📦 Міграція таблиці: {table_name}")
    
    try:
        # Отримуємо дані з SQLite
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute(f"SELECT * FROM {table_name}")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            print(f"   ⚠️  Таблиця {table_name} порожня")
            return True
        
        print(f"   📊 Знайдено {len(rows)} записів")
        
        # Вставляємо дані в PostgreSQL
        postgres_cursor = postgres_conn.cursor()
        
        # Створюємо плейсхолдери для INSERT
        placeholders = ', '.join(['%s'] * len(columns))
        column_names = ', '.join(columns)
        
        insert_query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"
        
        # Вставляємо дані
        postgres_cursor.executemany(insert_query, rows)
        postgres_conn.commit()
        
        print(f"   ✅ Успішно мігровано {len(rows)} записів")
        return True
        
    except Exception as e:
        print(f"   ❌ Помилка міграції таблиці {table_name}: {e}")
        postgres_conn.rollback()
        return False

def main():
    """Основна функція міграції"""
    print("🔄 === МІГРАЦІЯ ДАНИХ З SQLITE В POSTGRESQL ===")
    print()
    
    # Підключення до баз даних
    sqlite_conn = get_sqlite_connection()
    if not sqlite_conn:
        return False
    
    postgres_conn = get_postgres_connection()
    if not postgres_conn:
        sqlite_conn.close()
        return False
    
    try:
        # Список таблиць для міграції
        tables = [
            ('user', ['id', 'username', 'password_hash', 'role', 'created_at']),
            ('client', ['id', 'instagram', 'phone', 'telegram', 'credits', 'marketing_source', 'personal_discount', 'created_at']),
            ('courier', ['id', 'name', 'phone', 'telegram_username', 'telegram_chat_id', 'telegram_registered', 'is_active', 'created_at']),
            ('order', ['id', 'client_id', 'order_date', 'delivery_date', 'status', 'total_amount', 'payment_method', 'comment', 'created_at', 'updated_at']),
            ('delivery', ['id', 'order_id', 'client_id', 'delivery_date', 'status', 'comment', 'created_at', 'updated_at', 'street', 'building_number', 'floor', 'entrance', 'is_pickup', 'time_from', 'time_to', 'size', 'phone', 'courier_id', 'delivered_at', 'status_changed_at', 'bouquet_size', 'delivery_type', 'price_at_delivery', 'is_subscription', 'preferences']),
            ('settings', ['id', 'type', 'value', 'description', 'created_at']),
        ]
        
        success_count = 0
        total_tables = len(tables)
        
        for table_name, columns in tables:
            if migrate_table(sqlite_conn, postgres_conn, table_name, columns):
                success_count += 1
        
        print()
        print(f"📊 Результат міграції: {success_count}/{total_tables} таблиць успішно мігровано")
        
        if success_count == total_tables:
            print("✅ Міграція завершена успішно!")
            return True
        else:
            print("⚠️  Міграція завершена з помилками")
            return False
            
    except Exception as e:
        print(f"❌ Критична помилка під час міграції: {e}")
        return False
    finally:
        sqlite_conn.close()
        postgres_conn.close()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 