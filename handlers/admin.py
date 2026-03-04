from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

import states
from config import ADMIN_IDS
from database import Database
from keyboards import get_admin_keyboard, get_users_list_keyboard, get_main_menu, get_cancel_keyboard
from utils import parse_birthday
from datetime import datetime, date

router = Router()
db = Database()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У тебя нет доступа к админ-панели.")
        return
    
    await message.answer(
        "👨‍💻 <b>Админ-панель</b>\n\n"
        "Выбери действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode="html"
    )

@router.callback_query(F.data == "admin_list_users")
async def list_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    users = db.get_all_users()
    
    if not users:
        await callback.message.edit_text("Пользователей нет.")
        return
    
    # Оптимизация: получаем все адреса и пожелания одним запросом вместо N+1
    all_addresses = db.get_all_addresses()
    all_wishes = db.get_all_wishes()
    
    text = "👥 <b>Список пользователей:</b>\n\n"
    for user in users:
        addresses = all_addresses.get(user['user_id'], {})
        wishes = all_wishes.get(user['user_id'])
        
        text += (
            f"👤 {user['full_name']}\n"
            f"   ID: {user['user_id']}\n"
            f"   Ник: @{user['username'] or 'нет'}\n"
            f"   ДР: {user['birthday']}\n"
            f"   Тип: {'Только дарить' if user['participation_type'] == 'give_only' else 'Дарить и получать'}\n"
            f"   Зарегистрирован: {user['created_at'][:10]}\n"
        )
        
        # Добавляем адреса
        has_addresses = any(address for address in addresses.values() if address)
        if has_addresses:
            text += "   🏠 <b>Адреса:</b>\n"
            if addresses.get('ozon'):
                text += f"      📦 OZON: <code>{addresses['ozon']}</code>\n"
            if addresses.get('yandex'):
                text += f"      📦 Яндекс Маркет: <code>{addresses['yandex']}</code>\n"
            if addresses.get('wildberries'):
                text += f"      📦 Wildberries: <code>{addresses['wildberries']}</code>\n"
        else:
            text += "   🏠 Адреса: не указаны\n"
        
        # Добавляем пожелания
        if wishes:
            text += f"   💭 Пожелания: {wishes[:50]}{'...' if len(wishes) > 50 else ''}\n"
        
        text += "\n"
    
    # Отправляем новое сообщение вместо редактирования
    await callback.message.answer(text, parse_mode="html")
    await callback.answer()

