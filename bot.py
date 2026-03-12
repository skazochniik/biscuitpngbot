import io
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = "8778458203:AAEH8n7IY7Og1QaAHM1FuaOV7hEX88XUINo"

# Временное хранение файлов пользователей
user_images: dict[int, bytes] = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "˚* ੈ✩‧₊💗* ੈ✩‧₊˚*\nбисквитик, кинь PNG файл"
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.document:
        return

    document = message.document
    filename = document.file_name or ""

    if not filename.lower().endswith(".png"):
        await message.reply_text("пришли именно PNG файл.")
        return

    tg_file = await document.get_file()
    data = await tg_file.download_as_bytearray()

    user_id = update.effective_user.id
    user_images[user_id] = bytes(data)

    original_kb = len(data) / 1024

    keyboard = [
        [
            InlineKeyboardButton("100 KB", callback_data="size_100"),
            InlineKeyboardButton("300 KB", callback_data="size_300"),
        ],
        [
            InlineKeyboardButton("500 KB", callback_data="size_500"),
            InlineKeyboardButton("1 MB", callback_data="size_1000"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply_text(
        f"бисквиты готовы к выпеканию\nисходный размер: {original_kb:.1f} KB\n\n.・。.・゜✭・.・✫・゜・。\nвыбери размер:",
        reply_markup=reply_markup,
    )


def compress_to_target(data: bytes, target_kb: int) -> bytes:
    """
    Пытается ужать бисквитов примерно до target_kb.
    Сначала пробует optimize, потом уменьшает размеры,
    потом уменьшает количество начинки.
    """
    with Image.open(io.BytesIO(data)) as original:
        original = original.convert("RGBA")

        # Несколько уровней уменьшения
        scales = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2]
        color_options = [256, 128, 64, 32, 16]

        best_result = None
        best_diff = float("inf")

        for scale in scales:
            new_width = max(1, int(original.width * scale))
            new_height = max(1, int(original.height * scale))

            resized = original.resize((new_width, new_height), Image.LANCZOS)

            # Вариант 1: обычный PNG
            output = io.BytesIO()
            resized.save(output, format="PNG", optimize=True)
            result = output.getvalue()
            size_kb = len(result) / 1024

            diff = abs(size_kb - target_kb)
            if diff < best_diff:
                best_diff = diff
                best_result = result

            if size_kb <= target_kb:
                return result

            # Вариант 2: палитровые PNG
            for colors in color_options:
                paletted = resized.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors)

                output = io.BytesIO()
                paletted.save(output, format="PNG", optimize=True)
                result = output.getvalue()
                size_kb = len(result) / 1024

                diff = abs(size_kb - target_kb)
                if diff < best_diff:
                    best_diff = diff
                    best_result = result

                if size_kb <= target_kb:
                    return result

        return best_result if best_result is not None else data


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    await query.answer()

    user_id = query.from_user.id
    data = user_images.get(user_id)

    if not data:
        await query.message.reply_text("Сначала отправь PNG файл.")
        return

    size_map = {
        "size_100": 100,
        "size_300": 300,
        "size_500": 500,
        "size_1000": 1000,
    }

    target_kb = size_map.get(query.data)
    if target_kb is None:
        await query.message.reply_text("Неизвестный размер.")
        return

    await query.message.reply_text("присую бисквиты..")

    result_bytes = compress_to_target(data, target_kb)

    original_kb = len(data) / 1024
    result_kb = len(result_bytes) / 1024
    saved_percent = 0.0

    if len(data) > 0:
        saved_percent = (1 - len(result_bytes) / len(data)) * 100

    target_label = "1 MB" if target_kb == 1000 else f"{target_kb} KB"

    await query.message.reply_document(
        document=io.BytesIO(result_bytes),
        filename=f"compressed_{target_kb}kb.png",
        caption="вы спресовали бедных бисквитов",
    )

    user_images.pop(user_id, None)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Отправь картинку как документ, не как фото."
    )


def main() -> None:
    if BOT_TOKEN == "ВСТАВЬ_СЮДА_СВОЙ_ТОКЕН":
        raise ValueError("Вставь свой токен в BOT_TOKEN")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("bot started")
    app.run_polling()


if __name__ == "__main__":
    main()