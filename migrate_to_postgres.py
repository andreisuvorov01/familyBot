#!/usr/bin/env python3
"""
Скрипт для миграции с SQLite на PostgreSQL
"""

import asyncio
import sqlite3
import asyncpg
from datetime import datetime
from typing import List, Dict, Any
import json


async def migrate_to_postgres():
    """Миграция данных из SQLite в PostgreSQL"""
    
    # Конфигурация
    sqlite_db = "family_base.db"
    postgres_config = {
        "host": "localhost",
        "port": 5432,
        "database": "familybot",
        "user": "postgres",
        "password": "your_password"
    }
    
    print("🚀 Начинаем миграцию с SQLite на PostgreSQL...")
    
    # 1. Подключаемся к SQLite
    print("📊 Подключаемся к SQLite...")
    sqlite_conn = sqlite3.connect(sqlite_db)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    
    # 2. Подключаемся к PostgreSQL
    print("🐘 Подключаемся к PostgreSQL...")
    pg_conn = await asyncpg.connect(**postgres_config)
    
    try:
        # 3. Создаем таблицы в PostgreSQL
        print("🗄️ Создаем таблицы в PostgreSQL...")
        
        await pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                tg_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(32),
                role VARCHAR(10),
                family_id VARCHAR(10),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_users_tg_id ON users(tg_id);
            CREATE INDEX IF NOT EXISTS idx_users_family_id ON users(family_id);
        """)
        
        await pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description VARCHAR(1024),
                status VARCHAR(20) DEFAULT 'pending',
                visibility VARCHAR(10) DEFAULT 'common',
                deadline TIMESTAMP,
                reminder_sent BOOLEAN DEFAULT FALSE,
                repeat_rule VARCHAR(20),
                owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                family_id VARCHAR(10) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_tasks_family_id ON tasks(family_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id);
            CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline);
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        """)
        
        await pg_conn.execute("""
            CREATE TABLE IF NOT EXISTS subtasks (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                is_done BOOLEAN DEFAULT FALSE,
                task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS idx_subtasks_task_id ON subtasks(task_id);
        """)
        
        # 4. Мигрируем пользователей
        print("👥 Мигрируем пользователей...")
        sqlite_cursor.execute("SELECT * FROM users")
        users = sqlite_cursor.fetchall()
        
        for user in users:
            await pg_conn.execute("""
                INSERT INTO users (id, tg_id, username, role, family_id, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO NOTHING
            """, user["id"], user["tg_id"], user["username"], 
                user["role"], user["family_id"], user.get("created_at"))
        
        print(f"✅ Пользователи мигрированы: {len(users)} записей")
        
        # 5. Мигрируем задачи
        print("📝 Мигрируем задачи...")
        sqlite_cursor.execute("SELECT * FROM tasks")
        tasks = sqlite_cursor.fetchall()
        
        for task in tasks:
            await pg_conn.execute("""
                INSERT INTO tasks (
                    id, title, description, status, visibility,
                    deadline, reminder_sent, repeat_rule,
                    owner_id, family_id, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (id) DO NOTHING
            """, 
                task["id"], task["title"], task["description"],
                task["status"], task["visibility"], task["deadline"],
                task["reminder_sent"], task.get("repeat_rule"),
                task["owner_id"], task["family_id"], task.get("created_at")
            )
        
        print(f"✅ Задачи мигрированы: {len(tasks)} записей")
        
        # 6. Мигрируем подзадачи
        print("📋 Мигрируем подзадачи...")
        sqlite_cursor.execute("SELECT * FROM subtasks")
        subtasks = sqlite_cursor.fetchall()
        
        for subtask in subtasks:
            await pg_conn.execute("""
                INSERT INTO subtasks (id, title, is_done, task_id)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO NOTHING
            """, subtask["id"], subtask["title"], 
                subtask["is_done"], subtask["task_id"])
        
        print(f"✅ Подзадачи мигрированы: {len(subtasks)} записей")
        
        # 7. Обновляем sequences
        print("🔄 Обновляем sequences...")
        
        # Получаем максимальные ID
        sqlite_cursor.execute("SELECT MAX(id) as max_id FROM users")
        max_user_id = sqlite_cursor.fetchone()["max_id"] or 0
        
        sqlite_cursor.execute("SELECT MAX(id) as max_id FROM tasks")
        max_task_id = sqlite_cursor.fetchone()["max_id"] or 0
        
        sqlite_cursor.execute("SELECT MAX(id) as max_id FROM subtasks")
        max_subtask_id = sqlite_cursor.fetchone()["max_id"] or 0
        
        # Обновляем sequences
        await pg_conn.execute(f"""
            SELECT setval('users_id_seq', {max_user_id}, true);
            SELECT setval('tasks_id_seq', {max_task_id}, true);
            SELECT setval('subtasks_id_seq', {max_subtask_id}, true);
        """)
        
        print("✅ Sequences обновлены")
        
        # 8. Проверяем целостность данных
        print("🔍 Проверяем целостность данных...")
        
        # Подсчет записей
        pg_users_count = await pg_conn.fetchval("SELECT COUNT(*) FROM users")
        pg_tasks_count = await pg_conn.fetchval("SELECT COUNT(*) FROM tasks")
        pg_subtasks_count = await pg_conn.fetchval("SELECT COUNT(*) FROM subtasks")
        
        sqlite_cursor.execute("SELECT COUNT(*) FROM users")
        sqlite_users_count = sqlite_cursor.fetchone()[0]
        
        sqlite_cursor.execute("SELECT COUNT(*) FROM tasks")
        sqlite_tasks_count = sqlite_cursor.fetchone()[0]
        
        sqlite_cursor.execute("SELECT COUNT(*) FROM subtasks")
        sqlite_subtasks_count = sqlite_cursor.fetchone()[0]
        
        print(f"\n📊 Результаты миграции:")
        print(f"   Пользователи: SQLite={sqlite_users_count}, PostgreSQL={pg_users_count}")
        print(f"   Задачи: SQLite={sqlite_tasks_count}, PostgreSQL={pg_tasks_count}")
        print(f"   Подзадачи: SQLite={sqlite_subtasks_count}, PostgreSQL={pg_subtasks_count}")
        
        if (pg_users_count == sqlite_users_count and 
            pg_tasks_count == sqlite_tasks_count and
            pg_subtasks_count == sqlite_subtasks_count):
            print("\n🎉 Миграция успешно завершена!")
            print("\n📝 Следующие шаги:")
            print("1. Обновите DATABASE_URL в .env файле:")
            print("   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/familybot")
            print("2. Перезапустите приложение")
            print("3. Протестируйте работу с новой базой данных")
        else:
            print("\n⚠️  Обнаружены расхождения в количестве записей!")
            print("   Проверьте логи и выполните миграцию заново.")
        
    except Exception as e:
        print(f"\n❌ Ошибка при миграции: {str(e)}")
        raise
    
    finally:
        # Закрываем соединения
        sqlite_conn.close()
        await pg_conn.close()
        print("\n🔌 Соединения закрыты")


if __name__ == "__main__":
    asyncio.run(migrate_to_postgres())