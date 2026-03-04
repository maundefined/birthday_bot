from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import re

import states
from database import Database
from keyboards import get_delay_keyboard, get_users_list_keyboard, get_main_menu, get_ready_for_gifts_keyboard, get_notification_options_keyboard
from utils import format_birthday_message, calculate_next_birthday

router = Router()
db = Database()

@router.message(F.text == "🎁 Ближайшие дни рождения")
async def show_upcoming_birthdays(message: Message):
    users = db.get_all_users()
    upcoming = []
    
    today = datetime.now().date()
    
    for user in users:
        # Пропускаем текущего пользователя
        if user['user_id'] == message.from_user.id:
            continue
            
        if user['birthday']:
            try:
                # Парсим дату рождения
                bd_str = user['birthday']
                # Проверяем формат даты
                if len(bd_str) < 10:  # Неполная дата
                    continue
                    
                bd_date = datetime.strptime(bd_str, '%Y-%m-%d').date()
                
                # Рассчитываем следующий день рождения
                next_bd, days_until = calculate_next_birthday(bd_date)
                
                # Показываем только ближайшие 60 дней
                if 0 <= days_until <= 60:
                    upcoming.append({
                        'user': user,
                        'days_until': days_until,
                        'next_bd': next_bd
                    })
                    
            except Exception as e:
                print(f"Ошибка при обработке дня рождения пользователя {user['full_name']}: {e}")
                continue
    
    if not upcoming:
        await message.answer("🎉 В ближайшие 2 месяца дней рождения нет!")
        return
    
    # Сортируем по дням до дня рождения
    upcoming.sort(key=lambda x: x['days_until'])
    
    response = "🎁 <b>Ближайшие дни рождения:</b>\n\n"
    
    for item in upcoming:
        user = item['user']
        days = item['days_until']
        
        # Форматируем в зависимости от количества дней
        if days == 0:
            response += f"🎉 <b>СЕГОДНЯ!</b> {user['full_name']}\n"
        elif days == 1:
            response += f"🎁 <b>Завтра!</b> {user['full_name']}\n"
        elif days <= 7:
            response += f"🔥 Через {days} дней: {user['full_name']}\n"
        else:
            response += f"🎊 Через {days} дней: {user['full_name']}\n"
        
        # Добавляем дополнительную информацию
        response += f"   📅 Дата рождения: {user['birthday'][5:]}\n"
    
    await message.answer(response, parse_mode="html")

