# 🚀 Розгортання CRM на сервері з Docker та Telegram Bot

## 📋 Передумови

1. **Сервер з Ubuntu/Debian/CentOS**
2. **Docker та Docker Compose**
3. **Git** 
4. **Telegram Bot токен**

## 🔧 Крок 1: Підготовка сервера

### Встановлення Docker
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Перелогіньтесь або виконайте:
newgrp docker

# Встановлення Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Альтернативно (новий Docker Compose)
```bash
# Для нових версій Docker (включає compose plugin)
docker compose version
```

## 📦 Крок 2: Клонування проекту

```bash
# Клонування з GitHub
git clone https://github.com/isakawar/crmKvitkovaPovnya.git
cd crmKvitkovaPovnya

# Переключення на потрібну версію
git checkout v0.0.6

# Або на гілку з найновішими змінами
git checkout feature/telegram-bot-integration
```

## 🔑 Крок 3: Налаштування Telegram Bot

### 3.1 Створення Telegram Bot
1. Відкрийте [@BotFather](https://t.me/botfather) в Telegram
2. Виконайте команду `/newbot`
3. Дайте ім'я боту (наприклад: "Kvіtkova Povnya CRM Bot")
4. Дайте username боту (наприклад: "@kvitkova_crm_bot")
5. Скопіюйте отриманий токен

### 3.2 Створення .env файлу
```bash
# Створіть .env файл у корені проекту
cp env.example .env

# Відредагуйте файл
nano .env
```

**Вміст .env файлу:**
```env
TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ-abcdefg
```

⚠️ **Важливо:** Замініть значення на ваш реальний токен!

## 🚀 Крок 4: Розгортання

### Автоматичне розгортання (рекомендовано)
```bash
# Зробити скрипт виконуваним
chmod +x scripts/docker-deploy.sh

# Запустити розгортання
./scripts/docker-deploy.sh
```

### Ручне розгортання
```bash
# Зупинити існуючі контейнери (якщо є)
docker compose down

# Зібрати образи
docker compose build

# Запустити сервіси
docker compose up -d
```

## 📊 Крок 5: Перевірка стану

```bash
# Перевірити статус контейнерів
docker compose ps

# Подивитись логи
docker compose logs web
docker compose logs telegram-bot

# Логи в реальному часі
docker compose logs -f
```

**Очікуваний результат:**
```
NAME                            COMMAND                  SERVICE         STATUS          PORTS
crmkvitkovapovnya-telegram-bot-1   "python3 scripts/run…"   telegram-bot    running         
crmkvitkovapovnya-web-1            "/app/docker-entrypo…"   web             running         0.0.0.0:8000->8000/tcp
```

## 🌐 Крок 6: Доступ до додатку

- **Web інтерфейс:** `http://your-server-ip:8000`
- **Telegram Bot:** Відкрийте свого бота і надішліть `/start`

## 🔧 Налаштування Nginx (Опціонально)

Для продакшену рекомендується встановити Nginx:

```bash
# Встановлення Nginx
sudo apt update
sudo apt install nginx

# Створення конфігурації
sudo nano /etc/nginx/sites-available/crm
```

**Конфігурація Nginx:**
```nginx
server {
    listen 80;
    server_name your-domain.com;  # Замініть на ваш домен

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
# Активувати конфігурацію
sudo ln -s /etc/nginx/sites-available/crm /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 🔄 Управління сервісами

### Корисні команди
```bash
# Зупинити всі сервіси
docker compose down

# Перезапустити сервіси
docker compose restart

# Оновити з GitHub
git pull origin feature/telegram-bot-integration
docker compose build
docker compose up -d

# Переглянути логи конкретного сервісу
docker compose logs -f web
docker compose logs -f telegram-bot

# Виконати команди всередині контейнера
docker compose exec web bash
docker compose exec web python3 init_db.py

# Очистити та перестворити БД
docker compose exec web rm -f instance/kvitkova_crm.db
docker compose exec web python3 init_db.py
docker compose exec web python3 scripts/seed_settings.py
```

## 🛡️ Безпека

### Firewall налаштування
```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS (якщо використовуєте SSL)
sudo ufw allow 8000  # Тимчасово для тестування
sudo ufw enable
```

### SSL сертифікат (для продакшену)
```bash
# Встановлення Certbot
sudo apt install certbot python3-certbot-nginx

# Отримання SSL сертифіката
sudo certbot --nginx -d your-domain.com
```

## 📝 Моніторинг та логи

### Системні логи
```bash
# Логи Docker
sudo journalctl -u docker.service

# Логи Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Логи додатку
```bash
# Всі логи проекту
docker compose logs -f

# Окремо веб сервер
docker compose logs -f web

# Окремо Telegram бот
docker compose logs -f telegram-bot

# Останні 100 рядків
docker compose logs --tail=100 web
```

## 🆘 Усунення неполадок

### Проблема: "Port already in use"
```bash
# Знайти процес що використовує порт
sudo netstat -tulpn | grep :8000
sudo lsof -i :8000

# Зупинити процес
sudo kill -9 <PID>
```

### Проблема: "Telegram bot not responding"
```bash
# Перевірити логи бота
docker compose logs telegram-bot

# Перезапустити тільки бота
docker compose restart telegram-bot

# Перевірити токен
docker compose exec telegram-bot env | grep TELEGRAM
```

### Проблема: "Database locked"
```bash
# Перезапустити всі сервіси
docker compose down
docker compose up -d

# Або очистити БД
docker compose exec web rm -f instance/kvitkova_crm.db
docker compose exec web python3 init_db.py
```

## 📈 Масштабування

### Для високого навантаження
```yaml
# Додати до docker-compose.yml
version: '3.8'
services:
  web:
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
```

### Резервне копіювання
```bash
# Створити backup БД
docker compose exec web cp instance/kvitkova_crm.db instance/backup_$(date +%Y%m%d_%H%M%S).db

# Або скопіювати на хост
docker cp $(docker compose ps -q web):/app/instance/kvitkova_crm.db ./backup.db
```

---

## ✅ Checklist розгортання

- [ ] Docker та Docker Compose встановлені
- [ ] Telegram bot створений в @BotFather
- [ ] .env файл налаштований з токеном
- [ ] Проект склонований на сервер
- [ ] `docker compose up -d` виконано успішно
- [ ] Обидва контейнери (web + telegram-bot) працюють
- [ ] Web інтерфейс доступний по http://server-ip:8000
- [ ] Telegram bot відповідає на команду /start
- [ ] Firewall налаштований (порти 80, 443, 8000)
- [ ] Nginx налаштований (опціонально)
- [ ] SSL сертифікат встановлений (опціонально)

## 🎉 Готово!

Тепер ваша CRM система з Telegram ботом працює на сервері! 🚀

Для підтримки звертайтесь до документації або створюйте Issues в GitHub репозиторії. 