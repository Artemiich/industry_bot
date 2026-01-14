import os
from datetime import datetime
from aiogram import Router, types, Bot, F
from aiogram.fsm.context import FSMContext
from Database.db import add_order, get_user
from states.states import MenuCB, OrderFlow
from keyboards.builders import get_menu_keyboard, get_cart_keyboard, get_batch_keyboard
from utils.config import MENU_DATA, SHIFTS, TEXT_FIELDS

router = Router()


# --- ФУНКЦИЯ ПОДГОТОВКИ СПИСКА ---
def flatten_stage_data(stage, stage_data, category=None):
    items = []
    if "items" in stage_data: return stage_data["items"]

    if stage == "Декор":
        if "sizes" in stage_data and "quality" in stage_data:
            sizes = stage_data["sizes"]
            quality = stage_data["quality"]
            for s in sizes:
                for q in quality:
                    items.append(f"{s} | {q}")
            return items

    if "groups" in stage_data and isinstance(stage_data["groups"], list) and "quality" in stage_data:
        groups = stage_data["groups"]
        quality = stage_data["quality"]
        for g in groups:
            for q in quality:
                items.append(f"{g} | {q}")
        return items

    if "groups" in stage_data and isinstance(stage_data["groups"], dict):
        if category and category in stage_data["groups"]:
            return stage_data["groups"][category]

    return []


# --- 1. НАВИГАЦИЯ ---
@router.callback_query(MenuCB.filter(F.action == "nav"))
async def menu_navigation(call: types.CallbackQuery, callback_data: MenuCB, state: FSMContext):
    level = callback_data.level
    value = callback_data.value

    if level == 1 and value != "back":
        await state.update_data(product=value)
    elif level == 2 and value != "back":
        await state.update_data(shift=value)
    elif level == 3 and value != "back":
        await state.update_data(stage=value)
    elif level == 4 and value != "back":
        await state.update_data(category=value)

    if value != "back":
        await state.update_data(batch_temp={})

    data = await state.get_data()
    text, kb = "", None

    # ЗАЩИТА ОТ СБОЯ
    if level > 0 and not data.get("product"):
        await call.message.edit_text("🔄 Бот обновлен. Начните заново:",
                                     reply_markup=get_menu_keyboard(list(MENU_DATA.keys()), 1, 0))
        return

    # LEVEL 0: Продукт
    if level == 0:
        text = "🏭 Выберите продукт:"
        kb = get_menu_keyboard(list(MENU_DATA.keys()), 1, 0)

    # LEVEL 1: Смена
    elif level == 1:
        text = f"📦 Продукт: <b>{data.get('product')}</b>\n🕒 Выберите смену:"
        kb = get_menu_keyboard(SHIFTS, 2, 1)

    # LEVEL 2: Отдел
    elif level == 2:
        prod = data.get("product")
        text = f"📦 {prod} | 🕒 {data.get('shift')}\n⚙️ Выберите отдел:"
        items = list(MENU_DATA[prod]["stages"].keys())
        kb = get_menu_keyboard(items, 3, 2)

    # LEVEL 3: РАЗВИЛКА
    elif level == 3:
        prod = data.get("product")
        stage = data.get("stage")
        stage_data = MENU_DATA[prod]["stages"][stage]

        # Декор -> Кнопки
        if stage == "Декор":
            text = f"🎨 <b>{stage}</b>\nВыберите цвет:"
            groups = stage_data["groups"]
            kb = get_menu_keyboard(groups, 4, 3)
            await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            return

        # Резкага -> Кнопки
        if "groups" in stage_data and isinstance(stage_data["groups"], dict):
            groups = list(stage_data["groups"].keys())
            text = f"📂 <b>{stage}</b>\nВыберите категорию:"
            kb = get_menu_keyboard(groups, 4, 3)
            await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            return

        # Миксер/Цехдан -> Матрица
        await state.update_data(category=None)
        all_items = flatten_stage_data(stage, stage_data)
        await show_matrix(call, state, items=all_items, parent_name=stage, back_level=2)
        return

    # LEVEL 4: МАТРИЦА ПОСЛЕ КАТЕГОРИИ
    elif level == 4:
        prod = data.get("product")
        stage = data.get("stage")
        cat = data.get("category")
        stage_data = MENU_DATA[prod]["stages"][stage]

        all_items = flatten_stage_data(stage, stage_data, category=cat)
        await show_matrix(call, state, items=all_items, parent_name=cat, back_level=3)
        return

    if text and kb:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# --- ОТОБРАЖЕНИЕ МАТРИЦЫ ---