async def send_birthday_notification(birthday_user_id: int, bot, force: bool = False):
    """Отправляет уведомление о дне рождения другим пользователям"""
    try:
        # Используем модульный экземпляр db вместо создания нового
        
        birthday_user = db.get_user(birthday_user_id)
        if not birthday_user or not birthday_user['birthday']:
            return
        
        addresses = db.get_user_addresses(birthday_user_id)
        wishes = db.get_wishes(birthday_user_id)
        year = datetime.now().year
        
        # Проверяем, есть ли хотя бы один адрес
        has_addresses = any(address for address in addresses.values() if address)
        
        # Если адресов нет и не принудительная отправка - запрашиваем адреса
        if not force:
            # Проверяем, не запрашивали ли уже адреса сегодня
            if not db.is_notification_sent(birthday_user_id, year, "address_request_today"):
                try:
                    await bot.send_message(
                        birthday_user_id,
                        f"🎉 <b>Скоро твой день рождения!</b>\n\n"
                        f"Пожалуйста, укажи адреса ПВЗ для получения подарков, "
                        f"чтобы другие участники могли отправить тебе подарки.\n\n"
                        f"Перейди в '📅 Мой профиль' → нажми '✏️ Изменить адреса'\n\n"
                        f"Если адреса уже указаны, не забудь нажать кнопку, чтоб отправить уведомления другим участникам.",
                        parse_mode="html"
                    )
                    
                    # Сохраняем факт запроса адресов сегодня
                    db.add_notification(birthday_user_id, birthday_user_id, "address_request_today", year)
                    print(f"📬 Запрос адресов отправлен {birthday_user['full_name']} в день рождения")
                except Exception as e:
                    print(f"❌ Не удалось запросить адреса у пользователя {birthday_user_id}: {e}")
            
            # Не отправляем уведомления, пока нет адресов
            print(f"⏳ Ожидание адресов от {birthday_user['full_name']} перед отправкой уведомлений")
            return False
        
        # Проверяем, сегодня ли день рождения (вычисляем один раз для переиспользования)
        bd_date = datetime.strptime(birthday_user['birthday'], '%Y-%m-%d').date()
        next_bd, days_until = calculate_next_birthday(bd_date)
        is_birthday_today = (days_until == 0)
        
        # Если есть адреса, сегодня день рождения, и кнопка еще не нажата - показываем кнопку "Я готов забрать подарки"
        if has_addresses and is_birthday_today and not force and not db.has_ready_receive_notification_sent(birthday_user_id, year):
            if not db.is_notification_sent(birthday_user_id, year, "birthday_notification"):
                try:
                    await bot.send_message(
                        birthday_user_id,
                        f"🎉 <b>Сегодня твой день рождения!</b>\n\n"
                        f"Твои адреса сохранены. Нажми кнопку ниже, чтобы сообщить участникам, что ты готов(а) забрать подарки:",
                        reply_markup=get_ready_for_gifts_keyboard(), parse_mode="html"
                    )
                except Exception as e:
                    print(f"❌ Не удалось отправить сообщение с кнопкой пользователю {birthday_user_id}: {e}")
        
        # Получаем всех пользователей, кроме именинника
        all_users = db.get_all_users()
        
        # Проверяем, не было ли уже отправлено уведомление в этом году
        if db.is_notification_sent(birthday_user_id, year, "birthday_notification"):
            print(f"⚠️ Уведомление о дне рождения {birthday_user['full_name']} уже отправлено в этом году")
            return True
        
        # Проверяем, нажал ли именинник кнопку "Я готов забрать подарки" (если не принудительная отправка)
        if not force and not db.has_ready_receive_notification_sent(birthday_user_id, year):
            print(f"⏳ Ожидание нажатия кнопки 'Я готов забрать подарки' от {birthday_user['full_name']}")
            return False
        
        # Отправляем уведомление каждому пользователю
        notified_count = 0
        for user in all_users:
            if user['user_id'] == birthday_user_id:
                continue
            
            try:
                message = f"🎉 <b>СКОРО {birthday_user['full_name'].upper()} ПРАЗДНУЕТ ДЕНЬ РОЖДЕНИЯ!</b>\n\n"
                
                # Отправляем адреса только если кнопка была нажата
                if addresses and db.has_ready_receive_notification_sent(birthday_user_id, year):
                    # Добавляем дату и дни до дня рождения (используем уже вычисленные значения из строки 122)
                    message += f"📅 Дата рождения: {birthday_user['birthday']}\n"
                    if days_until == 0:
                        message += f"⏳ <b>СЕГОДНЯ!</b>\n\n"
                    elif days_until == 1:
                        message += f"⏳ До дня рождения: <b>завтра</b>\n\n"
                    else:
                        message += f"⏳ До дня рождения: <b>{days_until} дней</b>\n\n"
                    
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
                
                # Отправляем сообщение с кнопками для отложенного напоминания
                await bot.send_message(
                    user['user_id'], 
                    message, 
                    parse_mode="html",
                    reply_markup=get_delay_keyboard(birthday_user_id)
                )
                notified_count += 1
                
                # Сохраняем факт отправки уведомления
                db.add_notification(birthday_user_id, user['user_id'], "birthday_notification", year)
                
            except Exception as e:
                print(f"❌ Не удалось отправить уведомление пользователю {user['user_id']}: {e}")
        
        # Сохраняем общее уведомление для именинника
        db.add_notification(birthday_user_id, birthday_user_id, "birthday_notification", year)
        
        print(f"✅ Отправлено {notified_count} уведомлений о дне рождения {birthday_user['full_name']}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в send_birthday_notification: {e}")
        return False

