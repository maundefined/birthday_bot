from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import states
from database import Database
from keyboards import (
    get_main_menu, 
    get_edit_profile_keyboard,
    get_addresses_keyboard,
    get_participation_type_keyboard,
    get_cancel_keyboard,
    get_notification_options_keyboard
)
from utils import parse_birthday

router = Router()
db = Database()

@router.message(F.text == "📅 Мой профиль")
async def show_profile(message: Message):
    user = db.get_user(message.from_user.id)
    
    if not user:
        await message.answer("Сначала зарегистрируйся с помощью /start")
        return
    
    addresses = db.get_user_addresses(user['user_id'])
    wishes = db.get_wishes(user['user_id'])
    
    profile_text = (
        f"👤 <b>Твой профиль:</b>\n\n"
        f"📝 Имя: {user['full_name']}\n"
        f"📅 День рождения: {user['birthday']}\n"
        f"🎁 Тип участия: {'Только дарить' if user['participation_type'] == 'give_only' else 'Дарить и получать'}\n\n"
    )
    
    if addresses:
        profile_text += "🏠 <b>Адреса ПВЗ:</b>\n"
        for service, address in addresses.items():
            service_name = {
                'ozon': 'OZON',
                'yandex': 'Яндекс Маркет',
                'wildberries': 'Wildberries'
            }.get(service, service)
            profile_text += f"📦 {service_name}: {address}\n"
        profile_text += "\n"
    
    if wishes:
        profile_text += f"💭 <b>Пожелания:</b>\n{wishes}\n\n"
    
    profile_text += "Нажми кнопку ниже, чтобы отредактировать данные:"
    
    await message.answer(profile_text, reply_markup=get_edit_profile_keyboard(), parse_mode="html")

@router.callback_query(F.data == "edit_name")
async def edit_name(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введи новое имя:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(states.ProfileStates.editing_name)
    await callback.answer()

@router.message(states.ProfileStates.editing_name)
async def process_new_name(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await message.answer("Отменено", reply_markup=get_main_menu())
        await state.clear()
        return
    
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Пожалуйста, введи корректное имя (минимум 2 символа):")
        return
    
    db.update_user(message.from_user.id, full_name=name)
    await message.answer(f"✅ Имя изменено на: {name}", reply_markup=get_main_menu())
    await state.clear()

@router.callback_query(F.data == "edit_birthday")
async def edit_birthday(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введи новую дату рождения в формате ДД.ММ.ГГГГ:\n"
        "Например: 15.05.1990",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(states.ProfileStates.editing_birthday)
    await callback.answer()

@router.message(states.ProfileStates.editing_birthday)
async def process_new_birthday(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await message.answer("Отменено", reply_markup=get_main_menu())
        await state.clear()
        return
    
    birthday = parse_birthday(message.text)
    if not birthday:
        await message.answer(
            "Неверный формат даты. Пожалуйста, введи дату в формате ДД.ММ.ГГГГ:"
        )
        return
    
    db.update_user(message.from_user.id, birthday=birthday.strftime('%Y-%m-%d'))
    await message.answer(f"✅ Дата рождения изменена на: {birthday.strftime('%d.%m.%Y')}", reply_markup=get_main_menu())
    await state.clear()

@router.callback_query(F.data == "edit_participation")
async def edit_participation(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Выбери новый тип участия:",
        reply_markup=get_participation_type_keyboard()
    )
    await state.set_state(states.ProfileStates.editing_participation)
    await callback.answer()

@router.callback_query(states.ProfileStates.editing_participation, F.data.startswith("participation_"))
async def process_new_participation(callback: CallbackQuery, state: FSMContext):
    participation_type = callback.data.replace("participation_", "")
    participation_text = "Только дарить" if participation_type == "give_only" else "Дарить и получать"
    
    db.update_user(callback.from_user.id, participation_type=participation_type)
    await callback.message.edit_text(f"✅ Тип участия изменен на: {participation_text}")
    await callback.message.answer("Профиль обновлен!", reply_markup=get_main_menu())
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "edit_addresses")
async def edit_addresses(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Выбери сервис для изменения адреса:",
        reply_markup=get_addresses_keyboard()
    )
    await state.set_state(states.ProfileStates.editing_address)
    await callback.answer()

@router.callback_query(states.ProfileStates.editing_address, F.data.startswith("address_"))
async def select_address_service(callback: CallbackQuery, state: FSMContext):
    service = callback.data.replace("address_", "")
    
    if service == "done":
        addresses = db.get_user_addresses(callback.from_user.id)
        if not any(addresses.values()):
            await callback.message.answer(
                "⚠️ Ты не указал ни одного адреса. "
                "Рекомендую указать хотя бы один адрес для получения подарков.",
                reply_markup=get_main_menu()
            )
        else:
            # Проверяем, нужно ли отправить уведомления после завершения редактирования адресов
            from handlers.birthday import check_and_send_notifications_after_address_update
            await check_and_send_notifications_after_address_update(callback.from_user.id, callback.message.bot)
            
            await callback.message.answer("✅ Адреса сохранены!", reply_markup=get_main_menu())
        await state.clear()
        await callback.answer()
        return
    
    service_names = {
        'ozon': 'OZON',
        'yandex': 'Яндекс Маркет',
        'wildberries': 'Wildberries'
    }
    
    await state.update_data(selected_service=service)
    await callback.message.answer(
        f"Введи адрес ПВЗ для {service_names[service]}:\n"
        f"(Ты можешь оставить поле пустым, если не используешь этот сервис)",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(states.ProfileStates.editing_address)
async def process_address(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await message.answer("Отменено", reply_markup=get_main_menu())
        await state.clear()
        return
    
    data = await state.get_data()
    service = data['selected_service']
    
    db.set_address(message.from_user.id, service, message.text.strip())
    
    # Проверяем, нужно ли отправить уведомления после обновления адресов
    from handlers.birthday import check_and_send_notifications_after_address_update
    await check_and_send_notifications_after_address_update(message.from_user.id, message.bot)
    
    # Показываем клавиатуру снова для выбора следующего сервиса
    await message.answer(
        f"✅ Адрес сохранен!\n"
        "Выбери следующий сервис или нажми '✅ Готово':",
        reply_markup=get_addresses_keyboard()
    )

@router.callback_query(F.data == "edit_wishes")
async def edit_wishes(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введи свои пожелания к подаркам:\n"
        "(Что тебе нравится, размеры одежды, любимые бренды и т.д.)",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(states.ProfileStates.editing_wishes)
    await callback.answer()

@router.message(states.ProfileStates.editing_wishes)
async def process_wishes(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await message.answer("Отменено", reply_markup=get_main_menu())
        await state.clear()
        return
    
    db.set_wishes(message.from_user.id, message.text.strip())
    await message.answer("✅ Пожелания сохранены!", reply_markup=get_main_menu())
    await state.clear()