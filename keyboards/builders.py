from aiogram.utils.keyboard import InlineKeyboardBuilder
from states.states import MenuCB


def get_menu_keyboard(items: list, next_level: int, current_level: int):
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.button(text=item, callback_data=MenuCB(level=next_level, value=item[:20], action="nav"))

    if current_level > 0:
        back_level = current_level - 1
        builder.button(text="🔙 Назад", callback_data=MenuCB(level=back_level, value="back", action="nav"))

    builder.adjust(2)
    return builder.as_markup()


# --- ОБНОВЛЕННАЯ КЛАВИАТУРА КОРЗИНЫ ---
def get_cart_keyboard():
    builder = InlineKeyboardBuilder()

    # Кнопка 1: Добавить ДРУГОЙ товар -> Ведет в начало
    builder.button(text="➕ Добавить", callback_data="add_new")

    # Кнопка 2: Изменить ЭТОТ товар -> Ведет назад в матрицу
    builder.button(text="📝 Ўзгартириш", callback_data="edit_current")

    # Кнопка 3: Отправить
    builder.button(text="✅ Жунатиш", callback_data="confirm_order")

    builder.adjust(2, 1)
    return builder.as_markup()


# --------------------------------------

def get_batch_keyboard(items: list, current_data: dict, back_level: int, unit: str = "шт"):
    builder = InlineKeyboardBuilder()

    for item in items:
        val = current_data.get(item)

        if val is not None:
            if isinstance(val, int):
                val_text = f" : {val} {unit}"
            else:
                val_str = str(val)
                if len(val_str) > 10: val_str = val_str[:10] + "..."
                val_text = f" : {val_str}"
        else:
            val_text = " : -"

        safe_value = item[:30]

        builder.button(
            text=f"{item}{val_text}",
            callback_data=MenuCB(level=999, value=safe_value, action="edit")
        )

    builder.button(text="💾 Сақлаш", callback_data=MenuCB(level=999, value="save", action="save"))
    builder.button(text="🔙 Назад", callback_data=MenuCB(level=back_level, value="back", action="nav"))

    builder.adjust(1)
    return builder.as_markup()