import sqlite3

DB_NAME = "family_base.db"

try:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    print("🔄 Добавляем колонку repeat_rule...")

    # SQL команда для добавления колонки
    cursor.execute("ALTER TABLE tasks ADD COLUMN repeat_rule VARCHAR(20)")

    conn.commit()
    print("✅ Успешно! Колонка добавлена.")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e):
        print("⚠️ Колонка уже существует.")
    else:
        print(f"❌ Ошибка: {e}")
finally:
    conn.close()
