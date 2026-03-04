from aiogram.fsm.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_birthday = State()
    waiting_for_participation = State()

class ProfileStates(StatesGroup):
    editing_name = State()
    editing_birthday = State()
    editing_participation = State()
    editing_address = State()
    editing_wishes = State()

class BirthdayStates(StatesGroup):
    waiting_for_addresses = State()
    waiting_for_wishes = State()
    waiting_for_delay = State()
    ready_to_receive = State()

class BarcodeStates(StatesGroup):
    waiting_for_receiver = State()
    waiting_for_photo = State()

class AdminStates(StatesGroup):
    editing_user = State()
    deleting_user = State()
    broadcast = State()
