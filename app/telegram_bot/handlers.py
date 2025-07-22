# -*- coding: utf-8 -*-
"""
Telegram Bot Command Handlers for Kvitkova Povnya CRM
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes
from flask import current_app

from app.models.courier import Courier
from app.models.delivery import Delivery
from app.extensions import db
from .keyboards import CourierKeyboards
from .services import TelegramService

logger = logging.getLogger(__name__)


class CourierHandlers:
    """
    Handlers for courier bot commands and callbacks
    """
    
    def __init__(self, telegram_bot):
        self.bot = telegram_bot
        self.keyboards = CourierKeyboards()
        self.service = TelegramService()
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        # Check if courier is already registered
        courier = Courier.query.filter_by(telegram_chat_id=chat_id).first()
        
        if courier:
            # Update last activity
            courier.last_telegram_activity = datetime.utcnow()
            db.session.commit()
            
            await update.message.reply_text(
                f"🌸 Привіт, {courier.name}!\n\n"
                f"Ласкаво просимо назад до бота Квіткової Повні!\n"
                f"Оберіть дію з меню нижче:",
                reply_markup=self.keyboards.main_menu()
            )
        else:
            await update.message.reply_text(
                "🌸 Ласкаво просимо до Квіткової Повні!\n\n"
                "Цей бот допоможе вам управляти доставками.\n"
                "Для початку роботи вам потрібно зареєструватися.\n\n"
                "Використайте команду /register з вашим номером телефону:\n"
                "Приклад: /register +380501234567",
                reply_markup=self.keyboards.back_to_main()
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🌸 **ДОВІДКА ПО БОТУ КВІТКОВОЇ ПОВНІ**

**📱 Основні команди:**
/start - Почати роботу з ботом
/help - Показати цю довідку
/register - Зареєструватися в системі
/profile - Переглянути мій профіль
/deliveries - Показати всі доставки
/today - Доставки на сьогодні
/tomorrow - Доставки на завтра
/week - Доставки на тиждень

**🚚 Робота з доставками:**
• Перегляд списку доставок
• Відмітка про виконання
• Повідомлення про проблеми
• Перегляд деталей замовлення

**⚙️ Налаштування:**
• Увімкнення/вимкнення сповіщень
• Оновлення профілю

**❓ Потрібна допомога?**
Зверніться до адміністратора системи.
        """
        
        await update.message.reply_text(
            help_text,
            parse_mode='Markdown',
            reply_markup=self.keyboards.back_to_main()
        )
    
    async def register_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /register command with strict validation"""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        # Check if already registered
        existing_courier = Courier.query.filter_by(telegram_chat_id=chat_id).first()
        if existing_courier:
            if existing_courier.active:
                await update.message.reply_text(
                    f"✅ Ви вже зареєстровані як {existing_courier.name}",
                    reply_markup=self.keyboards.main_menu()
                )
            else:
                await update.message.reply_text(
                    "❌ Ваш акаунт кур'єра деактивований.\n"
                    "Зверніться до адміністратора для активації акаунту."
                )
            return
        
        # Get phone number from command arguments
        if not context.args:
            await update.message.reply_text(
                "❌ Необхідно вказати номер телефону.\n\n"
                "📝 **Використання:** `/register +380501234567`\n\n"
                "⚠️ **Важливо:**\n"
                "• Спочатку адміністратор повинен створити ваш акаунт в CRM системі\n"
                "• Використовуйте точно той номер, який вказаний в системі\n"
                "• Акаунт повинен бути активним\n\n"
                "💡 Якщо у вас немає доступу - зверніться до адміністратора.",
                parse_mode='Markdown'
            )
            return
        
        phone = context.args[0].strip()
        
        # Validate phone format
        if not phone.startswith('+380') or len(phone) != 13:
            await update.message.reply_text(
                "❌ Неправильний формат номера телефону.\n\n"
                "📱 **Правильний формат:** +380XXXXXXXXX\n"
                "📱 **Приклад:** +380501234567\n\n"
                "Спробуйте ще раз з правильним форматом."
            )
            return
        
        # Find courier by phone
        courier = Courier.query.filter_by(phone=phone).first()
        
        if not courier:
            await update.message.reply_text(
                "❌ **Кур'єра з таким номером не знайдено в системі.**\n\n"
                "🔍 **Можливі причини:**\n"
                "• Номер введено неправильно\n"
                "• Адміністратор ще не створив ваш акаунт\n"
                "• Номер не відповідає тому, що в системі\n\n"
                "📞 **Зверніться до адміністратора:**\n"
                "• Для створення акаунту кур'єра\n"
                "• Для перевірки правильності номера\n\n"
                "💡 Після створення акаунту спробуйте реєстрацію знову.",
                parse_mode='Markdown'
            )
            return
        
        # Check if courier account is active
        if not courier.active:
            await update.message.reply_text(
                "❌ **Ваш акаунт кур'єра деактивований.**\n\n"
                "⚠️ **Причини деактивації:**\n"
                "• Тимчасове призупинення роботи\n"
                "• Адміністративне рішення\n"
                "• Технічні причини\n\n"
                "📞 **Зверніться до адміністратора для:**\n"
                "• З'ясування причини деактивації\n"
                "• Активації акаунту\n"
                "• Відновлення доступу\n\n"
                "✅ Після активації ви зможете користуватися ботом.",
                parse_mode='Markdown'
            )
            return
        
        # Check if courier already has telegram linked to different account
        if courier.telegram_chat_id and courier.telegram_chat_id != chat_id:
            await update.message.reply_text(
                "❌ **Цей акаунт кур'єра вже прив'язаний до іншого Telegram.**\n\n"
                "🔒 **З міркувань безпеки:**\n"
                "• Один акаунт кур'єра = один Telegram\n"
                "• Неможливо використовувати з кількох пристроїв\n\n"
                "🛠️ **Для вирішення проблеми:**\n"
                "• Зверніться до адміністратора\n"
                "• Повідомте ваш номер телефону\n"
                "• Адміністратор зможе скинути прив'язку\n\n"
                "⚡ Після скидання спробуйте реєстрацію знову.",
                parse_mode='Markdown'
            )
            return
        
        # Register courier successfully
        courier.telegram_chat_id = chat_id
        courier.telegram_username = user.username if user.username else None
        courier.telegram_registered = True
        courier.last_telegram_activity = datetime.utcnow()
        db.session.commit()
        
        # Success message with onboarding info
        await update.message.reply_text(
            f"🎉 **Вітаємо, {courier.name}!**\n\n"
            f"✅ Ви успішно зареєстровані в боті **Квіткової Повні**\n\n"
            f"👤 **Ваші дані:**\n"
            f"• Ім'я: {courier.name}\n"
            f"• Телефон: {courier.phone}\n"
            f"• Рейт: {courier.delivery_rate}₴ за доставку\n\n"
            f"🔔 **Тепер ви будете отримувати:**\n"
            f"• Сповіщення про нові доставки\n"
            f"• Оновлення статусів замовлень\n"
            f"• Важливі повідомлення від адміністрації\n\n"
            f"💡 **Оберіть дію з меню нижче:**",
            reply_markup=self.keyboards.main_menu(),
            parse_mode='Markdown'
        )
        
        logger.info(f"Courier {courier.name} (ID: {courier.id}) successfully registered with Telegram chat_id {chat_id}")
    
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /profile command"""
        chat_id = update.effective_chat.id
        courier = await self._get_registered_courier(update, chat_id)
        if not courier:
            return
        
        # Get courier statistics
        total_deliveries = len(courier.deliveries)
        completed_deliveries = len([d for d in courier.deliveries if d.status == 'Доставлено'])
        pending_deliveries = len([d for d in courier.deliveries if d.status == 'Очікує'])
        
        # Today's deliveries
        today = datetime.now().date()
        today_deliveries = len([d for d in courier.deliveries if d.delivery_date == today and d.status != 'Скасовано'])
        
        profile_text = f"""
👤 **Профіль кур'єра**

**Особисті дані:**
• Ім'я: {courier.name}
• Телефон: {courier.phone}
• Статус: {'🟢 Активний' if courier.active else '🔴 Неактивний'}
• Рейт за доставку: {courier.delivery_rate}₴

**Статистика:**
• Всього доставок: {total_deliveries}
• Доставлено: {completed_deliveries}
• Очікує: {pending_deliveries}
• Сьогодні: {today_deliveries}

**Telegram налаштування:**
• Сповіщення: {'🔔 Увімкнені' if courier.telegram_notifications_enabled else '🔕 Вимкнені'}
• Username: @{courier.telegram_username or 'не вказано'}
• Остання активність: {courier.last_telegram_activity.strftime('%d.%m.%Y %H:%M') if courier.last_telegram_activity else 'невідома'}
        """
        
        await update.message.reply_text(
            profile_text,
            parse_mode='Markdown',
            reply_markup=self.keyboards.back_to_main()
        )
    
    async def deliveries_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /deliveries command"""
        chat_id = update.effective_chat.id
        courier = await self._get_registered_courier(update, chat_id)
        if not courier:
            return
        
        await self._show_deliveries_list(update, courier, "all")
    
    async def today_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /today command"""
        chat_id = update.effective_chat.id
        courier = await self._get_registered_courier(update, chat_id)
        if not courier:
            return
        
        await self._show_deliveries_list(update, courier, "today")
    
    async def tomorrow_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /tomorrow command"""
        chat_id = update.effective_chat.id
        courier = await self._get_registered_courier(update, chat_id)
        if not courier:
            return
        
        await self._show_deliveries_list(update, courier, "tomorrow")
    
    async def week_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /week command"""
        chat_id = update.effective_chat.id
        courier = await self._get_registered_courier(update, chat_id)
        if not courier:
            return
        
        await self._show_deliveries_list(update, courier, "week")
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards"""
        query = update.callback_query
        await query.answer()
        
        chat_id = query.message.chat_id
        courier = await self._get_registered_courier(update, chat_id, query=query)
        if not courier:
            return
        
        data = query.data
        
        # Route callback to appropriate handler
        if data == "main_menu":
            await self._show_main_menu(query, courier)
        elif data.startswith("deliveries_"):
            await self._handle_deliveries_callback(query, courier, data)
        elif data.startswith("delivery_"):
            await self._handle_delivery_action(query, courier, data)
        elif data.startswith("confirm_"):
            await self._handle_confirmation(query, courier, data)
        elif data.startswith("problem_"):
            await self._handle_problem_report(query, courier, data)
        else:
            await query.edit_message_text("❌ Невідома команда")
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular text messages"""
        chat_id = update.effective_chat.id
        courier = await self._get_registered_courier(update, chat_id)
        if not courier:
            return
        
        # Update last activity
        courier.last_telegram_activity = datetime.utcnow()
        db.session.commit()
        
        # For now, just show the main menu
        await update.message.reply_text(
            "💬 Для роботи з ботом використовуйте кнопки меню або команди.",
            reply_markup=self.keyboards.main_menu()
        )
    
    # === Helper Methods ===
    
    async def _get_registered_courier(self, update: Update, chat_id: int, query=None) -> Optional[Courier]:
        """Get registered courier or show registration message"""
        courier = Courier.query.filter_by(telegram_chat_id=chat_id).first()
        
        if not courier:
            message_text = ("❌ Ви не зареєстровані в системі.\n"
                          "Використайте команду /register для реєстрації.")
            
            if query:
                await query.edit_message_text(message_text)
            else:
                await update.message.reply_text(message_text)
            return None
        
        if not courier.active:
            message_text = ("❌ Ваш акаунт кур'єра неактивний.\n"
                          "Зверніться до адміністратора.")
            
            if query:
                await query.edit_message_text(message_text)
            else:
                await update.message.reply_text(message_text)
            return None
        
        return courier
    
    async def _show_main_menu(self, query, courier: Courier):
        """Show main menu"""
        await query.edit_message_text(
            f"🌸 Головне меню - {courier.name}\n\n"
            f"Оберіть дію:",
            reply_markup=self.keyboards.main_menu()
        )
    
    async def _show_deliveries_list(self, update, courier: Courier, period: str):
        """Show list of deliveries for specified period"""
        today = datetime.now().date()
        
        # Filter deliveries by period
        if period == "today":
            deliveries = [d for d in courier.deliveries if d.delivery_date == today and d.status != 'Скасовано']
            title = f"📦 Доставки на сьогодні ({today.strftime('%d.%m.%Y')})"
        elif period == "tomorrow":
            tomorrow = today + timedelta(days=1)
            deliveries = [d for d in courier.deliveries if d.delivery_date == tomorrow and d.status != 'Скасовано']
            title = f"📅 Доставки на завтра ({tomorrow.strftime('%d.%m.%Y')})"
        elif period == "week":
            week_end = today + timedelta(days=7)
            deliveries = [d for d in courier.deliveries 
                         if today <= d.delivery_date <= week_end and d.status != 'Скасовано']
            title = f"📅 Доставки на тиждень ({today.strftime('%d.%m')} - {week_end.strftime('%d.%m')})"
        else:  # all
            deliveries = [d for d in courier.deliveries if d.status != 'Скасовано']
            title = "📋 Всі доставки"
        
        if not deliveries:
            await update.message.reply_text(
                f"{title}\n\n"
                f"🎉 Доставок немає!",
                reply_markup=self.keyboards.back_to_main()
            )
            return
        
        # Sort by date and status
        deliveries.sort(key=lambda x: (x.delivery_date, x.status != 'Очікує'))
        
        # Format deliveries list
        text = f"{title}\n\n"
        for i, delivery in enumerate(deliveries[:10], 1):  # Show first 10
            status_emoji = "⏳" if delivery.status == "Очікує" else "✅"
            address = f"{delivery.street} {delivery.building_number}" if delivery.street else "Самовивіз"
            
            text += f"{status_emoji} **{i}. {delivery.delivery_date.strftime('%d.%m')}**\n"
            text += f"   📍 {address}\n"
            text += f"   🕐 {delivery.time_from}-{delivery.time_to}\n"
            text += f"   📞 {delivery.phone}\n\n"
        
        if len(deliveries) > 10:
            text += f"... та ще {len(deliveries) - 10} доставок\n\n"
        
        text += "💡 *Для детального перегляду використовуйте кнопки нижче*"
        
        await update.message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=self.keyboards.back_to_main()
        )
    
    async def _handle_deliveries_callback(self, query, courier: Courier, data: str):
        """Handle deliveries-related callbacks"""
        if data == "deliveries_today":
            await self._show_deliveries_for_callback(query, courier, "today")
        elif data == "deliveries_tomorrow":
            await self._show_deliveries_for_callback(query, courier, "tomorrow")
        elif data == "deliveries_all":
            await self._show_deliveries_for_callback(query, courier, "all")
    
    async def _show_deliveries_for_callback(self, query, courier: Courier, period: str):
        """Show deliveries list for callback query"""
        # This is a simplified version - implement pagination if needed
        today = datetime.now().date()
        
        if period == "today":
            deliveries = [d for d in courier.deliveries if d.delivery_date == today and d.status != 'Скасовано']
            title = f"📦 Доставки на сьогодні"
        elif period == "tomorrow":
            tomorrow = today + timedelta(days=1)
            deliveries = [d for d in courier.deliveries if d.delivery_date == tomorrow and d.status != 'Скасовано']
            title = f"📅 Доставки на завтра"
        else:  # all
            deliveries = [d for d in courier.deliveries if d.status != 'Скасовано']
            title = "📋 Всі доставки"
        
        if not deliveries:
            await query.edit_message_text(
                f"{title}\n\n🎉 Доставок немає!",
                reply_markup=self.keyboards.back_to_main()
            )
            return
        
        # Show summary
        pending = len([d for d in deliveries if d.status == 'Очікує'])
        completed = len([d for d in deliveries if d.status == 'Доставлено'])
        
        text = f"{title}\n\n"
        text += f"📊 **Статистика:**\n"
        text += f"⏳ Очікує: {pending}\n"
        text += f"✅ Доставлено: {completed}\n"
        text += f"📦 Всього: {len(deliveries)}\n\n"
        text += "💡 Використовуйте команди для детального перегляду:"
        
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=self.keyboards.back_to_main()
        )
    
    async def _handle_delivery_action(self, query, courier: Courier, data: str):
        """Handle delivery action callbacks"""
        
        try:
            if data.startswith("delivery_complete_"):
                delivery_id = int(data.split("_")[-1])
                await self._handle_delivery_completion_request(query, courier, delivery_id)
            
            elif data.startswith("delivery_problem_"):
                delivery_id = int(data.split("_")[-1])
                await self._handle_delivery_problem_request(query, courier, delivery_id)
            
            elif data.startswith("delivery_call_"):
                delivery_id = int(data.split("_")[-1])
                await self._handle_delivery_call_request(query, courier, delivery_id)
            
            elif data.startswith("delivery_location_"):
                delivery_id = int(data.split("_")[-1])
                await self._handle_delivery_location_request(query, courier, delivery_id)
            
            elif data.startswith("delivery_back_"):
                delivery_id = int(data.split("_")[-1])
                await self._show_delivery_details(query, courier, delivery_id)
            
            else:
                await query.edit_message_text(
                    "❌ Невідома дія з доставкою",
                    reply_markup=self.keyboards.back_to_main()
                )
                
        except (ValueError, IndexError):
            await query.edit_message_text(
                "❌ Помилка в ідентифікаторі доставки",
                reply_markup=self.keyboards.back_to_main()
            )
        except Exception as e:
            logger.error(f"Error handling delivery action {data}: {e}")
            await query.edit_message_text(
                "❌ Помилка обробки дії",
                reply_markup=self.keyboards.back_to_main()
            )
    
    async def _handle_confirmation(self, query, courier: Courier, data: str):
        """Handle confirmation callbacks"""
        
        try:
            if data.startswith("confirm_complete_"):
                delivery_id = int(data.split("_")[-1])
                await self._confirm_delivery_completion(query, courier, delivery_id)
            
            elif data.startswith("cancel_complete_"):
                delivery_id = int(data.split("_")[-1])
                await self._cancel_delivery_completion(query, courier, delivery_id)
            
            else:
                await query.edit_message_text(
                    "❌ Невідома команда підтвердження",
                    reply_markup=self.keyboards.back_to_main()
                )
                
        except Exception as e:
            logger.error(f"Error handling confirmation {data}: {e}")
            await query.edit_message_text(
                "❌ Помилка обробки підтвердження",
                reply_markup=self.keyboards.back_to_main()
            )
    
    async def _handle_problem_report(self, query, courier: Courier, data: str):
        """Handle problem report callbacks"""
        # Implementation for problem reports
        await query.edit_message_text(
            "🚧 Функція в розробці",
            reply_markup=self.keyboards.back_to_main()
        )
    
    # === Delivery Action Handlers ===
    
    async def _handle_delivery_completion_request(self, query, courier: Courier, delivery_id: int):
        """Handle request to complete delivery"""
        
        delivery = Delivery.query.filter_by(id=delivery_id, courier_id=courier.id).first()
        
        if not delivery:
            await query.edit_message_text(
                "❌ Доставку не знайдено або вона не призначена вам",
                reply_markup=self.keyboards.back_to_main()
            )
            return
        
        if delivery.status == 'Доставлено':
            await query.edit_message_text(
                "✅ Ця доставка вже відмічена як виконана",
                reply_markup=self.keyboards.back_to_main()
            )
            return
        
        # Показуємо підтвердження
        confirmation_text = (
            f"📦 **Доставка #{delivery.id}**\n\n"
            f"👤 {delivery.order.recipient_name if delivery.order else 'Не вказано'}\n"
            f"📞 {delivery.order.recipient_phone if delivery.order else delivery.phone}\n\n"
            f"❓ **Підтвердіть завершення доставки**\n"
            f"Після підтвердження статус зміниться на \"Доставлено\""
        )
        
        await query.edit_message_text(
            confirmation_text,
            reply_markup=self.keyboards.confirm_delivery_completion(delivery_id),
            parse_mode='Markdown'
        )
    
    async def _confirm_delivery_completion(self, query, courier: Courier, delivery_id: int):
        """Confirm and complete delivery"""
        
        delivery = Delivery.query.filter_by(id=delivery_id, courier_id=courier.id).first()
        
        if not delivery:
            await query.edit_message_text(
                "❌ Доставку не знайдено",
                reply_markup=self.keyboards.back_to_main()
            )
            return
        
        try:
            # Оновлюємо статус доставки
            delivery.status = 'Доставлено'
            delivery.delivered_at = datetime.utcnow()
            delivery.status_changed_at = datetime.utcnow()
            
            # Оновлюємо статистику кур'єра
            courier.deliveries_count = Delivery.query.filter_by(
                courier_id=courier.id, 
                status='Доставлено'
            ).count()
            
            db.session.commit()
            
            # Повідомлення про успіх
            success_text = (
                f"✅ **Доставка #{delivery.id} завершена!**\n\n"
                f"🎉 Дякуємо за роботу!\n"
                f"📊 Ваша статистика оновлена\n\n"
                f"💰 Нарахування: {courier.delivery_rate}₴"
            )
            
            await query.edit_message_text(
                success_text,
                reply_markup=self.keyboards.back_to_main(),
                parse_mode='Markdown'
            )
            
            logger.info(f"Delivery #{delivery_id} completed by courier {courier.name} (ID: {courier.id})")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error completing delivery #{delivery_id}: {e}")
            
            await query.edit_message_text(
                "❌ Помилка при завершенні доставки. Спробуйте пізніше.",
                reply_markup=self.keyboards.back_to_main()
            )
    
    async def _cancel_delivery_completion(self, query, courier: Courier, delivery_id: int):
        """Cancel delivery completion and return to delivery details"""
        
        # Повертаємося до деталей доставки замість просто повідомлення
        await self._show_delivery_details(query, courier, delivery_id)
    
    async def _show_delivery_details(self, query, courier: Courier, delivery_id: int):
        """Show detailed delivery information"""
        
        delivery = Delivery.query.filter_by(id=delivery_id, courier_id=courier.id).first()
        
        if not delivery:
            await query.edit_message_text(
                "❌ Доставку не знайдено або вона не призначена вам",
                reply_markup=self.keyboards.back_to_main()
            )
            return
        
        # Використовуємо сервіс для форматування інформації
        delivery_info = self.telegram_service.format_delivery_info(delivery, detailed=True)
        
        await query.edit_message_text(
            delivery_info,
            reply_markup=self.keyboards.delivery_actions(delivery_id),
            parse_mode='Markdown'
        )
    
    async def _handle_delivery_call_request(self, query, courier: Courier, delivery_id: int):
        """Handle call button press"""
        
        delivery = Delivery.query.filter_by(id=delivery_id, courier_id=courier.id).first()
        
        if not delivery:
            await query.edit_message_text(
                "❌ Доставку не знайдено",
                reply_markup=self.keyboards.back_to_main()
            )
            return
        
        phone = delivery.order.recipient_phone if delivery.order else delivery.phone
        
        call_text = (
            f"📞 **Зателефонувати клієнту**\n\n"
            f"👤 {delivery.order.recipient_name if delivery.order else 'Не вказано'}\n"
            f"📞 **{phone}**\n\n"
            f"💡 Натисніть на номер щоб зателефонувати"
        )
        
        await query.edit_message_text(
            call_text,
            reply_markup=self.keyboards.delivery_actions(delivery_id),
            parse_mode='Markdown'
        )
    
    async def _handle_delivery_location_request(self, query, courier: Courier, delivery_id: int):
        """Handle location button press"""
        
        delivery = Delivery.query.filter_by(id=delivery_id, courier_id=courier.id).first()
        
        if not delivery:
            await query.edit_message_text(
                "❌ Доставку не знайдено",
                reply_markup=self.keyboards.back_to_main()
            )
            return
        
        if delivery.is_pickup:
            location_text = "📍 **Самовивіз - адреса магазину**\n\nКлієнт забирає букет самостійно"
        else:
            address_parts = []
            if delivery.order and delivery.order.city:
                address_parts.append(delivery.order.city)
            if delivery.street:
                address_parts.append(delivery.street)
            if delivery.building_number:
                address_parts.append(delivery.building_number)
            
            address = ", ".join(address_parts)
            
            location_text = f"📍 **Адреса доставки**\n\n{address}"
            
            if delivery.floor:
                location_text += f"\n🏢 Поверх: {delivery.floor}"
            if delivery.entrance:
                location_text += f"\n🚪 Під'їзд: {delivery.entrance}"
        
        await query.edit_message_text(
            location_text,
            reply_markup=self.keyboards.delivery_actions(delivery_id),
            parse_mode='Markdown'
        )
    
    async def _handle_delivery_problem_request(self, query, courier: Courier, delivery_id: int):
        """Handle problem report request"""
        
        delivery = Delivery.query.filter_by(id=delivery_id, courier_id=courier.id).first()
        
        if not delivery:
            await query.edit_message_text(
                "❌ Доставку не знайдено",
                reply_markup=self.keyboards.back_to_main()
            )
            return
        
        problem_text = (
            f"❌ **Проблема з доставкою #{delivery.id}**\n\n"
            f"Оберіть тип проблеми:"
        )
        
        await query.edit_message_text(
            problem_text,
            reply_markup=self.keyboards.problem_types(delivery_id),
            parse_mode='Markdown'
        ) 