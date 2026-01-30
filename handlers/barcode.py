from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext

import states
from database import Database
from keyboards import get_users_list_keyboard, get_main_menu, get_cancel_keyboard

router = Router()
db = Database()

@router.message(F.text == "📦 Отправить штрих-код")
async def start_barcode_send(message: Message, state: FSMContext):
    # Получаем всех пользователей, которым можно отправить подарок
    users = db.get_all_users()
    
    if len(users) <= 1:
        await message.answer("В системе пока нет других пользователей.")
        return
    
    # Исключаем текущего пользователя из списка
    recipients = [u for u in users if u['user_id'] != message.from_user.id]
    
    await message.answer(
        "Выбери получателя подарка:",
        reply_markup=get_users_list_keyboard(recipients, "barcode_to_")
    )
    await state.set_state(states.BarcodeStates.waiting_for_receiver)

@router.callback_query(states.BarcodeStates.waiting_for_receiver, F.data.startswith("barcode_to_"))
async def select_receiver(callback: CallbackQuery, state: FSMContext):
    receiver_id = int(callback.data.replace("barcode_to_", ""))
    
    # Проверяем, существует ли пользователь
    receiver = db.get_user(receiver_id)
    if not receiver:
        await callback.message.edit_text("Пользователь не найден.")
        await state.clear()
        return
    
    await state.update_data(receiver_id=receiver_id)
    await callback.message.edit_text(
        f"Выбран получатель: {receiver['full_name']}\n\n"
        f"Теперь отправь фото штрих-кода подарка:",
        reply_markup=None
    )
    
    await callback.message.answer(
        "Отправь фото штрих-кода или нажмите '❌ Отмена':",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(states.BarcodeStates.waiting_for_photo)
    await callback.answer()

@router.message(states.BarcodeStates.waiting_for_photo, F.photo)
async def receive_barcode_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    receiver_id = data['receiver_id']
    
    # Сохраняем самое большое фото
    largest_photo = max(message.photo, key=lambda p: p.file_size)
    photo_file_id = largest_photo.file_id
    
    # Сохраняем штрих-код в базу данных
    barcode_id = db.add_barcode(
        sender_id=message.from_user.id,
        receiver_id=receiver_id,
        photo_file_id=photo_file_id
    )
    
    # Отправляем подтверждение отправителю
    receiver = db.get_user(receiver_id)
    await message.answer(
        f"✅ Штрих-код успешно отправлен {receiver['full_name']}!\n"
        f"Получатель получит его, когда попросит бота показать доступные подарки.",
        reply_markup=get_main_menu()
    )
    
    # Уведомляем получателя (опционально)
    try:
        sender = db.get_user(message.from_user.id)
        await message.bot.send_message(
            receiver_id,
            f"🎁 {sender['full_name']} отправил(а) тебе подарок!\n"
            f"Используй команду /gifts, чтобы посмотреть все доступные подарки."
        )
    except:
        pass  # Пользователь может заблокировать бота
    
    await state.clear()

@router.message(states.BarcodeStates.waiting_for_photo)
async def handle_non_photo_message(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await message.answer("Отменено", reply_markup=get_main_menu())
        await state.clear()
    else:
        await message.answer("Пожалуйста, отправь фото штрих-кода или нажмите '❌ Отмена'.")

@router.message(F.text == "/gifts")
async def show_available_gifts(message: Message):
    user_id = message.from_user.id
    barcodes = db.get_undelivered_barcodes(user_id)
    
    if not barcodes:
        await message.answer("У тебя пока нет доступных подарков.")
        return
    
    for barcode in barcodes:
        caption = (
            f"🎁 Подарок от: {barcode['sender_name']}\n"
            f"📅 Отправлен: {barcode['sent_at']}\n\n"
            f"Покажи этот штрих-код для получения подарка."
        )
        
        await message.answer_photo(
            barcode['photo_file_id'],
            caption=caption
        )
    
    # После показа всех штрих-кодов можно пометить их как доставленные
    for barcode in barcodes:
        db.mark_barcode_delivered(barcode['id'])
    
    await message.answer("Все штрих-коды были показаны и помечены как доставленные.")