from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📅 Мой профиль"))
    builder.add(KeyboardButton(text="🎁 Ближайшие дни рождения"))
    builder.add(KeyboardButton(text="📦 Отправить штрих-код"))
    builder.add(KeyboardButton(text="❓ Помощь"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def get_participation_type_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🎁 Только дарить", callback_data="participation_give_only"))
    builder.add(InlineKeyboardButton(text="🎁🎉 Дарить и получать", callback_data="participation_give_and_receive"))
    return builder.as_markup()

def get_edit_profile_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Изменить имя", callback_data="edit_name"))
    builder.add(InlineKeyboardButton(text="📅 Изменить дату рождения", callback_data="edit_birthday"))
    builder.add(InlineKeyboardButton(text="🎁 Изменить тип участия", callback_data="edit_participation"))
    builder.add(InlineKeyboardButton(text="🏠 Изменить адреса", callback_data="edit_addresses"))
    builder.add(InlineKeyboardButton(text="💭 Изменить пожелания", callback_data="edit_wishes"))
    builder.add(InlineKeyboardButton(text="📢 Уведомить с адресами", callback_data="notify_with_addresses"))
    builder.add(InlineKeyboardButton(text="🎁 Готов принимать подарки", callback_data="notify_ready_receive"))
    builder.adjust(2)
    return builder.as_markup()

def get_addresses_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📦 OZON", callback_data="address_ozon"))
    builder.add(InlineKeyboardButton(text="📦 Яндекс Маркет", callback_data="address_yandex"))
    builder.add(InlineKeyboardButton(text="📦 Wildberries", callback_data="address_wildberries"))
    builder.add(InlineKeyboardButton(text="✅ Готово", callback_data="address_done"))
    builder.adjust(3)
    return builder.as_markup()

def get_delay_keyboard(birthday_user_id: int = None):
    """Клавиатура для отложенных напоминаний. birthday_user_id опционален для обратной совместимости"""
    builder = InlineKeyboardBuilder()
    if birthday_user_id:
        builder.add(InlineKeyboardButton(text="⏰ Напомнить через день", callback_data=f"remind_1_{birthday_user_id}"))
        builder.add(InlineKeyboardButton(text="⏰ Напомнить через 3 дня", callback_data=f"remind_3_{birthday_user_id}"))
        builder.add(InlineKeyboardButton(text="⏰ Напомнить через неделю", callback_data=f"remind_7_{birthday_user_id}"))
        builder.add(InlineKeyboardButton(text="🚫 Не напоминать", callback_data=f"remind_never_{birthday_user_id}"))
    else:
        # Старый формат для обратной совместимости
        builder.add(InlineKeyboardButton(text="⏰ Напомнить через день", callback_data="remind_1"))
        builder.add(InlineKeyboardButton(text="⏰ Напомнить через 3 дня", callback_data="remind_3"))
        builder.add(InlineKeyboardButton(text="⏰ Напомнить через неделю", callback_data="remind_7"))
        builder.add(InlineKeyboardButton(text="🚫 Не напоминать", callback_data="remind_never"))
    builder.adjust(2)
    return builder.as_markup()

def get_users_list_keyboard(users, action_prefix="select_"):
    builder = InlineKeyboardBuilder()
    for user in users:
        builder.add(InlineKeyboardButton(
            text=f"{user['full_name']} ({user['birthday']})",
            callback_data=f"{action_prefix}{user['user_id']}"
        ))
    builder.adjust(1)
    return builder.as_markup()

def get_admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_list_users"))
    builder.add(InlineKeyboardButton(text="🎂 Все дни рождения", callback_data="admin_all_birthdays"))
    builder.add(InlineKeyboardButton(text="📬 История уведомлений", callback_data="admin_check_notifications"))
    builder.add(InlineKeyboardButton(text="👤 Просмотр пользователя", callback_data="admin_view_user"))
    builder.add(InlineKeyboardButton(text="✏️ Редактировать пользователя", callback_data="admin_edit_user"))
    builder.add(InlineKeyboardButton(text="❌ Удалить пользователя", callback_data="admin_delete_user"))
    builder.adjust(2)
    return builder.as_markup()

def get_cancel_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)

def get_ready_for_gifts_keyboard():
    """Клавиатура с кнопкой для уведомления участников"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🎁 Готов принимать подарки", callback_data="notify_ready_receive"))
    return builder.as_markup()

def get_notification_options_keyboard():
    """Клавиатура с опциями уведомлений после обновления адресов"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📢 Уведомить с адресами", callback_data="notify_with_addresses"))
    return builder.as_markup()