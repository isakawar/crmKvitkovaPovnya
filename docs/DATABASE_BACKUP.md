# Backup та Відновлення Бази Даних

Цей документ описує як створювати backup та відновлювати базу даних PostgreSQL.

## 📁 Структура файлів

```
crmKvitkovaPovnya/
├── data/
│   └── postgres/          # Постійні дані PostgreSQL
├── backups/               # Backup файли
│   ├── kvitkova_crm_backup_20241224_143022.sql
│   └── pre_deploy_backup_20241224_143022.sql
└── scripts/
    ├── database_backup.py     # Скрипт для backup/restore
    └── migrate_volume_to_local.py  # Міграція з Docker volume
```

## 🚀 Швидкий старт

### Створення backup
```bash
# Автоматичний backup перед деплоєм
./scripts/docker-deploy.sh

# Ручне створення backup
python3 scripts/database_backup.py create

# Створення backup через Docker
docker compose exec postgres pg_dump -U kvitkova_user kvitkova_crm > backup.sql
```

### Відновлення з backup
```bash
# Відновлення через скрипт
python3 scripts/database_backup.py restore backups/kvitkova_crm_backup_20241224_143022.sql

# Відновлення через Docker
docker compose exec -T postgres psql -U kvitkova_user -d kvitkova_crm < backup.sql
```

### Перегляд доступних backup
```bash
python3 scripts/database_backup.py list
```

## 📋 Детальний опис

### 1. Автоматичний Backup

При кожному деплої через `docker-deploy.sh` автоматично створюється backup:
- Файл: `backups/pre_deploy_backup_YYYYMMDD_HHMMSS.sql`
- Створюється перед зупинкою контейнерів
- Зберігає всі дані на момент деплою

### 2. Ручний Backup

```bash
# Створити backup з timestamp
python3 scripts/database_backup.py create

# Результат: backups/kvitkova_crm_backup_20241224_143022.sql
```

### 3. Відновлення

```bash
# Відновити з конкретного файлу
python3 scripts/database_backup.py restore backups/kvitkova_crm_backup_20241224_143022.sql

# Відновити з останнього backup
python3 scripts/database_backup.py restore $(ls -t backups/*.sql | head -1)
```

### 4. Міграція з Docker Volume

Якщо ви використовували Docker volume і хочете перейти на локальне збереження:

```bash
# Мігрувати дані з volume в локальну директорію
python3 scripts/migrate_volume_to_local.py
```

## 🔧 Налаштування

### Постійне збереження даних

Дані зберігаються в локальній директорії `data/postgres/`:
- ✅ Дані зберігаються між перезапусками
- ✅ Дані зберігаються при перебудуванні образів
- ✅ Дані можна легко копіювати/переносити
- ✅ Дані включені в .gitignore

### Права доступу

PostgreSQL потребує правильні права доступу:
```bash
# Встановити права (потрібен sudo)
sudo chown -R 999:999 data/postgres/
sudo chmod -R 700 data/postgres/
```

## 🚨 Важливі зауваження

### Безпека
- Backup файли містять всі дані - зберігайте їх безпечно
- Не комітьте backup файли в Git
- Регулярно створюйте backup на зовнішніх носіях

### Продуктивність
- Backup великих баз може займати час
- Рекомендується створювати backup в неактивний час
- Можна використовувати `pg_dump` з опцією `--compress=9` для стиснення

### Відновлення
- Завжди тестуйте відновлення на тестовому середовищі
- Перевіряйте цілісність backup файлів
- Зберігайте кілька версій backup

## 📊 Моніторинг

### Перевірка розміру backup
```bash
# Розмір всіх backup
du -sh backups/

# Розмір останнього backup
ls -lh backups/ | tail -1
```

### Перевірка цілісності backup
```bash
# Тестова перевірка backup
docker compose exec postgres pg_restore --list backup.sql > /dev/null && echo "✅ Backup цілісний" || echo "❌ Backup пошкоджений"
```

## 🔄 Автоматизація

### Cron job для регулярних backup
```bash
# Додати в crontab (backup щодня о 2:00)
0 2 * * * cd /path/to/crmKvitkovaPovnya && python3 scripts/database_backup.py create

# Додати в crontab (очищення старих backup через 30 днів)
0 3 * * * find /path/to/crmKvitkovaPovnya/backups -name "*.sql" -mtime +30 -delete
```

### GitHub Actions для backup
```yaml
# .github/workflows/backup.yml
name: Database Backup
on:
  schedule:
    - cron: '0 2 * * *'  # Щодня о 2:00 UTC

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Create backup
        run: |
          python3 scripts/database_backup.py create
      - name: Upload backup
        uses: actions/upload-artifact@v2
        with:
          name: database-backup
          path: backups/
```

## 🆘 Вирішення проблем

### Помилка прав доступу
```bash
# Виправити права доступу
sudo chown -R 999:999 data/postgres/
sudo chmod -R 700 data/postgres/
```

### Backup не створюється
```bash
# Перевірити статус PostgreSQL
docker compose ps postgres

# Перевірити логи
docker compose logs postgres
```

### Відновлення не працює
```bash
# Перевірити синтаксис backup файлу
head -10 backup.sql

# Спробувати часткове відновлення
docker compose exec postgres psql -U kvitkova_user -d kvitkova_crm -c "SELECT version();"
``` 