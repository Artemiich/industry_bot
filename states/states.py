from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.callback_data import CallbackData


class RegistrationState(StatesGroup):
    waiting_for_phone = State()


class OrderFlow(StatesGroup):
    making_order = State()
    waiting_for_quantity = State()

    # НОВОЕ: Ждем число для конкретной ячейки в матрице
    waiting_for_batch_qty = State()


# Добавляем поле 'action' для управления матрицей
# action может быть: 'nav' (навигация), 'edit' (редактирование числа), 'save' (сохранение пачки)
class MenuCB(CallbackData, prefix="m"):
    level: int
    value: str
    action: str = "nav"