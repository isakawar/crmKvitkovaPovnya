#!/usr/bin/env python3
"""
Скрипт для міграції даних з Docker volume в локальну директорію
"""

import os
import subprocess
import shutil
import sys
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

def backup_current_data():
    """Створити backup поточних даних"""
    print("🔄 Створення backup поточних даних...")
    
    # Створити backup директорію
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    # Створити backup бази даних
    backup_file = backup_dir / f"backup_$(date +%Y%m%d_%H%M%S).sql"
    
    cmd = f'docker compose exec -T postgres pg_dump -U kvitkova_user kvitkova_crm > {backup_file}'
    result = run_command(cmd, check=False)
    
    if result is not None:
        print(f"✅ Backup створено: {backup_file}")
        return backup_file
    else:
        print("❌ Помилка створення backup")
        return None

def migrate_volume_data():
    """Мігрувати дані з Docker volume в локальну директорію"""
    print("🔄 Міграція даних з Docker volume...")
    
    # Отримати шлях до volume
    volume_inspect = run_command('docker volume inspect crmkvitkovapovnya_postgres_data')
    if not volume_inspect:
        print("❌ Не вдалося знайти Docker volume")
        return False
    
    # Зупинити PostgreSQL контейнер
    print("⏹️ Зупинка PostgreSQL контейнера...")
    run_command("docker compose stop postgres")
    
    # Скопіювати дані з volume в локальну директорію
    print("📁 Копіювання даних...")
    data_dir = Path("data/postgres")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Використати тимчасовий контейнер для копіювання
    copy_cmd = f'''
    docker run --rm -v crmkvitkovapovnya_postgres_data:/source -v {data_dir.absolute()}:/dest alpine sh -c "
        cp -r /source/* /dest/ 2>/dev/null || true
        chown -R 999:999 /dest/
    "
    '''
    
    result = run_command(copy_cmd)
    if result is None:
        print("❌ Помилка копіювання даних")
        return False
    
    print("✅ Дані успішно скопійовано")
    return True

def update_permissions():
    """Оновити права доступу для PostgreSQL"""
    print("🔐 Оновлення прав доступу...")
    
    data_dir = Path("data/postgres")
    if data_dir.exists():
        # PostgreSQL потребує права 999:999 (postgres user)
        run_command(f"sudo chown -R 999:999 {data_dir}")
        run_command(f"sudo chmod -R 700 {data_dir}")
        print("✅ Права доступу оновлено")
    else:
        print("⚠️ Директорія data/postgres не існує")

def main():
    """Головна функція"""
    print("🚀 === МІГРАЦІЯ DOCKER VOLUME В ЛОКАЛЬНУ ДИРЕКТОРІЮ ===")
    
    # Перевірити, чи запущений PostgreSQL
    postgres_status = run_command("docker compose ps postgres --format '{{.Status}}'")
    if not postgres_status or "Up" not in postgres_status:
        print("❌ PostgreSQL контейнер не запущений")
        return
    
    # Створити backup
    backup_file = backup_current_data()
    
    # Мігрувати дані
    if migrate_volume_data():
        # Оновити права доступу
        update_permissions()
        
        # Запустити з новою конфігурацією
        print("🔄 Запуск з новою конфігурацією...")
        run_command("docker compose up postgres -d")
        
        print("✅ Міграція завершена успішно!")
        print(f"📁 Дані тепер зберігаються в: {Path('data/postgres').absolute()}")
        if backup_file:
            print(f"💾 Backup збережено в: {backup_file}")
    else:
        print("❌ Міграція не вдалася")
        if backup_file:
            print(f"💾 Можна відновити з backup: {backup_file}")

if __name__ == "__main__":
    main() 