async def show_matrix(call: types.CallbackQuery, state: FSMContext, items: list, parent_name: str, back_level: int):
    data = await state.get_data()
    cart = data.get('cart', [])
    prod = data.get('product')
    shift = data.get('shift')
    stage = data.get('stage')
    category_state = data.get('category')

    # Флаг: True = Редактирование, False = Добавление
    is_edit_mode = data.get('is_edit_mode', False)

    batch_temp = {}
    items_to_show = []

    # --- ЛОГИКА ФИЛЬТРАЦИИ ---
    for item_key in items:
        # Определяем, как этот ключ выглядит в БД (Category/SubCategory)
        target_cat = None
        target_sub = None

        if category_state:
            target_cat = category_state
            target_sub = item_key
        elif " | " in item_key:
            parts = item_key.split(" | ")
            target_cat = parts[0]
            target_sub = parts[1]
        else:
            target_cat = item_key
            target_sub = None

        # Проверяем, есть ли уже в корзине
        in_cart = False
        cart_value = None

        for cart_item in cart:
            if (cart_item['product'] == prod and
                    cart_item['shift'] == shift and
                    cart_item['stage'] == stage and
                    cart_item['category'] == target_cat and
                    cart_item['sub_category'] == target_sub):

                in_cart = True
                if cart_item.get('is_text_field'):
                    cart_value = cart_item['sub_category']
                elif not cart_item.get('is_empty'):
                    cart_value = cart_item['quantity']
                break

        # ЕСЛИ РЕЖИМ ДОБАВЛЕНИЯ (Қўшиш)
        if not is_edit_mode:
            # Если товар УЖЕ в корзине -> СКРЫВАЕМ ЕГО
            if in_cart:
                continue
                # Если нет в корзине -> ПОКАЗЫВАЕМ
            items_to_show.append(item_key)

        # ЕСЛИ РЕЖИМ РЕДАКТИРОВАНИЯ (Ўзгартириш)
        else:
            # Показываем ВСЕ
            items_to_show.append(item_key)
            # И подгружаем значения
            if in_cart and cart_value is not None:
                batch_temp[item_key] = cart_value

    await state.update_data(batch_temp=batch_temp)
    await state.update_data(
        matrix_context={"items": items_to_show, "parent_name": parent_name, "back_level": back_level})

    unit = "кг" if stage == "Миксер" else "шт"
    full_title = f"{prod} | {shift} | {stage}"
    if back_level == 3: full_title += f" | {parent_name}"

    mode_text = "(Қўшиш режими)" if not is_edit_mode else "(Ўзгартириш режими)"

    # Если в режиме добавления всё уже выбрано
    if not items_to_show and not is_edit_mode:
        text = f"📝 <b>{full_title}</b>\n\n✅ Все позиции из этого раздела уже добавлены.\nНажмите <b>«Назад»</b> или перейдите в <b>«Узгартириш»</b>, чтобы изменить."
    else:
        text = (f"📝 <b>{full_title}</b> {mode_text}\n\n👇 Введите данные:\nВ конце нажмите <b>💾 Сақлаш</b>.")

    kb = get_batch_keyboard(items_to_show, batch_temp, back_level, unit=unit)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# --- 2. РЕДАКТИРОВАНИЕ ---