async def request_addresses_from_user(user_id: int, bot):
    try:
        user = db.get_user(user_id)
        if not user:
            return
        
        year = datetime.now().year
        bd_date = datetime.strptime(user['birthday'], '%Y-%m-%d').date()
        next_bd, days_until = calculate_next_birthday(bd_date)
        
        # Планировщик вызывает эту функцию только при days_until == 10,
        # но на всякий случай оставим проверку
        if days_until != 10:
            return
        
        # Проверяем, не запрашивали ли уже адреса в этом году
        if db.is_notification_sent(user_id, year, "address_request"):
            print(f"⚠️ Запрос адресов у {user['full_name']} уже отправлялся в этом году")
            return
        
        addresses = db.get_user_addresses(user_id)
        has_addresses = any(address for address in addresses.values() if address)
        
        if not has_addresses:
            # Адресов нет – запрашиваем их
            try:
                await bot.send_message(
                    user_id,
                    f"🎉 Привет! Через 10 дней твой день рождения!\n\n"
                    f"Пожалуйста, укажи адреса ПВЗ для получения подарков.\n"
                    f"Можно указать несколько или хотя бы один адрес.\n\n"
                    f"Перейди в '📅 Мой профиль' → нажми '✏️ Изменить адреса'"
                )
                db.add_notification(user_id, user_id, "address_request", year)
                print(f"✅ Запрос адресов отправлен {user['full_name']}")
            except Exception as e:
                print(f"❌ Не удалось запросить адреса у пользователя {user_id}: {e}")
        else:
            # Адреса уже есть – предлагаем уведомить участников, если ещё не отправляли такое напоминание
            if not db.is_notification_sent(user_id, year, "remind_to_notify"):
                try:
                    await bot.send_message(
                        user_id,
                        f"🎉 Через 10 дней твой день рождения!\n\n"
                        f"Твои адреса уже сохранены. Хочешь уведомить участников, чтобы они знали, куда отправлять подарки?",
                        reply_markup=get_notification_options_keyboard()
                    )
                    # Запоминаем, что мы уже отправили это напоминание (чтобы не дублировать)
                    db.add_notification(user_id, user_id, "remind_to_notify", year)
                    print(f"✅ Напоминание об уведомлении отправлено {user['full_name']}")
                except Exception as e:
                    print(f"❌ Не удалось отправить напоминание об уведомлении {user_id}: {e}")
            else:
                print(f"ℹ️ У {user['full_name']} уже есть адреса, и напоминание об уведомлении отправлялось")
                
    except Exception as e:
        print(f"❌ Ошибка в request_addresses_from_user: {e}")

async def send_notification_with_addresses(birthday_user_id: int, bot):
    """Отправляет уведомление с адресами всем участникам"""
    try:
        # Используем модульный экземпляр db вместо создания нового
        
        birthday_user = db.get_user(birthday_user_id)
        if not birthday_user or not birthday_user['birthday']:
            return False
        
        addresses = db.get_user_addresses(birthday_user_id)
        wishes = db.get_wishes(birthday_user_id)
        
        # Проверяем, есть ли хотя бы один адрес
        has_addresses = any(address for address in addresses.values() if address)
        if not has_addresses:
            return False
        
        # Рассчитываем дату и дни до дня рождения
        bd_date = datetime.strptime(birthday_user['birthday'], '%Y-%m-%d').date()
        next_bd, days_until = calculate_next_birthday(bd_date)
        
        # Получаем всех пользователей, кроме именинника
        all_users = db.get_all_users()
        year = datetime.now().year
        
        # Отправляем уведомление каждому пользователю
        notified_count = 0
        for user in all_users:
            if user['user_id'] == birthday_user_id:
                continue
            
            try:
                message = f"🎉 <b>{birthday_user['full_name'].upper()} ПРАЗДНУЕТ СВОЙ ДЕНЬ РОЖДЕНИЯ!</b>\n\n"
                
                # Добавляем дату и дни до дня рождения
                message += f"📅 Дата рождения: {birthday_user['birthday']}\n"
                if days_until == 0:
                    message += f"⏳ <b>СЕГОДНЯ!</b>\n\n"
                elif days_until == 1:
                    message += f"⏳ До дня рождения: <b>завтра</b>\n\n"
                else:
                    message += f"⏳ До дня рождения: <b>{days_until} дней</b>\n\n"
                
                # Всегда отправляем адреса в этом уведомлении
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
                
                # Отправляем сообщение с кнопками для отложенного напоминания
                await bot.send_message(
                    user['user_id'], 
                    message, 
                    parse_mode="html",
                    reply_markup=get_delay_keyboard(birthday_user_id)
                )
                notified_count += 1
                
                # Сохраняем факт отправки уведомления
                db.add_notification(birthday_user_id, user['user_id'], "notification_with_addresses", year)
                
            except Exception as e:
                print(f"❌ Не удалось отправить уведомление пользователю {user['user_id']}: {e}")
        
        # Отмечаем, что уведомление с адресами было отправлено
        db.add_notification(birthday_user_id, birthday_user_id, "notification_with_addresses", year)
        
        print(f"✅ Отправлено {notified_count} уведомлений с адресами от {birthday_user['full_name']}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в send_notification_with_addresses: {e}")
        return False

