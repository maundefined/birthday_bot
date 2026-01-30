from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

import states
from database import Database
from keyboards import get_main_menu, get_participation_type_keyboard
from utils import parse_birthday

router = Router()
db = Database()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    
    if user:
        await message.answer(
            f"👋 С возвращением, {user['full_name']}!\n"
            f"Используй меню ниже для навигации.",
            reply_markup=get_main_menu()
        )
        await state.clear()
    else:
        await message.answer(
            "👋 Привет! Я бот для управления днями рождения в вашем сообществе.\n\n"
            "Для начала давай зарегистрируем тебя.\n"
            "Введи свое имя:"
        )
        await state.set_state(states.RegistrationStates.waiting_for_name)

# Обработчик и команды /help, и кнопки "Помощь"
@router.message(Command("help"))
@router.message(F.text == "❓ Помощь")
async def cmd_help(message: Message):
    help_text = (
        "🤖 <b>Помощь по боту:</b>\n\n"
        "📅 <b>Мой профиль</b> - просмотр и редактирование твоих данных\n"
        "🎁 <b>Ближайшие дни рождения</b> - список предстоящих праздников\n"
        "📦 <b>Отправить штрих-код</b> - отправить штрих-код подарка\n\n"
        "🎉 <b>Как это работает:</b>\n"
        "1. Заполни свой профиль (имя, дата рождения, адреса)\n"
        "2. За 10 дней до дня рождения бот запросит у тебя адреса ПВЗ\n"
        "3. Бот уведомит других участников о твоем дне рождения\n"
        "4. В день получения подарков ты получишь штрих-коды от друзей\n\n"
        "🔄 Ты можешь изменить свои данные в любое время!"
    )
    await message.answer(help_text, parse_mode="html")

@router.message(states.RegistrationStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("Пожалуйста, введи корректное имя (минимум 2 символа):")
        return
    
    await state.update_data(full_name=name)
    await message.answer(
        f"Отлично, {name}!\n\n"
        "Теперь введи свою дату рождения в формате ДД.ММ.ГГГГ\n"
        "Например: 15.05.1990\n"
        "(Если пожелаешь, год можно не вводить)"
    )
    await state.set_state(states.RegistrationStates.waiting_for_birthday)

@router.message(states.RegistrationStates.waiting_for_birthday)
async def process_birthday(message: Message, state: FSMContext):
    birthday = parse_birthday(message.text)
    
    if not birthday:
        await message.answer(
            "Неверный формат даты. Пожалуйста, введи дату в формате ДД.ММ.ГГГГ:\n"
            "Например: 15.05.1990"
        )
        return
    
    await state.update_data(birthday=birthday.strftime('%Y-%m-%d'))
    await message.answer(
        "Теперь выбери тип участия:",
        reply_markup=get_participation_type_keyboard()
    )
    await state.set_state(states.RegistrationStates.waiting_for_participation)

@router.callback_query(states.RegistrationStates.waiting_for_participation, F.data.startswith("participation_"))
async def process_participation(callback: CallbackQuery, state: FSMContext):
    participation_type = callback.data.replace("participation_", "")
    data = await state.get_data()
    
    # Сохраняем пользователя в базу данных
    db.add_user(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=data['full_name'],
        birthday=data['birthday'],
        participation_type=participation_type
    )
    
    await callback.message.edit_text(
        "✅ Регистрация завершена!\n\n"
        f"👤 Имя: {data['full_name']}\n"
        f"📅 День рождения: {data['birthday']}\n"
        f"🎁 Тип участия: {'Только дарить' if participation_type == 'give_only' else 'Дарить и получать'}\n\n"
        "Теперь ты можешь:\n"
        "1. Заполнить адреса ПВЗ в профиле\n"
        "2. Указать пожелания к подаркам\n"
        "3. Смотреть ближайшие дни рождения",
        reply_markup=None
    )
    
    await callback.message.answer(
        "Используй меню ниже для навигации:",
        reply_markup=get_main_menu()
    )
    
    await state.clear()
    await callback.answer()