@router.callback_query(MenuCB.filter(F.action == "edit"))
async def matrix_edit_handler(call: types.CallbackQuery, callback_data: MenuCB, state: FSMContext):
    item_name = callback_data.value
    await state.update_data(current_editing_item=item_name)
    data = await state.get_data()
    stage = data.get('stage')

    is_text_field = item_name in TEXT_FIELDS

    if is_text_field:
        prompt = f"📝 Ёзинг (Словами) для:\n<b>{item_name}</b>"
    else:
        unit = "кг" if stage == "Миксер" else "шт"
        prompt = f"🔢 Введите количество ({unit}) для:\n<b>{item_name}</b>"

    msg = await call.message.answer(prompt, parse_mode="HTML")
    await state.update_data(menu_msg_id=call.message.message_id, prompt_msg_id=msg.message_id)
    await state.set_state(OrderFlow.waiting_for_batch_qty)
    await call.answer()


# --- 3. ПОЛУЧЕНИЕ ЦИФРЫ ---
@router.message(OrderFlow.waiting_for_batch_qty)
async def receive_batch_qty(message: types.Message, state: FSMContext, bot: Bot):
    try:
        await message.delete()
    except:
        pass
    data = await state.get_data()
    try:
        await bot.delete_message(message.chat.id, data["prompt_msg_id"])
    except:
        pass

    item_name = data.get("current_editing_item")
    is_text_field = item_name in TEXT_FIELDS
    value_to_save = None

    if is_text_field:
        value_to_save = message.text
    else:
        if message.text.isdigit(): value_to_save = int(message.text)

    if value_to_save is not None:
        batch_temp = data.get("batch_temp", {})
        batch_temp[item_name] = value_to_save
        await state.update_data(batch_temp=batch_temp)

    ctx = data.get("matrix_context")
    stage = data.get('stage')
    unit = "кг" if stage == "Миксер" else "шт"
    new_kb = get_batch_keyboard(ctx["items"], data.get("batch_temp", {}), ctx["back_level"], unit=unit)
    try:
        await bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=data["menu_msg_id"],
                                            reply_markup=new_kb)
    except:
        pass
    await state.set_state(OrderFlow.making_order)


