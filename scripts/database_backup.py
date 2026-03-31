#!/usr/bin/env python3
"""
Скрипт для створення та відновлення backup бази даних
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def run_command(command, check=True):
    """Виконати команду і повернути результат"""
    try:
        result = subprocess.run(command, shell=True, check=check, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Помилка виконання команди: {e}")
        print(f"Stderr: {e.stderr}")
        return None

def create_backup():
    """Створити backup бази даних"""
    print("🔄 Створення backup бази даних...")
    
    # Створити backup директорію
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    # Створити ім'я файлу з timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"kvitkova_crm_backup_{timestamp}.sql"
    
    # Створити backup (--clean --if-exists дозволяє відновлювати на існуючу БД)
    cmd = f'docker compose exec -T postgres pg_dump --clean --if-exists -U kvitkova_user kvitkova_crm > {backup_file}'
    result = run_command(cmd, check=False)
    
    if result is not None:
        print(f"✅ Backup створено: {backup_file}")
        return backup_file
    else:
        print("❌ Помилка створення backup")
        return None

def restore_backup(backup_file):
    """Відновити базу даних з backup"""
    if not backup_file:
        print("❌ Файл backup не вказано")
        return False
    
    backup_path = Path(backup_file)
    if not backup_path.exists():
        print(f"❌ Файл backup не знайдено: {backup_file}")
        return False
    
    print(f"🔄 Відновлення з backup: {backup_file}")
    
    # Відновити backup
    cmd = f'docker compose exec -T postgres psql -U kvitkova_user -d kvitkova_crm < {backup_file}'
    result = run_command(cmd, check=False)
    
    if result is not None:
        print("✅ Backup відновлено успішно")
        return True
    else:
        print("❌ Помилка відновлення backup")
        return False

def list_backups():
    """Показати список доступних backup"""
    backup_dir = Path("backups")
    if not backup_dir.exists():
        print("📁 Директорія backups не існує")
        return
    
    backup_files = list(backup_dir.glob("*.sql"))
    if not backup_files:
        print("📁 Backup файли не знайдено")
        return
    
    print("📋 Доступні backup файли:")
    for i, backup_file in enumerate(sorted(backup_files, reverse=True), 1):
        size = backup_file.stat().st_size
        size_mb = size / (1024 * 1024)
        print(f"  {i}. {backup_file.name} ({size_mb:.2f} MB)")

def main():
    """Головна функція"""
    if len(sys.argv) < 2:
        print("🚀 === BACKUP БАЗИ ДАНИХ ===")
        print("Використання:")
        print("  python3 scripts/database_backup.py create    # Створити backup")
        print("  python3 scripts/database_backup.py list       # Показати список backup")
        print("  python3 scripts/database_backup.py restore <file>  # Відновити з backup")
        return
    
    action = sys.argv[1]
    
    if action == "create":
        create_backup()
    elif action == "list":
        list_backups()
    elif action == "restore":
        if len(sys.argv) < 3:
            print("❌ Вкажіть файл backup для відновлення")
            return
        restore_backup(sys.argv[2])
    else:
        print(f"❌ Невідома дія: {action}")

if __name__ == "__main__":
    main() 