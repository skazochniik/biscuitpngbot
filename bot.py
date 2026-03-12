import tempfile
import shutil
import io
import os
import threading
from flask import Flask
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

BOT_TOKEN = os.getenv("BOT_TOKEN")


# Временное хранение файлов пользователей
user_images: dict[int, str] = {}

# веб сервер для Render
web_app = Flask(__name__)

@web_app.route("/")
def home():
    return "bot is alive"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)


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

    if document.file_size and document.file_size > 50 * 1024 * 1024:
        await message.reply_text("слишком огромный бисквит 🍪 максимум 50 MB")
        return

    user_id = update.effective_user.id

    temp_dir = tempfile.mkdtemp(prefix=f"pngbot_{user_id}_")
    input_path = os.path.join(temp_dir, "input.png")

    try:
        tg_file = await document.get_file()
        await tg_file.download_to_drive(custom_path=input_path)

        user_images[user_id] = input_path

        original_kb = os.path.getsize(input_path) / 1024

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
            f"бисквиты готовы к выпеканию\n"
            f"исходный размер: {original_kb:.1f} KB\n\n"
            f".・。.・゜✭・.・✫・゜・。\n"
            f"выбери размер уменьшения:",
            reply_markup=reply_markup,
        )

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def compress_to_target(input_path: str, target_kb: int) -> bytes:
    with Image.open(input_path) as original:
        if original.width * original.height > 40_000_000:
            return b""

        original = original.convert("RGBA")
        

        scales = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2]
        color_options = [256, 128, 64, 32, 16]

        best_result = None
        best_diff = float("inf")

        for scale in scales:
            new_width = max(1, int(original.width * scale))
            new_height = max(1, int(original.height * scale))

            resized = original.resize((new_width, new_height), Image.LANCZOS)

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

        return best_result if best_result is not None else b""


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    if not query.message:
        return

    await query.answer()

    user_id = query.from_user.id
    input_path = user_images.get(user_id)

    if not input_path or not os.path.exists(input_path):
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

    try:
        await query.message.reply_text("присую бисквиты..")

        result_bytes = compress_to_target(input_path, target_kb)

        if not result_bytes:
            await query.message.reply_text("не получилось спрессовать бисквит :(")
            return

        await query.message.reply_document(
            document=io.BytesIO(result_bytes),
            filename=f"compressed_{target_kb}kb.png",
            caption="вы спресовали бедных бисквитов",
        )

    finally:
        temp_dir = os.path.dirname(input_path)
        shutil.rmtree(temp_dir, ignore_errors=True)
        user_images.pop(user_id, None)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Отправь картинку как документ, не как фото."
    )


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not found")

    threading.Thread(target=run_web, daemon=True).start()
    
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    print("bot started")
    app.run_polling()


if __name__ == "__main__":
    main()

