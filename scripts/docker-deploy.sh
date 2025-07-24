#!/bin/bash

# Скрипт для розгортання CRM з Telegram ботом в Docker

set -e

# Парсинг аргументів
CREATE_MIGRATION=""
MIGRATION_MESSAGE=""
FORCE_MIGRATIONS=false
SKIP_MIGRATIONS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --create-migration)
            CREATE_MIGRATION=true
            MIGRATION_MESSAGE="$2"
            shift 2
            ;;
        --force-migrations)
            FORCE_MIGRATIONS=true
            shift
            ;;
        --skip-migrations)
            SKIP_MIGRATIONS=true
            shift
            ;;
        --help)
            echo "Використання: $0 [опції]"
            echo "Опції:"
            echo "  --create-migration 'повідомлення'  Створити нову міграцію з повідомленням"
            echo "  --force-migrations                Примусово виконати міграції"
            echo "  --skip-migrations                 Пропустити міграції"
            echo "  --help                           Показати цю довідку"
            exit 0
            ;;
        *)
            echo "Невідома опція: $1"
            echo "Використайте --help для довідки"
            exit 1
            ;;
    esac
done

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

# Функція для створення міграцій
create_migration() {
    local message="$1"
    echo "📝 Створення міграції: $message"
    
    if $DOCKER_COMPOSE exec -T web python3 -m flask db migrate -m "$message" 2>/dev/null; then
        echo "✅ Міграція створена успішно"
        return 0
    else
        echo "⚠️  Не вдалося створити міграцію автоматично"
        echo "📝 Створіть міграцію вручну:"
        echo "   $DOCKER_COMPOSE exec web python3 -m flask db migrate -m \"$message\""
        return 1
    fi
}

# Функція для перевірки, чи потрібні міграції
check_migrations_needed() {
    echo "🔍 Перевірка необхідності міграцій..."
    
    # Створюємо тимчасовий скрипт для перевірки
    cat > /tmp/check_migrations.py << 'EOF'
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/app')

try:
    from app import create_app
    from flask_migrate import current
    
    app = create_app()
    with app.app_context():
        try:
            current_revision = current()
            print(f"CURRENT_REVISION:{current_revision}")
        except Exception as e:
            print(f"ERROR:{str(e)}")
            sys.exit(1)
except Exception as e:
    print(f"ERROR:{str(e)}")
    sys.exit(1)
EOF

    local result
    result=$($DOCKER_COMPOSE exec -T web python3 /tmp/check_migrations.py 2>/dev/null || echo "ERROR:Failed to check migrations")
    
    if [[ $result == ERROR* ]]; then
        echo "⚠️  Не вдалося перевірити міграції: ${result#ERROR:}"
        return 1
    fi
    
    local current_revision
    current_revision=$(echo "$result" | grep "CURRENT_REVISION:" | cut -d: -f2)
    
    if [[ -z "$current_revision" ]]; then
        echo "✅ База даних порожня, міграції не потрібні"
        return 0
    fi
    
    echo "📊 Поточна ревізія: $current_revision"
    return 0
}

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

# Очікування готовності PostgreSQL
echo "⏳ Очікування готовності PostgreSQL..."
sleep 15

# Очікування готовності веб сервера
echo "⏳ Очікування готовності веб сервера..."
sleep 10

# Виконання міграцій бази даних
if [ "$SKIP_MIGRATIONS" = true ]; then
    echo "⏭️  Пропуск міграцій (--skip-migrations)"
elif [ "$FORCE_MIGRATIONS" = true ]; then
    echo "🗄️  Примусове виконання міграцій..."
    if $DOCKER_COMPOSE exec -T web python3 -m flask db upgrade 2>/dev/null; then
        echo "✅ Міграції успішно виконано"
    else
        echo "⚠️  Помилка виконання міграцій"
    fi
else
    echo "🗄️  Перевірка та виконання міграцій бази даних..."
    
    # Перевіряємо, чи потрібні міграції
    if check_migrations_needed; then
        echo "🔄 Виконання міграцій..."
        if $DOCKER_COMPOSE exec -T web python3 -m flask db upgrade 2>/dev/null; then
            echo "✅ Міграції успішно виконано"
        else
            echo "⚠️  Помилка виконання міграцій через Flask CLI"
            echo "🔄 Спробуємо альтернативний спосіб..."
            
            # Альтернативний спосіб - через Python скрипт
            cat > /tmp/run_migrations.py << 'EOF'
#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '/app')

try:
    from app import create_app
    from app.extensions import db
    from flask_migrate import upgrade
    
    app = create_app()
    with app.app_context():
        upgrade()
        print("✅ Міграції успішно виконано")
except Exception as e:
    print(f"❌ Помилка виконання міграцій: {e}")
    sys.exit(1)
EOF

            if $DOCKER_COMPOSE exec -T web python3 /tmp/run_migrations.py; then
                echo "✅ Міграції виконано через Python скрипт"
            else
                echo "⚠️  Не вдалося виконати міграції автоматично"
                echo "📝 Можливо, потрібно виконати міграції вручну:"
                echo "   $DOCKER_COMPOSE exec web python3 -m flask db upgrade"
            fi
        fi
    else
        echo "✅ Міграції не потрібні або перевірка не вдалася"
    fi
fi

# Створення міграції, якщо потрібно
if [ "$CREATE_MIGRATION" = true ]; then
    if [ -z "$MIGRATION_MESSAGE" ]; then
        echo "❌ Помилка: не вказано повідомлення для міграції"
        echo "📝 Використайте: $0 --create-migration 'ваше повідомлення'"
        exit 1
    fi
    
    echo "📝 Створення міграції: $MIGRATION_MESSAGE"
    if create_migration "$MIGRATION_MESSAGE"; then
        echo "✅ Міграція створена успішно"
        echo "🔄 Застосування нової міграції..."
        if $DOCKER_COMPOSE exec -T web python3 -m flask db upgrade 2>/dev/null; then
            echo "✅ Нова міграція застосована"
        else
            echo "⚠️  Не вдалося застосувати нову міграцію автоматично"
        fi
    else
        echo "❌ Не вдалося створити міграцію"
    fi
fi

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
echo "   $0 --create-migration 'msg'      - Створити нову міграцію"
echo "   $DOCKER_COMPOSE exec web flask db upgrade - Застосувати міграції"
echo "   $DOCKER_COMPOSE exec web flask db migrate -m 'msg' - Створити міграцію"
echo
echo "🌐 Веб інтерфейс: http://localhost:8000"
echo "🤖 Telegram бот працює в фоновому режимі" 