# --- 4. СОХРАНЕНИЕ ---
@router.callback_query(MenuCB.filter(F.action == "save"))
async def save_batch_handler(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    batch_temp = data.get("batch_temp", {})
    ctx = data.get("matrix_context")

    # Флаг режима: True=Перезапись, False=Суммирование
    is_edit_mode = data.get('is_edit_mode', False)

    if not batch_temp:
        await call.answer("⚠️ Пусто!", show_alert=True)
        return

    cart = data.get('cart', [])
    prod = data.get('product')
    shift = data.get('shift')
    stage = data.get('stage')
    category_state = data.get('category')
    items_list = ctx["items"]

    for item_key in items_list:
        if item_key not in batch_temp: continue

        val = batch_temp.get(item_key)

        if val is not None:
            final_val = val
            is_empty = False
        else:
            final_val = 0
            is_empty = True

        if category_state:
            cat_db = category_state
            sub_db = item_key
        elif " | " in item_key:
            parts = item_key.split(" | ")
            cat_db = parts[0]
            sub_db = parts[1]
        else:
            cat_db = item_key
            sub_db = None

        is_text = item_key in TEXT_FIELDS
        # Для текста всегда перезапись
        qty_db = final_val if not is_text else 1
        sub_db_final = sub_db
        if is_text and not is_empty: sub_db_final = f"{final_val}"

        new_item = {
            'product': prod,
            'shift': shift,
            'stage': stage,
            'category': cat_db,
            'sub_category': sub_db_final,
            'quantity': qty_db,
            'is_empty': is_empty,
            'is_text_field': is_text
        }

        # --- ГЛАВНАЯ ЛОГИКА ОБНОВЛЕНИЯ ---
        found = False
        for i, existing_item in enumerate(cart):
            if (existing_item['product'] == new_item['product'] and
                    existing_item['shift'] == new_item['shift'] and
                    existing_item['stage'] == new_item['stage'] and
                    existing_item['category'] == new_item['category'] and
                    existing_item['sub_category'] == new_item['sub_category']):

                # Если режим "Изменить" или текст -> ПЕРЕЗАПИСЬ
                if is_edit_mode or is_text:
                    cart[i] = new_item
                # Если режим "Добавить" -> СУММИРОВАНИЕ (на всякий случай, хотя кнопки скрыты)
                else:
                    if not existing_item['is_empty'] and not new_item['is_empty']:
                        cart[i]['quantity'] += new_item['quantity']
                    elif existing_item['is_empty'] and not new_item['is_empty']:
                        cart[i] = new_item

                found = True
                break

        if not found:
            cart.append(new_item)

    await state.update_data(cart=cart, batch_temp={}, category=None)

    current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
    current_shift = shift if shift else (cart[0]['shift'] if cart else "-")

    summary_lines = []
    counter = 1
    for item in cart:
        if item.get('is_empty'): continue

        if item.get('is_text_field'):
            val_display = f"📝 {item['sub_category']}"
        else:
            unit = "кг" if item['stage'] == "Миксер" else "шт"
            val_display = f"<b>{item['quantity']} {unit}</b>"

        sub_cat_print = item['sub_category']
        if item.get('is_text_field'): sub_cat_print = ""
        sub_text = f" | {sub_cat_print}" if sub_cat_print else ""

        line = f"{counter}. {item['stage']} | {item['category']}{sub_text} — {val_display}"
        summary_lines.append(line)
        counter += 1

    summary_text = "\n".join(summary_lines)
    if not summary_text: summary_text = "Пусто"

    total_msg = (
        f"🛒 <b>Сизнинг корзинангиз:</b>\n"
        f"🕒 Смена: <b>{current_shift}</b>\n"
        f"📅 {current_time}\n\n"
        f"{summary_text}\n\n"
        f"💾 <b>Сақланди!</b> Давом етамизми ёки жунатасизми?"
    )

    await call.message.edit_text(total_msg, reply_markup=get_cart_keyboard(), parse_mode="HTML")


# --- 5. ОТПРАВКА ---
@router.callback_query(F.data == "confirm_order")
async def confirm_order_handler(call: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    cart = data.get('cart', [])
    user_info = await get_user(call.from_user.id)
    if not cart: return

    current_time = datetime.now().strftime("%d.%m.%Y %H:%M")
    current_shift = cart[0]['shift'] if cart else "-"

    report_lines = []
    for item in cart:
        if item.get('is_empty'): continue

        await add_order(call.from_user.id, item, item['quantity'])

        if item.get('is_text_field'):
            val_display = f"📝 {item['sub_category']}"
        else:
            unit = "кг" if item['stage'] == "Миксер" else "шт"
            val_display = f"{item['quantity']} {unit}"

        sub_cat_print = item['sub_category']
        if item.get('is_text_field'): sub_cat_print = ""
        sub_text = f" | <b>{sub_cat_print}</b>" if sub_cat_print else ""

        line = f"🔸 {item['product']} | {item['stage']} | {item['category']}{sub_text} — {val_display}"
        report_lines.append(line)

    if not report_lines:
        await call.message.edit_text("⚠️ Пустой отчет.")
        return

    admin_id = os.getenv("ADMIN_ID")
    if admin_id:
        full_report = (
                f"🔥 <b>Ишлаб чиқариш ҳисоботи</b>\n"
                f"📅 Сана: {current_time}\n"
                f"👤 {user_info[1]} ({user_info[2]})\n"
                f"🕒 Смена: <b>{current_shift}</b>\n"
                f"➖➖➖➖➖➖➖➖\n"
                + "\n".join(report_lines)
        )
        try:
            await bot.send_message(admin_id, full_report, parse_mode="HTML")
        except:
            pass

    final_user_text = "\n".join(report_lines)
    await call.message.edit_text(
        f"✅ <b>Хисобот муваффақиятли юборилди!</b>\n"
        f"📅 {current_time}\n\n"
        f"📋 <b>Юборилган рўйхат:</b>\n"
        f"{final_user_text}",
        parse_mode="HTML"
    )
    await call.message.answer("Главное меню:", reply_markup=get_menu_keyboard(list(MENU_DATA.keys()), 1, 0))
    await state.clear()


# --- 6. ДОБАВИТЬ НОВОЕ (ЧИСТЫЙ ЛИСТ) ---
@router.callback_query(F.data == "add_new")
async def add_new_handler(call: types.CallbackQuery, state: FSMContext):
    # Выключаем показ старых цифр (Будет чисто)
    await state.update_data(is_edit_mode=False)
    await state.update_data(batch_temp={})

    data = await state.get_data()
    prod = data.get('product')
    stage = data.get('stage')
    category = data.get('category')

    if not prod or not stage:
        await call.message.edit_text("🏭 Выберите продукт:",
                                     reply_markup=get_menu_keyboard(list(MENU_DATA.keys()), 1, 0))
        await state.set_state(OrderFlow.making_order)
        return

    stage_data = MENU_DATA[prod]["stages"][stage]

    # Если уже в категории -> остаемся
    if category:
        all_items = flatten_stage_data(stage, stage_data, category=category)
        await show_matrix(call, state, items=all_items, parent_name=category, back_level=3)
        return

    # Если это Миксер/Цехдан -> остаемся
    if "items" in stage_data or ("groups" in stage_data and isinstance(stage_data["groups"], list)):
        all_items = flatten_stage_data(stage, stage_data)
        await show_matrix(call, state, items=all_items, parent_name=stage, back_level=2)
        return

    # Иначе (Декор/Резкага без выбранной категории) -> Выбор категории
    if stage == "Декор":
        groups = stage_data["groups"]
        kb = get_menu_keyboard(groups, 4, 3)
        await call.message.edit_text(f"🎨 <b>{stage}</b>\nВыберите цвет:", reply_markup=kb, parse_mode="HTML")
    elif "groups" in stage_data and isinstance(stage_data["groups"], dict):
        groups = list(stage_data["groups"].keys())
        kb = get_menu_keyboard(groups, 4, 3)
        await call.message.edit_text(f"📂 <b>{stage}</b>\nВыберите категорию:", reply_markup=kb, parse_mode="HTML")

    await state.set_state(OrderFlow.making_order)


# --- 7. ИЗМЕНИТЬ (ГРУЗИМ СТАРЫЕ ЦИФРЫ) ---
@router.callback_query(F.data == "edit_current")
async def edit_current_handler(call: types.CallbackQuery, state: FSMContext):
    # Включаем режим показа старого
    await state.update_data(is_edit_mode=True)

    data = await state.get_data()
    prod = data.get('product')
    stage = data.get('stage')
    category = data.get('category')

    if not prod or not stage:
        await add_new_handler(call, state)
        return

    stage_data = MENU_DATA[prod]["stages"][stage]

    if category:
        all_items = flatten_stage_data(stage, stage_data, category=category)
        await show_matrix(call, state, items=all_items, parent_name=category, back_level=3)
        return

    if "items" in stage_data or ("groups" in stage_data and isinstance(stage_data["groups"], list)):
        all_items = flatten_stage_data(stage, stage_data)
        await show_matrix(call, state, items=all_items, parent_name=stage, back_level=2)
        return

    if stage == "Декор":
        groups = stage_data["groups"]
        kb = get_menu_keyboard(groups, 4, 3)
        await call.message.edit_text(f"🎨 <b>{stage}</b>\nВыберите цвет для изменения:", reply_markup=kb,
                                     parse_mode="HTML")
    elif "groups" in stage_data and isinstance(stage_data["groups"], dict):
        groups = list(stage_data["groups"].keys())
        kb = get_menu_keyboard(groups, 4, 3)
        await call.message.edit_text(f"📂 <b>{stage}</b>\nВыберите категорию для изменения:", reply_markup=kb,
                                     parse_mode="HTML")

    await state.set_state(OrderFlow.making_order)