from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from Database.db import get_user, add_user
from keyboards.reply import get_contact_kb
# ИМПОРТИРУЕМ НОВУЮ КЛАВИАТУРУ И ДАННЫЕ
from keyboards.builders import get_menu_keyboard
from utils.config import MENU_DATA
from states.states import RegistrationState

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)

    # Генерация главного меню (уровень 0 -> ведет на уровень 1)
    # Берем список продуктов (keys) из нашего конфига
    main_menu_items = list(MENU_DATA.keys())
    main_kb = get_menu_keyboard(items=main_menu_items, next_level=1, current_level=0)

    if user:
        await message.answer(f"Привет, {user[1]}! Выберите направление:", reply_markup=main_kb)
    else:
        await message.answer(
            "Добро пожаловать! Для начала работы нам нужен ваш номер телефона.",
            reply_markup=get_contact_kb()
        )
        await state.set_state(RegistrationState.waiting_for_phone)


@router.message(RegistrationState.waiting_for_phone, F.contact)
async def process_phone(message: types.Message, state: FSMContext):
    contact = message.contact
    await add_user(message.from_user.id, message.from_user.full_name, contact.phone_number)

    # То же самое, генерируем меню после успешной регистрации
    main_menu_items = list(MENU_DATA.keys())
    main_kb = get_menu_keyboard(items=main_menu_items, next_level=1, current_level=0)

    await state.clear()
    await message.answer(
        "Регистрация успешна! ✅\nТеперь вы можете вводить данные.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await message.answer("Выберите направление:", reply_markup=main_kb)