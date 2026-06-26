# migrate_add_region.py
import sqlite3

DB_NAME = 'requirements.db'

def add_region_column():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Проверяем, существует ли колонка
        cursor.execute("PRAGMA table_info(objects_settings)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'region' not in columns:
            cursor.execute('ALTER TABLE objects_settings ADD COLUMN region TEXT DEFAULT ""')
            print("✅ Колонка 'region' добавлена")
        else:
            print("ℹ️ Колонка 'region' уже существует")
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == '__main__':
    add_region_column()