async def send_ready_receive_notification(birthday_user_id: int, bot):
    """Отправляет уведомление о готовности принимать подарки"""
    try:
        # Используем модульный экземпляр db вместо создания нового
        
        birthday_user = db.get_user(birthday_user_id)
        if not birthday_user or not birthday_user['birthday']:
            return False
        
        wishes = db.get_wishes(birthday_user_id)
        
        # Получаем всех пользователей, кроме именинника
        all_users = db.get_all_users()
        year = datetime.now().year
        
        # Отправляем уведомление каждому пользователю
        notified_count = 0
        for user in all_users:
            if user['user_id'] == birthday_user_id:
                continue
            
            try:
                message = f"🎁 <b>{birthday_user['full_name']} готов(а) принимать подарки!</b>\n\n"
                
                message += "🎉 Не забудь отправить штрих-код!"
                
                await bot.send_message(user['user_id'], message, parse_mode="html")
                notified_count += 1
                
                # Сохраняем факт отправки уведомления
                db.add_notification(birthday_user_id, user['user_id'], "ready_receive_notification", year)
                
            except Exception as e:
                print(f"❌ Не удалось отправить уведомление пользователю {user['user_id']}: {e}")
        
        # Отмечаем, что уведомление было отправлено
        db.mark_ready_receive_notification_sent(birthday_user_id, year)
        
        print(f"✅ Отправлено {notified_count} уведомлений о готовности принимать подарки от {birthday_user['full_name']}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в send_ready_receive_notification: {e}")
        return False

async def check_and_send_notifications_after_address_update(user_id: int, bot):
    """Проверяет, нужно ли показать кнопки уведомления после обновления адресов"""
    try:
        from database import Database
        db = Database()
        
        user = db.get_user(user_id)
        if not user or not user['birthday']:
            return
        
        # Проверяем, есть ли адреса
        addresses = db.get_user_addresses(user_id)
        has_addresses = any(address for address in addresses.values() if address)
        
        if has_addresses:
            try:
                await bot.send_message(
                    user_id,
                    "✅ Адреса сохранены!\n\n"
                    "Выбери действие:",
                    reply_markup=get_notification_options_keyboard()
                )
            except:
                pass
                        
    except Exception as e:
        print(f"❌ Ошибка в check_and_send_notifications_after_address_update: {e}")

