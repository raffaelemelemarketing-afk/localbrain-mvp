#!/usr/bin/env python3
"""
Migration script to add image_url column to items table
"""
import sqlite3
import os

def migrate_database():
    db_path = "localbrain.db"

    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if image_url column already exists
        cursor.execute("PRAGMA table_info(items)")
        columns = [column[1] for column in cursor.fetchall()]

        if "image_url" in columns:
            print("image_url column already exists in items table")
            return True

        # Add image_url column
        cursor.execute("ALTER TABLE items ADD COLUMN image_url TEXT DEFAULT ''")
        conn.commit()
        print("✅ Successfully added image_url column to items table")
        return True

    except Exception as e:
        print(f"❌ Error migrating database: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()