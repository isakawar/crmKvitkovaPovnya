# 🔧 НАЛАШТУВАННЯ ЗМІННИХ ОТОЧЕННЯ

## 📝 Необхідні змінні для Telegram Bot

Створіть файл `.env` в корені проекту з наступними змінними:

```bash
# Flask Configuration
SECRET_KEY=your_secret_key_here
FLASK_ENV=development

# Database
DATABASE_URL=sqlite:///instance/kvitkova_crm.db

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/webhook/telegram
TELEGRAM_WEBHOOK_SECRET=your_webhook_secret_here
TELEGRAM_NOTIFICATIONS_ENABLED=true

# Development settings
DEBUG=true
```

## 🤖 Як отримати TELEGRAM_BOT_TOKEN:

1. Відкрийте Telegram
2. Знайдіть бота @BotFather
3. Напишіть команду `/newbot`
4. Дайте назву боту (наприклад: "Kvitkova Povnya Courier Bot")
5. Дайте username боту (наприклад: "kvitkova_courier_bot")
6. Скопіюйте отриманий токен в TELEGRAM_BOT_TOKEN

## 🚀 Запуск в Development режимі:

```bash
# Створіть .env файл з вашим токеном
export TELEGRAM_BOT_TOKEN="ваш_токен_тут"

# Запустіть додаток
python3 run.py
```

## 🔒 Безпека:

- ❌ НІКОЛИ не комітьте .env файл в git
- ✅ Додайте .env в .gitignore
- ✅ Використовуйте різні токени для dev/prod
- ✅ Регулярно ротуйте токени в продакшені 

## 🎯 **ЕТАП 2 ЗАВЕРШЕНО! ГОТОВИЙ ДО ТЕСТУВАННЯ!**

### ✅ **Що зроблено:**

1. **🗃️ Розширення моделей:**
   - Додано Telegram поля до `Courier` (chat_id, username, registered, notifications, last_activity)
   - Додано поля до `Delivery` (notification_sent, message_id)
   - Створено та застосовано міграцію

2. **🤖 Створення бота:**
   - Базовий клас `TelegramBot` з ініціалізацією
   - Inline клавіатури в `CourierKeyboards`
   - Повноцінні обробники команд в `CourierHandlers`
   - Бізнес-логіка в `TelegramService`

3. **🔗 Інтеграція:**
   - Підключено бот до Flask додатку
   - Створено тестовий скрипт
   - Готовий скрипт для запуску

### 🚀 **ГОТОВО ДО ТЕСТУВАННЯ!**

**Запустіть бота:**
```bash
python3 scripts/run_telegram_bot.py
```

**Протестуйте команди в Telegram:**
1. Знайдіть свого бота в Telegram
2. Напишіть `/start`
3. Спробуйте `/help`
4. Для реєстрації кур'єра: `/register +номер_телефону_існуючого_кур'єра`

### 🎯 **НАСТУПНИЙ ЕТАП 3:**
- Детальна робота з доставками
- Сповіщення про нові доставки
- Відмітки про виконання
- Інтеграція з CRM

**Готові тестувати бота? Запускайте і кажіть як працює!** 🎉 