@router.callback_query(F.data.startswith("remind_"))
async def handle_reminder(callback: CallbackQuery):
    """Обработчик отложенных напоминаний о днях рождения"""
    # Парсим callback_data: remind_<days>_<birthday_user_id> или remind_<days> (старый формат)
    parts = callback.data.split("_")
    
    if len(parts) < 2:
        await callback.answer("Ошибка обработки запроса", show_alert=True)
        return
    
    action = parts[1]  # "never", "1", "3", "7"
    birthday_user_id = None
    
    # Если есть третий элемент - это birthday_user_id
    if len(parts) >= 3:
        try:
            birthday_user_id = int(parts[2])
        except ValueError:
            pass
    
    if action == "never":
        # Пользователь не хочет напоминаний
        await callback.message.edit_text("✅ Хорошо, напоминать не буду.")
        await callback.answer()
        return
    
    try:
        delay_days = int(action)
        
        # Если birthday_user_id не передан, пытаемся найти из сообщения
        if not birthday_user_id:
            message_text = callback.message.text or callback.message.caption or ""
            
            # Пытаемся извлечь ID именинника из сообщения
            # Ищем паттерн "ID: <число>" в сообщении
            id_match = re.search(r'ID:\s*(\d+)', message_text)
            if id_match:
                birthday_user_id = int(id_match.group(1))
            
            # Если не нашли ID, пытаемся найти по имени
            if not birthday_user_id:
                # Извлекаем имя именинника из сообщения
                birthday_user_name = None
                if "ПРАЗДНУЕТ ДЕНЬ РОЖДЕНИЯ" in message_text:
                    match = re.search(r'(?:СКОРО\s+)?([А-ЯЁ\s]+?)\s+ПРАЗДНУЕТ', message_text)
                    if match:
                        birthday_user_name = match.group(1).strip()
                
                if birthday_user_name:
                    all_users = db.get_all_users()
                    for user in all_users:
                        if user['full_name'].upper() == birthday_user_name:
                            birthday_user_id = user['user_id']
                            break
        
        if birthday_user_id:
            birthday_user = db.get_user(birthday_user_id)
            if birthday_user:
                year = datetime.now().year
                
                # Сохраняем отложенное напоминание
                db.set_delay(
                    user_id=callback.from_user.id,
                    birthday_user_id=birthday_user_id,
                    delay_days=delay_days,
                    year=year
                )
                
                # Рассчитываем дату напоминания
                reminder_date = datetime.now() + timedelta(days=delay_days)
                
                await callback.message.edit_text(
                    f"✅ Отлично! Напомню тебе о дне рождения "
                    f"через {delay_days} {'день' if delay_days == 1 else 'дня' if delay_days < 5 else 'дней'} "
                    f"({reminder_date.strftime('%d.%m.%Y')})!\n\n"
                    f"Я пришлю сообщение в этот день с напоминанием 🎁"
                )
            else:
                await callback.message.edit_text(f"✅ Запомнил! Напомню через {delay_days} дней!")
        else:
            # Если не удалось найти именинника
            await callback.message.edit_text(f"✅ Хорошо! Напомню через {delay_days} дней!")
            
    except ValueError:
        await callback.message.edit_text("❌ Ошибка: неверный формат запроса")
    except Exception as e:
        print(f"❌ Ошибка обработки напоминания: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при сохранении напоминания")
    
    await callback.answer()
    
@router.callback_query(F.data == "notify_members")
async def handle_notify_members(callback: CallbackQuery):
    """Обработчик нажатия кнопки 'Уведомить участников'"""
    try:
        user = db.get_user(callback.from_user.id)
        if not user:
            await callback.answer("Сначала зарегистрируйся!", show_alert=True)
            return
        
        if not user['birthday']:
            await callback.answer("У тебя не указан день рождения!", show_alert=True)
            return
        
        # Проверяем, сегодня ли день рождения
        bd_date = datetime.strptime(user['birthday'], '%Y-%m-%d').date()
        next_bd, days_until = calculate_next_birthday(bd_date)
        
        if days_until != 0:
            await callback.answer("Эта кнопка доступна только в день рождения!", show_alert=True)
            return
        
        year = datetime.now().year
        
        # Проверяем, не отправлены ли уже уведомления
        if db.is_notification_sent(callback.from_user.id, year, "birthday_notification"):
            await callback.answer("Уведомления уже были отправлены!", show_alert=True)
            return
        
        # Отмечаем, что кнопка была нажата
        db.mark_notify_members_clicked(callback.from_user.id, year)
        
        # Отправляем уведомления
        result = await send_birthday_notification(callback.from_user.id, callback.message.bot, force=True)
        
        if result:
            await callback.message.edit_text(
                "✅ Уведомления с адресами отправлены другим участникам! 🎉"
            )
        else:
            await callback.answer("⚠️ Не удалось отправить уведомления. Проверьте логи.", show_alert=True)
        
        await callback.answer()
        
    except Exception as e:
        print(f"❌ Ошибка обработки кнопки уведомления: {e}")
        await callback.answer("❌ Ошибка при отправке уведомлений", show_alert=True)