@router.callback_query(F.data == "admin_all_birthdays")
async def show_all_birthdays(callback: CallbackQuery):
    """Показать все дни рождения"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    # Получаем все дни рождения, отсортированные по месяцу и дню
    birthdays = db.get_all_birthdays(sort_by="month_day")
    
    if not birthdays:
        await callback.message.answer("📭 В базе нет данных о днях рождениях.")
        await callback.answer()
        return
    
    # Подсчитываем статистику
    total_users = len(db.get_all_users())
    
    # Формируем сообщение
    response = f"🎂 <b>Все дни рождения</b>\n\n"
    response += f"Всего пользователей: {total_users}\n"
    
    # Группируем по месяцам
    months = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
    }
    
    grouped_by_month = {}
    for user in birthdays:
        try:
            bd_str = user['birthday']
            month_num = int(bd_str.split('-')[1])
            
            if month_num not in grouped_by_month:
                grouped_by_month[month_num] = []
            
            grouped_by_month[month_num].append(user)
        except:
            continue
    
    # Сортируем месяцы по порядку, начиная с текущего
    current_month = datetime.now().month
    sorted_months = []
    for i in range(12):
        month = (current_month + i - 1) % 12 + 1
        if month in grouped_by_month:
            sorted_months.append(month)
    
    # Выводим по месяцам
    for month_num in sorted_months:
        month_users = grouped_by_month[month_num]
        
        # Сортируем по дню месяца
        month_users.sort(key=lambda x: int(x['birthday'].split('-')[2]))
        
        response += f"<b>{months[month_num]}:</b>\n"
        
        for user in month_users:
            # Форматируем дату
            bd_str = user['birthday']
            bd_parts = bd_str.split('-')
            day = bd_parts[2]
            month = bd_parts[1]
            year = bd_parts[0] if len(bd_parts) > 0 else ""
            
            # Форматируем возраст (если есть)
            age_info = ""
            if 'age' in user:
                age_info = f" ({user['age']} лет)"
            
            # Форматируем информацию о ближайшем дне рождения
            days_info = ""
            if 'days_until' in user:
                days = user['days_until']
                if days == 0:
                    days_info = " - 🎉 СЕГОДНЯ!"
                elif days == 1:
                    days_info = " - 🎁 Завтра!"
                elif days <= 7:
                    days_info = f" - через {days} дней"
                elif days <= 30:
                    days_info = f" - через {days} дней"
                else:
                    next_date = datetime.strptime(user['next_birthday'], '%Y-%m-%d')
                    days_info = f" - {next_date.strftime('%d.%m.%Y')}"
            
            # Добавляем информацию об адресах
            addresses = db.get_user_addresses(user['user_id'])
            has_addresses = any(address for address in addresses.values() if address)
            address_icon = "🏠" if has_addresses else "❓"
            
            # Добавляем строку пользователя
            response += f"{address_icon} {day}.{month}"
            
            # Добавляем год, если он не 1900
            if year and year != "1900":
                response += f".{year}"
            
            response += f" - {user['full_name']}{age_info}{days_info}\n"
            
            # Добавляем краткую информацию о типе участия
            participation = "🎁🎉" if user['participation_type'] == 'give_and_receive' else "🎁"
            response += f"     {participation} "
            
            # Добавляем ID пользователя
            response += f"ID: {user['user_id']}\n"
        
        response += "\n"
        
    await callback.message.answer(response, parse_mode="html")
    await callback.answer()

@router.callback_query(F.data == "admin_edit_user")
async def select_user_to_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    users = db.get_all_users()
    
    if not users:
        await callback.message.edit_text("Пользователей нет.")
        return
    
    # Вместо edit_text используем answer для новых сообщений
    await callback.message.answer(
        "Выбери пользователя для редактирования:",
        reply_markup=get_users_list_keyboard(users, "edit_user_")
    )
    await state.set_state(states.AdminStates.editing_user)
    await callback.answer()

@router.callback_query(states.AdminStates.editing_user, F.data.startswith("edit_user_"))
async def edit_user_selected(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.replace("edit_user_", ""))
    user = db.get_user(user_id)
    
    if not user:
        await callback.message.answer("Пользователь не найден.")
        await state.clear()
        return
    
    await state.update_data(editing_user_id=user_id)
    
    # Используем answer вместо edit_text, так как у нас будет ReplyKeyboardMarkup
    await callback.message.answer(
        f"👤 Редактирование пользователя: {user['full_name']}\n\n"
        f"Текущие данные:\n"
        f"Имя: {user['full_name']}\n"
        f"ДР: {user['birthday']}\n"
        f"Тип: {user['participation_type']}\n\n"
        f"Введите новые данные в формате:\n"
        f"<code>Имя Фамилия|ДД.ММ.ГГГГ|give_only/give_and_receive</code>\n\n"
        f"Пример:\n"
        f"<code>Иван Иванов|15.05.1990|give_and_receive</code>",
        reply_markup=get_cancel_keyboard(), parse_mode="html"
    )
    await callback.answer()

@router.message(states.AdminStates.editing_user)
async def process_user_edit(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await message.answer("Отменено", reply_markup=get_main_menu())
        await state.clear()
        return
    
    data = await state.get_data()
    user_id = data['editing_user_id']
    
    try:
        parts = message.text.split('|')
        if len(parts) != 3:
            raise ValueError
        
        name = parts[0].strip()
        birthday_str = parts[1].strip()
        participation = parts[2].strip()
        
        birthday = parse_birthday(birthday_str)
        if not birthday:
            raise ValueError
        
        if participation not in ['give_only', 'give_and_receive']:
            raise ValueError
        
        # Обновляем пользователя
        db.update_user(
            user_id,
            full_name=name,
            birthday=birthday.strftime('%Y-%m-%d'),
            participation_type=participation
        )
        
        await message.answer(
            f"✅ Пользователь обновлен!\n\n"
            f"Новые данные:\n"
            f"Имя: {name}\n"
            f"ДР: {birthday.strftime('%d.%m.%Y')}\n"
            f"Тип: {'Только дарить' if participation == 'give_only' else 'Дарить и получать'}",
            reply_markup=get_main_menu()
        )
        
    except ValueError:
        await message.answer(
            "Неверный формат. Введите:\n"
            "<code>Имя Фамилия|ДД.ММ.ГГГГ|give_only/give_and_receive</code>",
            reply_markup=get_cancel_keyboard(), parse_mode="html"
        )
        return
    
    await state.clear()

@router.callback_query(F.data == "admin_view_user")
async def select_user_to_view(callback: CallbackQuery, state: FSMContext):
    """Выбор пользователя для просмотра детальной информации"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    users = db.get_all_users()
    
    if not users:
        await callback.message.edit_text("Пользователей нет.")
        return
    
    await callback.message.answer(
        "Выбери пользователя для просмотра:",
        reply_markup=get_users_list_keyboard(users, "view_user_")
    )
    await callback.answer()

