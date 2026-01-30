import asyncio
from datetime import datetime, date, timedelta
from aiogram import Bot
from database import Database
from utils import calculate_next_birthday

class BirthdayScheduler:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.db = Database()
        self.is_running = False
    
    async def start(self):
        """Запуск планировщика проверки дней рождений"""
        self.is_running = True
        print("🎯 Планировщик дней рождения запущен")
        
        while self.is_running:
            try:
                await self.check_birthdays()
                # Проверяем каждые 24 часа
                await asyncio.sleep(60 * 60 * 24)
            except Exception as e:
                print(f"❌ Ошибка в планировщике: {e}")
                await asyncio.sleep(60 * 60)  # Ждем 60 минут при ошибке
    
    async def stop(self):
        """Остановка планировщика"""
        self.is_running = False
        print("🛑 Планировщик дней рождения остановлен")
    
    async def check_birthdays(self):
        """Проверяет дни рождения и отправляет уведомления"""
        print("🔍 Проверка дней рождения...")
        
        users = self.db.get_all_users()
        today = datetime.now().date()
        year = today.year
        
        for user in users:
            if not user['birthday']:
                continue
            
            try:
                # Парсим дату рождения
                bd_str = user['birthday']
                if len(bd_str) >= 10:
                    bd_date = datetime.strptime(bd_str, '%Y-%m-%d').date()
                    
                    # Рассчитываем следующий день рождения
                    next_bd, days_until = calculate_next_birthday(bd_date)
                    
                    print(f"👤 {user['full_name']}: день рождения {bd_str}, через {days_until} дней")
                    
                    # Если до дня рождения 10 дней - запрашиваем адреса
                    if days_until == 10:
                        await self.request_addresses(user['user_id'])
                    
                    # Если сегодня день рождения - сначала проверяем/запрашиваем адреса, затем уведомляем
                    if days_until == 0:
                        # Функция notify_about_birthday теперь сама проверяет адреса и запрашивает их при необходимости
                        await self.notify_about_birthday(user['user_id'])
                    
                    # Также проверяем, не пора ли напоминать об отложенных уведомлениях
                    await self.check_delayed_notifications(user['user_id'], days_until)
                        
            except Exception as e:
                print(f"❌ Ошибка обработки дня рождения {user['full_name']}: {e}")
                continue
    
    async def request_addresses(self, user_id: int):
        """Запрашивает адреса у именинника за 10 дней до дня рождения"""
        try:
            from handlers.birthday import request_addresses_from_user
            await request_addresses_from_user(user_id, self.bot)
        except Exception as e:
            print(f"❌ Ошибка при запросе адресов у {user_id}: {e}")
    
    async def notify_about_birthday(self, user_id: int):
        """Уведомляет других пользователей о дне рождении"""
        try:
            from handlers.birthday import send_birthday_notification
            await send_birthday_notification(user_id, self.bot)
        except Exception as e:
            print(f"❌ Ошибка при уведомлении о дне рождения {user_id}: {e}")
    
    async def check_delayed_notifications(self, birthday_user_id: int, days_until: int):
        """Проверяет отложенные уведомления для конкретного именинника"""
        try:
            # Оптимизация: получаем только напоминания для этого именинника
            delays = self.db.get_delays_by_birthday_user(birthday_user_id)
            
            for delay in delays:
                delay_days = delay['delay_days']
                # Если время для напоминания настало (дней до ДР соответствует задержке)
                if days_until == delay_days:
                    await self.send_reminder(delay['user_id'], birthday_user_id)
                    # Удаляем напоминание после отправки
                    self.db.delete_delay(delay['user_id'], birthday_user_id)
        except Exception as e:
            print(f"❌ Ошибка проверки отложенных уведомлений: {e}")
    
    async def send_reminder(self, user_id: int, birthday_user_id: int):
        """Отправляет напоминание пользователю о дне рождения"""
        try:
            from handlers.birthday import send_birthday_notification
            
            birthday_user = self.db.get_user(birthday_user_id)
            if not birthday_user:
                return
            
            # Получаем адреса и пожелания
            addresses = self.db.get_user_addresses(birthday_user_id)
            wishes = self.db.get_wishes(birthday_user_id)
            
            # Рассчитываем дату и дни до дня рождения
            bd_date = datetime.strptime(birthday_user['birthday'], '%Y-%m-%d').date()
            next_bd, days_until = calculate_next_birthday(bd_date)
            
            message = f"⏰ <b>Напоминание о дне рождения!</b>\n\n"
            message += f"🎉 <b>{birthday_user['full_name'].upper()} ПРАЗДНУЕТ ДЕНЬ РОЖДЕНИЯ!</b>\n\n"
            message += f"📅 Дата рождения: {birthday_user['birthday']}\n"
            
            if days_until == 0:
                message += f"⏳ <b>СЕГОДНЯ!</b>\n\n"
            elif days_until == 1:
                message += f"⏳ До дня рождения: <b>завтра</b>\n\n"
            else:
                message += f"⏳ До дня рождения: <b>{days_until} дней</b>\n\n"
            
            # Добавляем адреса если есть
            has_addresses = any(address for address in addresses.values() if address)
            if has_addresses:
                message += "🏠 <b>Адреса для отправки подарков:</b>\n"
                if addresses.get('ozon'):
                    message += f"📦 OZON: <code>{addresses['ozon']}</code>\n"
                if addresses.get('yandex'):
                    message += f"📦 Яндекс Маркет: <code>{addresses['yandex']}</code>\n"
                if addresses.get('wildberries'):
                    message += f"📦 Wildberries: <code>{addresses['wildberries']}</code>\n"
                message += "\n"
            
            if wishes:
                message += f"💭 <b>Пожелания именинника:</b>\n{wishes}\n\n"
            
            message += "🎁 Не забудь отправить подарок!"
            
            await self.bot.send_message(user_id, message, parse_mode="html")
            print(f"✅ Отправлено напоминание пользователю {user_id} о дне рождения {birthday_user['full_name']}")
        except Exception as e:
            print(f"❌ Ошибка отправки напоминания {user_id}: {e}")