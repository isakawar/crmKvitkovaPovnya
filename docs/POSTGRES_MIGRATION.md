# Міграція на PostgreSQL

Цей документ описує процес міграції CRM системи з SQLite на PostgreSQL.

## Зміни

### 1. Нова архітектура
- **PostgreSQL** як основна база даних
- **Окремий контейнер** для бази даних
- **Розумні міграції** - виконуються тільки за потреби

### 2. Оновлені файли
- `docker-compose.yml` - додано PostgreSQL сервіс
- `requirements.txt` - додано `psycopg2-binary`
- `app/config.py` - підтримка PostgreSQL URL
- `scripts/docker-deploy.sh` - розумні міграції
- `scripts/migrate_sqlite_to_postgres.py` - міграція даних

### 3. Нові змінні середовища
```bash
DATABASE_URL=postgresql://kvitkova_user:kvitkova_password@postgres:5432/kvitkova_crm
POSTGRES_PASSWORD=kvitkova_password
```

## Використання

### Перший запуск
```bash
# Клонування та перехід на гілку
git checkout feature/postgres-migration

# Копіювання .env файлу
cp env.example .env

# Редагування .env (встановити TELEGRAM_BOT_TOKEN та POSTGRES_PASSWORD)

# Запуск
./scripts/docker-deploy.sh
```

### Міграція існуючих даних
```bash
# Якщо у вас є дані в SQLite
python3 scripts/migrate_sqlite_to_postgres.py
```

### Розумні міграції
```bash
# Звичайний запуск (міграції тільки за потреби)
./scripts/docker-deploy.sh

# Примусове виконання міграцій
./scripts/docker-deploy.sh --force-migrations

# Пропуск міграцій
./scripts/docker-deploy.sh --skip-migrations

# Створення нової міграції
./scripts/docker-deploy.sh --create-migration "Add new field"
```

## Переваги PostgreSQL

1. **Масштабованість** - краща продуктивність при великих обсягах даних
2. **Надійність** - ACID транзакції, резервне копіювання
3. **Розширені можливості** - JSON поля, повнотекстовий пошук
4. **Паралельні запити** - краща продуктивність при одночасних запитах
5. **Індекси** - більше типів індексів для оптимізації

## Структура бази даних

PostgreSQL версія використовує ті самі моделі, що й SQLite, але з кращою продуктивністю та надійністю.

## Моніторинг

```bash
# Перегляд логів PostgreSQL
docker-compose logs postgres

# Підключення до бази даних
docker-compose exec postgres psql -U kvitkova_user -d kvitkova_crm

# Перегляд статистики
docker-compose exec postgres psql -U kvitkova_user -d kvitkova_crm -c "SELECT version();"
```

## Резервне копіювання

```bash
# Створення резервної копії
docker-compose exec postgres pg_dump -U kvitkova_user kvitkova_crm > backup.sql

# Відновлення з резервної копії
docker-compose exec -T postgres psql -U kvitkova_user kvitkova_crm < backup.sql
``` 