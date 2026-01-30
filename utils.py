import re
from datetime import datetime, date, timedelta
from typing import Optional, Tuple

def parse_birthday(text: str) -> Optional[date]:
    """Парсит дату рождения из текста"""
    patterns = [
        r'(\d{1,2})\.(\d{1,2})\.(\d{4})',  # DD.MM.YYYY
        r'(\d{1,2})\.(\d{1,2})',  # DD.MM (без года)
        r'(\d{1,2})/(\d{1,2})/(\d{4})',  # DD/MM/YYYY
        r'(\d{1,2})-(\d{1,2})-(\d{4})',  # DD-MM-YYYY
    ]
    
    for pattern in patterns:
        match = re.match(pattern, text)
        if match:
            groups = match.groups()
            if len(groups) == 3:  # С годом
                day, month, year = map(int, groups)
                try:
                    return date(year, month, day)
                except ValueError:
                    continue
            elif len(groups) == 2:  # Без года (используем год рождения 1900 как placeholder)
                day, month = map(int, groups)
                try:
                    return date(1900, month, day)  # Год будет игнорироваться при сравнении
                except ValueError:
                    continue
    return None

def calculate_next_birthday(birthday: date) -> Tuple[date, int]:
    """Рассчитывает следующий день рождения и сколько дней осталось"""
    today = date.today()
    current_year = today.year
    
    # Пробуем день рождения в этом году
    next_bd = birthday.replace(year=current_year)
    
    # Если день рождения в этом году уже прошел, берем следующий год
    if next_bd < today:
        next_bd = birthday.replace(year=current_year + 1)
    
    days_until = (next_bd - today).days
    return next_bd, days_until

def format_birthday_message(user: dict, addresses: dict = None, wishes: str = None) -> str:
    """Форматирует сообщение о дне рождения"""
    message = f"🎉 <b>Скоро свой день рождения празднует {user['full_name']}!</b>\n\n"
    
    next_bd, days_until = calculate_next_birthday(
        datetime.strptime(user['birthday'], '%Y-%m-%d').date()
    )
    
    message += f"📅 Дата: {user['birthday']}\n"
    message += f"⏳ До дня рождения: {days_until} дней\n\n"
    
    if addresses:
        message += "🏠 <b>Адреса для отправки подарков:</b>\n"
        if 'ozon' in addresses and addresses['ozon']:
            message += f"📦 OZON: <code>{addresses['ozon']}</code>\n"
        if 'yandex' in addresses and addresses['yandex']:
            message += f"📦 Яндекс Маркет: <code>{addresses['yandex']}</code>\n"
        if 'wildberries' in addresses and addresses['wildberries']:
            message += f"📦 Wildberries: <code>{addresses['wildberries']}</code>\n"
        message += "\n"
    
    if wishes:
        message += f"💭 <b>Пожелания именинника:</b>\n{wishes}\n\n"
    
    message += "🎁 Не забудьте подготовить подарок!"
    return message

def validate_addresses(addresses: dict) -> bool:
    """Проверяет, что указан хотя бы один адрес"""
    return any(address for address in addresses.values() if address)