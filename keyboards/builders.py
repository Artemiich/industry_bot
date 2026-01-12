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


def get_cart_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Узгартириш", callback_data="add_more")
    builder.button(text="✅ Жунатиш", callback_data="confirm_order")
    builder.adjust(1)
    return builder.as_markup()


# --- ИЗМЕНЕНИЯ ЗДЕСЬ ---
def get_batch_keyboard(items: list, current_data: dict, back_level: int, unit: str = "шт"):
    builder = InlineKeyboardBuilder()

    for item in items:
        qty = current_data.get(item)

        # Если число введено, добавляем единицу измерения (шт или кг)
        # Пример: " : 50 шт"
        if qty is not None:
            qty_text = f" : {qty} {unit}"
        else:
            qty_text = " : -"

        # Обрезаем value для безопасности
        safe_value = item[:30]

        builder.button(
            text=f"{item}{qty_text}",
            callback_data=MenuCB(level=999, value=safe_value, action="edit")
        )

    # Кнопка сохранения (Оставил текст как у тебя на скрине или стандартный)
    builder.button(text="💾 Cаклаш", callback_data=MenuCB(level=999, value="save", action="save"))
    builder.button(text="🔙 Назад", callback_data=MenuCB(level=back_level, value="back", action="nav"))

    builder.adjust(1)
    return builder.as_markup()