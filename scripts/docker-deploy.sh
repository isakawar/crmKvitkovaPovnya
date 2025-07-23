#!/bin/bash

# Скрипт для розгортання CRM з Telegram ботом в Docker

set -e

echo "🌸 === РОЗГОРТАННЯ КВІТКОВОЇ ПОВНІ В DOCKER === 🌸"
echo

# Перевірка наявності .env файлу
if [ ! -f .env ]; then
    echo "❌ Файл .env не знайдено!"
    echo "📝 Створіть файл .env з наступною змінною:"
    echo "   TELEGRAM_BOT_TOKEN=your-bot-token-here"
    echo
    exit 1
fi

# Перевірка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не встановлено!"
    exit 1
fi

# Перевірка Docker Compose (новий або старий синтаксис)
DOCKER_COMPOSE="docker compose"
if ! docker compose version &> /dev/null; then
    if command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE="docker-compose"
    else
        echo "❌ Docker Compose не встановлено!"
        echo "📝 Встановіть Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi
fi

echo "✅ Docker та Docker Compose знайдені ($DOCKER_COMPOSE)"
echo

# Зупинення старих контейнерів
echo "🛑 Зупинення існуючих контейнерів..."
$DOCKER_COMPOSE down

# Збірка образів
echo "🔨 Збірка Docker образів..."
$DOCKER_COMPOSE build

# Запуск сервісів
echo "🚀 Запуск сервісів..."
$DOCKER_COMPOSE up -d

echo
echo "✅ Розгортання завершено!"
echo
echo "📊 Стан сервісів:"
$DOCKER_COMPOSE ps

echo
echo "📝 Корисні команди:"
echo "   $DOCKER_COMPOSE logs web          - Логи веб сервера"
echo "   $DOCKER_COMPOSE logs telegram-bot - Логи Telegram бота"
echo "   $DOCKER_COMPOSE logs -f           - Всі логи в реальному часі"
echo "   $DOCKER_COMPOSE down              - Зупинити всі сервіси"
echo "   $DOCKER_COMPOSE restart           - Перезапустити сервіси"
echo
echo "🌐 Веб інтерфейс: http://localhost:8000"
echo "🤖 Telegram бот працює в фоновому режимі" 