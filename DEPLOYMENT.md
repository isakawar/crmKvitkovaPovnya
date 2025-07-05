# Інструкції для розгортання CRM системи

## Розгортання з Docker

### 1. Збірка та запуск контейнера

```bash
# Збірка образу
docker build -t kvitkova-crm .

# Запуск контейнера
docker run -d \
  --name kvitkova-crm \
  -p 8000:8000 \
  -v $(pwd)/instance:/app/instance \
  kvitkova-crm
```

### 2. Використання docker-compose

```bash
# Запуск
docker-compose up -d

# Перегляд логів
docker-compose logs -f

# Зупинка
docker-compose down
```

## Що відбувається при запуску контейнера

1. **Перевірка структури проекту** - виводиться список файлів
2. **Виконання міграцій БД** - `flask db upgrade`
3. **Заповнення налаштувань** - `python3 app/scripts/seed_settings.py`
   - Додаються міста (Київ, Полтава, Вишгород, Бровари, Буча)
   - Типи доставки (Weekly, Monthly, Bi-weekly, One-Time)
   - Розміри (M, L, XL, XXL)
   - Категорії "Для кого" (дівчина собі, хлопець дівчині, тощо)
   - Джерела маркетингу (Таргет, Тікток, Контент інстаграм, тощо)
4. **Запуск веб-сервера** - Gunicorn на порту 8000

## Доступ до додатку

Після запуску контейнера додаток буде доступний за адресою:
- **Локально**: http://localhost:8000
- **На сервері**: http://your-server-ip:8000

## Структура даних

Всі налаштування зберігаються в таблиці `settings` з полями:
- `type` - тип налаштування (city, delivery_type, size, for_whom, marketing_source)
- `value` - значення налаштування

## Логування

Логи контейнера можна переглянути командою:
```bash
docker logs kvitkova-crm
```

## Оновлення

Для оновлення додатку:
```bash
# Зупинити контейнер
docker-compose down

# Перебудувати образ
docker-compose build

# Запустити знову
docker-compose up -d
```

## Резервне копіювання

База даних зберігається в томі `./instance:/app/instance`. Для резервного копіювання:
```bash
# Створити резервну копію
cp -r instance instance_backup_$(date +%Y%m%d)

# Відновити з резервної копії
cp -r instance_backup_20250101 instance
``` 