@router.callback_query(F.data.startswith("view_user_"))
async def view_user_details(callback: CallbackQuery):
    """Показать детальную информацию о пользователе включая адреса"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    user_id = int(callback.data.replace("view_user_", ""))
    user = db.get_user(user_id)
    
    if not user:
        await callback.message.answer("Пользователь не найден.")
        await callback.answer()
        return
    
    # Получаем адреса и пожелания
    addresses = db.get_user_addresses(user_id)
    wishes = db.get_wishes(user_id)
    
    user_info = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"<b>Основные данные:</b>\n"
        f"Имя: {user['full_name']}\n"
        f"ID: {user['user_id']}\n"
        f"Ник: @{user['username'] or 'нет'}\n"
        f"ДР: {user['birthday']}\n"
        f"Тип участия: {'Только дарить' if user['participation_type'] == 'give_only' else 'Дарить и получать'}\n"
        f"Зарегистрирован: {user['created_at'][:10]}\n"
    )
    
    # Добавляем адреса
    has_addresses = any(address for address in addresses.values() if address)
    if has_addresses:
        user_info += "\n🏠 <b>Адреса для отправки подарков:</b>\n"
        if addresses.get('ozon'):
            user_info += f"📦 OZON: <code>{addresses['ozon']}</code>\n"
        if addresses.get('yandex'):
            user_info += f"📦 Яндекс Маркет: <code>{addresses['yandex']}</code>\n"
        if addresses.get('wildberries'):
            user_info += f"📦 Wildberries: <code>{addresses['wildberries']}</code>\n"
    else:
        user_info += "\n🏠 Адреса: не указаны\n"
    
    # Добавляем пожелания
    if wishes:
        user_info += f"\n💭 <b>Пожелания:</b>\n{wishes}\n"
    else:
        user_info += "\n💭 Пожелания: не указаны\n"
    
    await callback.message.answer(user_info, parse_mode="html")
    await callback.answer()

@router.callback_query(F.data == "admin_check_notifications")
async def check_notifications(callback: CallbackQuery):
    """Показать историю отправленных уведомлений"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    # Получаем все уведомления
    notifications = db.get_notifications_history()
    
    if not notifications:
        await callback.message.answer("📭 Уведомления еще не отправлялись.")
        await callback.answer()
        return
    
    # Группируем по именинникам и годам
    grouped = {}
    for notif in notifications:
        key = (notif['birthday_user_id'], notif['year'])
        if key not in grouped:
            grouped[key] = {
                'birthday_user_name': notif['birthday_user_name'] or f"ID: {notif['birthday_user_id']}",
                'year': notif['year'],
                'notified_users': []
            }
        
        # Добавляем уведомленного пользователя (если это не сам именинник)
        if notif['notified_user_id'] != notif['birthday_user_id']:
            notified_name = notif['notified_user_name'] or f"ID: {notif['notified_user_id']}"
            if notified_name not in grouped[key]['notified_users']:
                grouped[key]['notified_users'].append(notified_name)
    
    # Формируем сообщение
    text = "📬 <b>История отправленных уведомлений</b>\n\n"
    
    # Сортируем по дате отправки (новые сначала)
    sorted_groups = sorted(grouped.items(), key=lambda x: x[1]['year'], reverse=True)
    
    for (bd_user_id, year), data in sorted_groups:
        text += f"🎂 <b>{data['birthday_user_name']}</b>\n"
        text += f"   Год: {year}\n"
        
        if data['notified_users']:
            text += f"   Отправлено {len(data['notified_users'])} пользователям:\n"
            for user_name in data['notified_users']:
                text += f"   • {user_name}\n"
        else:
            text += "   Уведомления отправлены только имениннику\n"
        
        text += "\n"

    
    await callback.message.answer(text, parse_mode="html")
    await callback.answer()

