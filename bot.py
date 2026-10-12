import asyncio
import json
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# ⚠️ ВСТАВЬ СЮДА СВОЙ ТОКЕН ОТ BOTFATHER
TOKEN = "8662941832:AAFtBMudq2ZnVQLRq_Zap3Iu8tZNRUi_YZs"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

DATA_FILE = "user_data.json"


# --- РАБОТА С ХРАНИЛИЩЕМ (JSON) ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# --- СОСТОЯНИЯ (FSM) ---
class Form(StatesGroup):
    waiting_for_title = State()
    waiting_for_content = State()
    waiting_for_edit_select = State()
    waiting_for_edit_content = State()


# --- КЛАВИАТУРЫ ---
def get_main_menu_keyboard(user_id):
    data = load_data()
    user_notes = data.get(str(user_id), {})

    builder_inline = []
    # Кнопки со сохраненными пунктами
    for title in user_notes.keys():
        builder_inline.append(
            [
                InlineKeyboardButton(
                    text=f"📌 {title}", callback_data=f"show_{title}"
                )
            ]
        )

    inline_kb = (
        InlineKeyboardMarkup(inline_keyboard=builder_inline)
        if builder_inline
        else None
    )

    # Главное меню (Reply-кнопки снизу)
    reply_kb = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Добавить пункт"),
                KeyboardButton(text="🗑 Удалить пункт"),
            ],
            [
                KeyboardButton(text="✏️ Изменить пункт"),
                KeyboardButton(text="🏠 Главное меню"),
            ],
        ],
        resize_keyboard=True,
    )

    return inline_kb, reply_kb


# --- ХЕНДЛЕРЫ КОМАНД И МЕНЮ ---
@dp.message(CommandStart())
@dp.message(F.text == "🏠 Главное меню")
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    inline_kb, reply_kb = get_main_menu_keyboard(message.from_user.id)

    text = "👋 Добро пожаловать в менеджер закладок!\nВыбери нужный пункт из списка ниже или используй меню для управления:"
    if not inline_kb:
        text = "📭 Твой список пока пуст. Нажми «➕ Добавить пункт», чтобы создать первую закладку!"

    await message.answer(text, reply_markup=reply_kb)
    if inline_kb:
        await message.answer("📋 Твои сохраненные пункты:", reply_markup=inline_kb)


# --- ПОКАЗ СОДЕРЖИМОГО ПУНКТА ---
@dp.callback_query(F.data.startswith("show_"))
async def show_note_content(callback: types.CallbackQuery):
    title = callback.data.split("show_")[1]
    data = load_data()
    user_notes = data.get(str(callback.from_user.id), {})

    content = user_notes.get(title, "Пункт не найден.")
    await callback.message.answer(
        f"📌 **{title}**\n\n{content}", parse_mode="Markdown"
    )
    await callback.answer()


# --- ДОБАВЛЕНИЕ ПУНКТА ---
@dp.message(F.text == "➕ Добавить пункт")
async def add_start(message: types.Message, state: FSMContext):
    await state.set_state(Form.waiting_for_title)
    await message.answer(
        "📝 Введи **название** для нового пункта (это будет текст на кнопке):"
    )


@dp.message(Form.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(Form.waiting_for_content)
    await message.answer(
        "🔗 Отлично! Теперь отправь **текст или ссылку**, которую нужно сохранить:"
    )


@dp.message(Form.waiting_for_content)
async def process_content(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    title = user_data["title"]
    content = message.text

    data = load_data()
    user_id = str(message.from_user.id)
    if user_id not in data:
        data[user_id] = {}

    data[user_id][title] = content
    save_data(data)

    await state.clear()
    await message.answer(f"✅ Пункт **«{title}»** успешно сохранен!")
    await start_cmd(message, state)


# --- УДАЛЕНИЕ ПУНКТА ---
@dp.message(F.text == "🗑 Удалить пункт")
async def delete_start(message: types.Message):
    data = load_data()
    user_notes = data.get(str(message.from_user.id), {})

    if not user_notes:
        await message.answer("У тебя пока нет сохраненных пунктов для удаления.")
        return

    buttons = [
        [
            InlineKeyboardButton(
                text=f"❌ {title}", callback_data=f"del_{title}"
            )
        ]
        for title in user_notes.keys()
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери пункт, который хочешь удалить:", reply_markup=kb)


@dp.callback_query(F.data.startswith("del_"))
async def process_delete(callback: types.CallbackQuery):
    title = callback.data.split("del_")[1]
    data = load_data()
    user_id = str(callback.from_user.id)

    if user_id in data and title in data[user_id]:
        del data[user_id][title]
        save_data(data)
        await callback.message.answer(f"🗑 Пункт **«{title}»** удален.")
    else:
        await callback.message.answer("Ошибка: пункт не найден.")

    await callback.answer()


# --- ИЗМЕНЕНИЕ ПУНКТА ---
@dp.message(F.text == "✏️ Изменить пункт")
async def edit_start(message: types.Message):
    data = load_data()
    user_notes = data.get(str(message.from_user.id), {})

    if not user_notes:
        await message.answer("У тебя пока нет сохраненных пунктов для изменения.")
        return

    buttons = [
        [
            InlineKeyboardButton(
                text=f"✏️ {title}", callback_data=f"edit_{title}"
            )
        ]
        for title in user_notes.keys()
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери пункт, который хочешь изменить:", reply_markup=kb)


@dp.callback_query(F.data.startswith("edit_"))
async def process_edit_select(
    callback: types.CallbackQuery, state: FSMContext
):
    title = callback.data.split("edit_")[1]
    await state.update_data(edit_title=title)
    await state.set_state(Form.waiting_for_edit_content)

    await callback.message.answer(
        f"Введи новый текст/ссылку для пункта **«{title}»**:"
    )
    await callback.answer()


@dp.message(Form.waiting_for_edit_content)
async def process_edit_content(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    title = user_data["edit_title"]
    new_content = message.text

    data = load_data()
    user_id = str(message.from_user.id)

    if user_id in data and title in data[user_id]:
        data[user_id][title] = new_content
        save_data(data)
        await message.answer(f"✏️ Содержимое пункта **«{title}»** обновлено!")

    await state.clear()
    await start_cmd(message, state)


# --- ЗАПУСК БОТА ---
async def main():
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())