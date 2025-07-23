# -*- coding: utf-8 -*-
"""
Telegram Inline Keyboards for Kvitkova Povnya CRM Bot
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Optional


class CourierKeyboards:
    """
    Class for generating inline keyboards for courier bot
    """
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Main menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("📦 Мої доставки сьогодні", callback_data="deliveries_today"),
                InlineKeyboardButton("📅 Доставки завтра", callback_data="deliveries_tomorrow")
            ],
            [
                InlineKeyboardButton("📋 Всі доставки", callback_data="deliveries_all"),
                InlineKeyboardButton("👤 Мій профіль", callback_data="profile")
            ],
            [
                InlineKeyboardButton("📊 Статистика", callback_data="statistics"),
                InlineKeyboardButton("❓ Допомога", callback_data="help")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def delivery_actions(delivery_id: int) -> InlineKeyboardMarkup:
        """Keyboard with actions for specific delivery"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Доставлено", callback_data=f"delivery_complete_{delivery_id}"),
                InlineKeyboardButton("📞 Зателефонувати", callback_data=f"delivery_call_{delivery_id}")
            ],
            [
                InlineKeyboardButton("📍 Показати на карті", callback_data=f"delivery_location_{delivery_id}"),
                InlineKeyboardButton("❌ Проблема", callback_data=f"delivery_problem_{delivery_id}")
            ],
            [
                InlineKeyboardButton("🔙 Назад до списку", callback_data="deliveries_back")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirm_delivery_completion(delivery_id: int) -> InlineKeyboardMarkup:
        """Confirmation keyboard for delivery completion"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Так, доставлено", callback_data=f"confirm_complete_{delivery_id}"),
                InlineKeyboardButton("❌ Скасувати", callback_data=f"cancel_complete_{delivery_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def problem_types(delivery_id: int) -> InlineKeyboardMarkup:
        """Keyboard with problem types"""
        keyboard = [
            [
                InlineKeyboardButton("🏠 Немає дома", callback_data=f"problem_no_home_{delivery_id}"),
                InlineKeyboardButton("📞 Не відповідає", callback_data=f"problem_no_answer_{delivery_id}")
            ],
            [
                InlineKeyboardButton("🚫 Відмовився", callback_data=f"problem_refused_{delivery_id}"),
                InlineKeyboardButton("📍 Не знайшов адресу", callback_data=f"problem_address_{delivery_id}")
            ],
            [
                InlineKeyboardButton("💰 Проблема з оплатою", callback_data=f"problem_payment_{delivery_id}"),
                InlineKeyboardButton("🔧 Інше", callback_data=f"problem_other_{delivery_id}")
            ],
            [
                InlineKeyboardButton("🔙 Назад", callback_data=f"delivery_back_{delivery_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def time_periods() -> InlineKeyboardMarkup:
        """Keyboard for selecting time periods"""
        keyboard = [
            [
                InlineKeyboardButton("📅 Сьогодні", callback_data="period_today"),
                InlineKeyboardButton("📅 Завтра", callback_data="period_tomorrow")
            ],
            [
                InlineKeyboardButton("📅 Цей тиждень", callback_data="period_week"),
                InlineKeyboardButton("📅 Наступний тиждень", callback_data="period_next_week")
            ],
            [
                InlineKeyboardButton("🔙 Головне меню", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def registration_confirmation(phone: str) -> InlineKeyboardMarkup:
        """Keyboard for registration confirmation"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Підтвердити", callback_data=f"confirm_registration_{phone}"),
                InlineKeyboardButton("❌ Скасувати", callback_data="cancel_registration")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_to_main() -> InlineKeyboardMarkup:
        """Simple back to main menu keyboard"""
        keyboard = [
            [InlineKeyboardButton("🔙 Головне меню", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def today_deliveries_menu() -> InlineKeyboardMarkup:
        """Menu for today's deliveries with send addresses button"""
        keyboard = [
            [
                InlineKeyboardButton("📍 Надіслати адреси", callback_data="send_today_addresses")
            ],
            [
                InlineKeyboardButton("🔙 Головне меню", callback_data="main_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def navigation_options(delivery_id: int, address: str) -> InlineKeyboardMarkup:
        """Keyboard with navigation app options"""
        import urllib.parse
        
        # Кодуємо адресу для URL
        encoded_address = urllib.parse.quote(address)
        
        # Google Maps URL
        google_maps_url = f"https://maps.google.com/maps?q={encoded_address}"
        
        # Waze URL  
        waze_url = f"https://waze.com/ul?q={encoded_address}"
        
        keyboard = [
            [
                InlineKeyboardButton("🗺️ Google Maps", url=google_maps_url),
                InlineKeyboardButton("🚗 Waze", url=waze_url)
            ],
            [
                InlineKeyboardButton("📱 Apple Maps", url=f"http://maps.apple.com/?q={encoded_address}")
            ],
            [
                InlineKeyboardButton("🔙 До доставки", callback_data=f"delivery_back_{delivery_id}")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def delivery_list_navigation(page: int = 0, total_pages: int = 1) -> InlineKeyboardMarkup:
        """Navigation keyboard for delivery lists"""
        keyboard = []
        
        # Navigation buttons
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Попередня", callback_data=f"deliveries_page_{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("Наступна ➡️", callback_data=f"deliveries_page_{page+1}"))
        
        if nav_row:
            keyboard.append(nav_row)
        
        # Page indicator
        if total_pages > 1:
            keyboard.append([
                InlineKeyboardButton(f"Сторінка {page + 1} з {total_pages}", callback_data="page_info")
            ])
        
        # Back to main menu
        keyboard.append([
            InlineKeyboardButton("🔙 Головне меню", callback_data="main_menu")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def custom_keyboard(buttons: List[List[dict]]) -> InlineKeyboardMarkup:
        """
        Create custom keyboard from button configuration
        
        Args:
            buttons: List of button rows, each containing button configs with 'text' and 'callback_data'
        
        Example:
            buttons = [
                [{"text": "Button 1", "callback_data": "btn1"}, {"text": "Button 2", "callback_data": "btn2"}],
                [{"text": "Button 3", "callback_data": "btn3"}]
            ]
        """
        keyboard = []
        for row in buttons:
            keyboard_row = []
            for button_config in row:
                keyboard_row.append(
                    InlineKeyboardButton(
                        text=button_config['text'],
                        callback_data=button_config['callback_data']
                    )
                )
            keyboard.append(keyboard_row)
        
        return InlineKeyboardMarkup(keyboard) 