@router.callback_query(F.data == "notify_with_addresses")
async def handle_notify_with_addresses(callback: CallbackQuery):
    """Обработчик нажатия кнопки 'Уведомить с адресами'"""
    try:
        user = db.get_user(callback.from_user.id)
        if not user:
            await callback.answer("Сначала зарегистрируйся!", show_alert=True)
            return
        
        if not user['birthday']:
            await callback.answer("У тебя не указан день рождения!", show_alert=True)
            return
        
        # --- НОВАЯ ПРОВЕРКА: сколько дней осталось до дня рождения ---
        bd_date = datetime.strptime(user['birthday'], '%Y-%m-%d').date()
        _, days_until = calculate_next_birthday(bd_date)
        
        if days_until > 10:
            await callback.answer(
                f"❌ Уведомление можно отправить только когда до дня рождения останется 10 дней или меньше.\n"
                f"Сейчас осталось {days_until} дней.",
                show_alert=True
            )
            return
        # -------------------------------------------------------------
        
        # Проверяем, есть ли адреса
        addresses = db.get_user_addresses(callback.from_user.id)
        has_addresses = any(address for address in addresses.values() if address)
        
        if not has_addresses:
            await callback.answer("Сначала укажи адреса в профиле!", show_alert=True)
            return
        
        # Отправляем уведомления с адресами
        result = await send_notification_with_addresses(callback.from_user.id, callback.message.bot)
        
        if result:
            try:
                await callback.message.edit_text(
                    "✅ Уведомления с адресами отправлены другим участникам! 🎉"
                )
            except:
                # Если не удалось отредактировать сообщение, отправляем новое
                await callback.message.answer(
                    "✅ Уведомления с адресами отправлены другим участникам! 🎉",
                    reply_markup=get_main_menu()
                )
        else:
            await callback.answer("⚠️ Не удалось отправить уведомления. Проверь логи.", show_alert=True)
        
        await callback.answer()
        
    except Exception as e:
        print(f"❌ Ошибка обработки кнопки уведомления с адресами: {e}")
        await callback.answer("❌ Ошибка при отправке уведомлений", show_alert=True)

@router.callback_query(F.data == "notify_ready_receive")
async def handle_notify_ready_receive(callback: CallbackQuery):
    """Обработчик нажатия кнопки 'Я готов забрать подарки'"""
    try:
        user = db.get_user(callback.from_user.id)
        if not user:
            await callback.answer("Сначала зарегистрируйся!", show_alert=True)
            return
        
        if not user['birthday']:
            await callback.answer("У тебя не указан день рождения!", show_alert=True)
            return
        
        # Проверяем, сегодня ли день рождения
        bd_date = datetime.strptime(user['birthday'], '%Y-%m-%d').date()
        next_bd, days_until = calculate_next_birthday(bd_date)
        
        if days_until != 0:
            await callback.answer("Эта кнопка доступна только в день рождения!", show_alert=True)
            return
        
        year = datetime.now().year
        
        # Проверяем, не отправлено ли уже такое уведомление в этом году
        if db.has_ready_receive_notification_sent(callback.from_user.id, year):
            await callback.answer("Такое уведомление уже было отправлено в этом году!", show_alert=True)
            return
        
        # Отправляем уведомление о готовности принимать подарки
        result = await send_ready_receive_notification(callback.from_user.id, callback.message.bot)
        
        if result:
            try:
                await callback.message.edit_text(
                    "✅ Уведомление о готовности забрать подарки отправлено другим участникам! 🎁"
                )
            except:
                # Если не удалось отредактировать сообщение, отправляем новое
                await callback.message.answer(
                    "✅ Уведомление о готовности забрать подарки отправлено другим участникам! 🎁",
                    reply_markup=get_main_menu()
                )
        else:
            await callback.answer("⚠️ Не удалось отправить уведомление. Проверь логи.", show_alert=True)
        
        await callback.answer()
        
    except Exception as e:
        print(f"❌ Ошибка обработки кнопки готовности принимать подарки: {e}")
        await callback.answer("❌ Ошибка при отправке уведомления", show_alert=True)

@router.message(F.text == "/force_notify")
async def force_notification(message: Message):
    """Принудительно отправить уведомление о своем дне рождения"""
    try:
        user = db.get_user(message.from_user.id)
        if not user:
            await message.answer("Сначала зарегистрируйся!")
            return
        
        if not user['birthday']:
            await message.answer("У тебя не указан день рождения!")
            return
        
        # Отмечаем, что кнопка была нажата (для принудительной отправки)
        year = datetime.now().year
        db.mark_notify_members_clicked(message.from_user.id, year)
        
        # Используем функцию отправки уведомления с force=True для принудительной отправки
        result = await send_birthday_notification(message.from_user.id, message.bot, force=True)
        
        if result:
            await message.answer("✅ Уведомления отправлены другим участникам!")
        else:
            await message.answer("⚠️ Не удалось отправить уведомления. Проверь логи.")
        
    except Exception as e:
        print(f"❌ Ошибка принудительного уведомления: {e}")

        await message.answer("❌ Ошибка при отправке уведомлений")


