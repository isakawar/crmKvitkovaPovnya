# 🐳 Розгортання в Docker

Цей документ описує як розгорнути CRM Квіткова Повня з Telegram ботом в Docker контейнерах.

## 📋 Передумови

- [Docker](https://docs.docker.com/get-docker/) встановлений
- [Docker Compose](https://docs.docker.com/compose/install/) встановлений  
- Telegram Bot Token від [@BotFather](https://t.me/botfather)

## ⚙️ Налаштування

1. **Створіть файл `.env`** в корені проекту:
   ```bash
   cp env.example .env
   ```

2. **Додайте ваш Telegram Bot Token** до файлу `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789
   ```

## 🚀 Швидкий запуск

```bash
# Автоматичне розгортання
./scripts/docker-deploy.sh
```

## 📝 Ручний запуск

```bash
# Зупинити існуючі контейнери
docker-compose down

# Збірка образів
docker-compose build

# Запуск всіх сервісів
docker-compose up -d
```

## 🔍 Моніторинг

```bash
# Перевірка стану сервісів
docker-compose ps

# Логи веб сервера
docker-compose logs web

# Логи Telegram бота
docker-compose logs telegram-bot

# Всі логи в реальному часі
docker-compose logs -f
```

## 🏗️ Архітектура

Система складається з двох сервісів:

### 🌐 Web Service (`web`)
- **Порт:** 8000
- **Функції:** Веб інтерфейс CRM, API
- **База даних:** SQLite (збережена в `./instance/`)
- **Логи:** `./logs/`

### 🤖 Telegram Bot Service (`telegram-bot`)
- **Функції:** Обробка повідомлень від кур'єрів
- **Залежність:** Чекає готовності web сервісу
- **Логи:** `./logs/telegram_bot.log`

## 🛠️ Корисні команди

```bash
# Перезапуск всіх сервісів
docker-compose restart

# Перезапуск тільки Telegram бота
docker-compose restart telegram-bot

# Зупинка всіх сервісів
docker-compose down

# Зупинка з видаленням volumes
docker-compose down -v

# Видалення всіх контейнерів і образів
docker-compose down --rmi all

# Вхід в контейнер web
docker-compose exec web bash

# Вхід в контейнер telegram-bot
docker-compose exec telegram-bot bash
```

## 🔧 Налагодження

### Перевірка логів
```bash
# Якщо web сервіс не запускається
docker-compose logs web

# Якщо Telegram бот не працює
docker-compose logs telegram-bot
```

### Типові проблеми

1. **Telegram бот не запускається:**
   - Перевірте правильність `TELEGRAM_BOT_TOKEN` в `.env`
   - Перевірте що токен активний в [@BotFather](https://t.me/botfather)

2. **Web сервіс недоступний:**
   - Перевірте що порт 8000 не зайнятий
   - Перевірте логи: `docker-compose logs web`

3. **База даних не створюється:**
   - Перевірте права доступу до папки `./instance/`
   - Видаліть контейнери і спробуйте знову: `docker-compose down -v && docker-compose up -d`

## 🌐 Доступ

Після успішного запуску:
- **CRM інтерфейс:** http://localhost:8000
- **Telegram бот:** Працює автоматично, обробляє повідомлення кур'єрів

## 📊 Продакшн розгортання

Для продакшн використання:

1. Змініть `FLASK_ENV=production` в `docker-compose.yml`
2. Використайте зовнішню базу даних замість SQLite
3. Налаштуйте reverse proxy (nginx)
4. Додайте HTTPS сертифікати
5. Налаштуйте моніторинг та бекапи 