@router.callback_query(F.data == "admin_delete_user")
async def select_user_to_delete(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    users = db.get_all_users()
    
    if not users:
        await callback.message.edit_text("Пользователей нет.")
        return
    
    # Используем answer вместо edit_text
    await callback.message.answer(
        "Выбери пользователя для удаления:",
        reply_markup=get_users_list_keyboard(users, "delete_user_")
    )
    await state.set_state(states.AdminStates.deleting_user)
    await callback.answer()

@router.callback_query(states.AdminStates.deleting_user, F.data.startswith("delete_user_"))
async def delete_user_confirmation(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.replace("delete_user_", ""))
    user = db.get_user(user_id)
    
    if not user:
        await callback.message.answer("Пользователь не найден.")
        await state.clear()
        return
    
    await state.update_data(deleting_user_id=user_id)
    
    # Используем answer вместо edit_text, так как потом будет ReplyKeyboardMarkup
    await callback.message.answer(
        f"⚠️ <b>Подтверди удаление</b>\n\n"
        f"Пользователь: {user['full_name']}\n"
        f"ДР: {user['birthday']}\n"
        f"Тип: {user['participation_type']}\n\n"
        f"Это действие нельзя отменить!\n"
        f"Напиши 'ДА' для подтверждения или 'НЕТ' для отмены.",
        reply_markup=get_cancel_keyboard(), parse_mode="html"
    )
    await callback.answer()

@router.message(states.AdminStates.deleting_user)
async def process_user_delete(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data['deleting_user_id']
    
    if message.text == "❌ Отмена":
        await message.answer("❌ Удаление отменено.", reply_markup=get_main_menu())
        await state.clear()
        return
    
    if message.text.upper() == 'ДА':
        user = db.get_user(user_id)
        if user:
            db.delete_user(user_id)
            await message.answer(f"✅ Пользователь {user['full_name']} удален.", reply_markup=get_main_menu())
    elif message.text.upper() == 'НЕТ':
        await message.answer("❌ Удаление отменено.", reply_markup=get_main_menu())
    else:
        await message.answer(
            "Пожалуйста, введи 'ДА' для подтверждения или 'НЕТ' для отмены.\n"
            "Или нажми '❌ Отмена'.",
            reply_markup=get_cancel_keyboard()
        )
        return
    

    await state.clear()

@router.message(F.text == "/test_reminder")
async def test_reminder_command(message: Message):
    """Тестовая команда для проверки напоминаний (только для админов)"""
    try:
        from database import Database
        db = Database()
        
        # Проверяем, есть ли напоминания для отправки сегодня
        due_delays = db.get_due_delays()
        
        if not due_delays:
            await message.answer("📭 Сегодня нет напоминаний для отправки")
            return
        
        response = "⏰ <b>Напоминания на сегодня:</b>\n\n"
        
        for delay in due_delays:
            response += (
                f"👤 Пользователь: {delay['user_name']}\n"
                f"🎂 Именинник: {delay['birthday_user_name']}\n"
                f"📅 Дата напоминания: {delay['delay_until']}\n"
                f"⏱ Через дней: {delay['delay_days']}\n\n"
            )
        
        await message.answer(response)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        print(f"Ошибка в test_reminder_command: {e}")


@router.message(F.text == "/set_test_reminder")
async def set_test_reminder_command(message: Message):
    """Установить тестовое напоминание на завтра (для отладки)"""
    try:
        from database import Database
        db = Database()
        
        # Берем первого пользователя как именинника
        all_users = db.get_all_users()
        if len(all_users) < 2:
            await message.answer("Нужно хотя бы 2 пользователя для теста")
            return
        
        # Берем второго пользователя как именинника
        birthday_user = all_users[1]
        
        # Устанавливаем напоминание на завтра
        db.set_delay(
            user_id=message.from_user.id,
            birthday_user_id=birthday_user['user_id'],
            delay_days=1,  # На завтра
            year=datetime.now().year
        )
        
        await message.answer(
            f"✅ Тестовое напоминание установлено!\n"
            f"Завтра я напомню вам о дне рождения {birthday_user['full_name']}"
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        print(f"Ошибка в set_test_reminder_command: {e}")

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    await callback.message.answer(
        "📢 Введите сообщение для рассылки всем пользователям.\n"
        "Это может быть текст, фото, документ – я скопирую его в точности.\n"
        "Для отмены нажмите кнопку ниже.",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.broadcast)
    await callback.answer()

@router.message(AdminStates.broadcast)
async def admin_broadcast_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа")
        await state.clear()
        return

    # Кнопка отмены
    if message.text == "❌ Отмена":
        await message.answer("❌ Рассылка отменена.", reply_markup=get_main_menu())
        await state.clear()
        return

    # Получаем всех пользователей
    users = db.get_all_users()
    if not users:
        await message.answer("📭 В базе нет пользователей для рассылки.")
        await state.clear()
        return

    # Уведомление о начале
    status_msg = await message.answer("⏳ Начинаю рассылку...")

    successful = 0
    failed = 0

    for user in users:
        try:
            # Копируем исходное сообщение (текст, фото, документ – всё поддерживается)
            await message.copy_to(chat_id=user['user_id'])
            successful += 1
        except Exception as e:
            print(f"❌ Ошибка отправки пользователю {user['user_id']}: {e}")
            failed += 1

    await status_msg.delete()
    await message.answer(
        f"✅ Рассылка завершена!\n"
        f"📨 Успешно отправлено: {successful}\n"
        f"❌ Не удалось отправить: {failed}",
        reply_markup=get_main_menu()
    )
    await state.clear()
