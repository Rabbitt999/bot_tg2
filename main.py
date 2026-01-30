import os
import tempfile
import json
import html
import telebot
from telebot import types
from telebot.types import Message

# ================== НАЛАШТУВАННЯ ==================
BOT_TOKEN = "8067473611:AAHaIRuXuCF_SCkiGkg-gfHf2zKPOkT_V9g"
ADMIN_IDS = [6974875043]  # Список адмінів для отримання повідомлень

MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB

# ================== ІНІЦІАЛІЗАЦІЯ БОТА ==================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Словник для зберігання тимчасових даних
user_states = {}


# ================== ФУНКЦІЯ ЕКРАНУВАННЯ HTML ==================
def escape_html(text: str) -> str:
    """
    Екранує спеціальні символи для HTML
    """
    if not text:
        return ""
    return html.escape(text)


# ================== ГЕНЕРАЦІЯ КЛАВІАТУР ==================
def get_main_menu_keyboard():
    """
    Створює головне меню для користувачів
    """
    keyboard = types.ReplyKeyboardMarkup(
        row_width=2,
        resize_keyboard=True,
        one_time_keyboard=False
    )

    btn1 = types.KeyboardButton("📤 Поділитися інформацією")
    btn2 = types.KeyboardButton("📢 Розмістити рекламу")

    keyboard.add(btn1, btn2)
    return keyboard


def get_cancel_keyboard():
    """
    Клавіатура для скасування дії
    """
    keyboard = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True
    )
    keyboard.add(types.KeyboardButton("❌ Скасувати"))
    return keyboard


# ================== ОБРОБКА КОМАНД ==================
@bot.message_handler(commands=['start'])
def handle_start(message: Message):
    """
    Обробка команди /start
    """
    welcome_text = (
        "🏠 <b>Головне меню</b>\n\n"
        "Оберіть одну з опцій:\n\n"
        "• 📤 <b>Поділитися інформацією</b> - надіслати новину чи інформацію для публікації\n"
        "• 📢 <b>Розмістити рекламу</b> - залишити заявку на розміщення реклами\n"
    )

    bot.send_message(
        message.chat.id,
        welcome_text,
        reply_markup=get_main_menu_keyboard()
    )


@bot.message_handler(commands=['menu'])
def handle_menu(message: Message):
    """
    Обробка команди /menu
    """
    if message.chat.id in user_states:
        user_states.pop(message.chat.id)

    handle_start(message)


@bot.message_handler(commands=['cancel'])
def handle_cancel(message: Message):
    """
    Обробка команди /cancel
    """
    if message.chat.id in user_states:
        user_states.pop(message.chat.id)

    bot.send_message(
        message.chat.id,
        "❌ Операція скасована.",
        reply_markup=get_main_menu_keyboard()
    )


# ================== ОБРОБКА ГОЛОВНОГО МЕНЮ ==================
@bot.message_handler(func=lambda message: message.text == "📤 Поділитися інформацією")
def handle_share_info(message: Message):
    """
    Обробка вибору "Поділитися інформацією"
    """
    info_text = (
        "📤 <b>Поділитися інформацією</b>\n\n"
        "Надішліть вашу інформацію (текст, фото, відео з описом), я передам адміну для перевірки та публікації.\n\n"
        "❗️ Надсилаючи матеріали, ви підтверджуєте згоду на їх публікацію в нашому Telegram-каналі.\n\n"
        "Для скасування натисніть кнопку '❌ Скасувати' або напишіть /cancel"
    )

    user_states[message.chat.id] = "waiting_info"

    bot.send_message(
        message.chat.id,
        info_text,
        reply_markup=get_cancel_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "📢 Розмістити рекламу")
def handle_advertise(message: Message):
    """
    Обробка вибору "Розмістити рекламу"
    """
    advertise_text = (
        "📢 <b>Розмістити рекламу</b>\n\n"
        "Опишіть коротко, що ви хочете прорекламувати в нашому каналі.\n\n"
        "Обв'язково, залиште ваші контактні дані (наприклад Telegram), щоб ми могли з вами зв'язатися.\n\n"
        "Для скасування натисніть кнопку '❌ Скасувати' або напишіть /cancel"
    )

    user_states[message.chat.id] = "waiting_ad"

    bot.send_message(
        message.chat.id,
        advertise_text,
        reply_markup=get_cancel_keyboard()
    )


@bot.message_handler(func=lambda message: message.text == "❌ Скасувати")
def handle_cancel_button(message: Message):
    """
    Обробка натискання кнопки "Скасувати"
    """
    handle_cancel(message)


# ================== ОБРОБКА СТАНІВ ==================
@bot.message_handler(
    func=lambda message: message.chat.id in user_states and user_states[message.chat.id] == "waiting_info",
    content_types=['text', 'photo', 'video', 'document']
)
def receive_info(message: Message):
    """
    Обробка інформації від користувача
    """
    if message.text and message.text == "/cancel":
        handle_cancel(message)
        return

    # Отримуємо текст та медіа
    text = message.text or message.caption or ""
    media_file = None
    media_type = None

    # Обробка фото
    if message.photo:
        media_type = "photo"
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_file.write(downloaded_file)
        temp_file.close()
        media_file = temp_file.name

    # Обробка відео
    elif message.video:
        # Перевірка розміру відео
        if message.video.file_size and message.video.file_size > MAX_VIDEO_SIZE:
            bot.send_message(
                message.chat.id,
                f"❌ Відео занадто велике ({message.video.file_size // (1024 * 1024)} МБ). "
                f"Максимальний розмір: {MAX_VIDEO_SIZE // (1024 * 1024)} МБ.\n"
                "Спробуйте стиснути відео або надіслати посилання на нього.",
                reply_markup=get_main_menu_keyboard()
            )
            user_states.pop(message.chat.id, None)
            return

        media_type = "video"
        file_info = bot.get_file(message.video.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_file.write(downloaded_file)
        temp_file.close()
        media_file = temp_file.name

    # Обробка документа (відео як документ)
    elif message.document and message.document.mime_type and 'video' in message.document.mime_type:
        # Перевірка розміру
        if message.document.file_size and message.document.file_size > MAX_VIDEO_SIZE:
            bot.send_message(
                message.chat.id,
                f"❌ Відео занадто велике ({message.document.file_size // (1024 * 1024)} МБ). "
                f"Максимальний розмір: {MAX_VIDEO_SIZE // (1024 * 1024)} МБ.\n"
                "Спробуйте стиснути відео або надіслати посилання на нього.",
                reply_markup=get_main_menu_keyboard()
            )
            user_states.pop(message.chat.id, None)
            return

        media_type = "video"
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        file_name = message.document.file_name or "video.mp4"
        if '.' in file_name:
            ext = '.' + file_name.split('.')[-1]
        else:
            ext = '.mp4'

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        temp_file.write(downloaded_file)
        temp_file.close()
        media_file = temp_file.name

    # Формуємо повідомлення для адмінів
    username = message.from_user.username or message.from_user.full_name
    user_info = f"👤 Від: @{username} (ID: {message.from_user.id})"

    escaped_text = escape_html(text) if text else '📁 Медіа без тексту'
    caption_text = f"{user_info}\n\n📤 Інформація:\n{escaped_text}"

    if media_type:
        caption_text += f"\n\n📁 Тип: {media_type.upper()}"

    # Надсилаємо повідомлення всім адмінам
    for admin_id in ADMIN_IDS:
        try:
            if media_file and os.path.exists(media_file) and os.path.getsize(media_file) > 0:
                if media_type == "photo":
                    with open(media_file, 'rb') as photo:
                        bot.send_photo(
                            admin_id,
                            photo,
                            caption=caption_text
                        )
                elif media_type == "video":
                    with open(media_file, 'rb') as video:
                        bot.send_video(
                            admin_id,
                            video,
                            caption=caption_text
                        )

                # Видаляємо тимчасовий файл після відправки
                try:
                    os.remove(media_file)
                except:
                    pass
            else:
                bot.send_message(
                    admin_id,
                    caption_text
                )
        except Exception as e:
            print(f"Не вдалося надіслати повідомлення адміну {admin_id}: {e}")

    # Відповідь користувачу
    bot.send_message(
        message.chat.id,
        "✅ Ваша інформація надіслана адміну для перевірки. Дякуємо!\n\n"
        "Меню знову доступне:",
        reply_markup=get_main_menu_keyboard()
    )

    # Очищаємо стан користувача
    user_states.pop(message.chat.id, None)


@bot.message_handler(
    func=lambda message: message.chat.id in user_states and user_states[message.chat.id] == "waiting_ad",
    content_types=['text', 'photo', 'video', 'document']
)
def receive_ad(message: Message):
    """
    Обробка реклами від користувача
    """
    if message.text and message.text == "/cancel":
        handle_cancel(message)
        return

    # Отримуємо текст та медіа
    text = message.text or message.caption or ""
    media_file = None
    media_type = None

    # Обробка фото
    if message.photo:
        media_type = "photo"
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
        temp_file.write(downloaded_file)
        temp_file.close()
        media_file = temp_file.name

    # Обробка відео
    elif message.video:
        # Перевірка розміру відео
        if message.video.file_size and message.video.file_size > MAX_VIDEO_SIZE:
            bot.send_message(
                message.chat.id,
                f"❌ Відео занадто велике ({message.video.file_size // (1024 * 1024)} МБ). "
                f"Максимальний розмір: {MAX_VIDEO_SIZE // (1024 * 1024)} МБ.\n"
                "Спробуйте стиснути відео або надіслати посилання на нього.",
                reply_markup=get_main_menu_keyboard()
            )
            user_states.pop(message.chat.id, None)
            return

        media_type = "video"
        file_info = bot.get_file(message.video.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        temp_file.write(downloaded_file)
        temp_file.close()
        media_file = temp_file.name

    # Формуємо повідомлення для адмінів
    username = message.from_user.username or message.from_user.full_name
    user_info = f"👤 Від: @{username} (ID: {message.from_user.id})"

    escaped_text = escape_html(text) if text else "📁 Медіа без тексту"
    admin_message = f"📢 Реклама:\n{user_info}\n\n{escaped_text}"

    if media_type:
        admin_message += f"\n\n📁 Тип медіа: {media_type.upper()}"

    # Надсилаємо повідомлення всім адмінам
    for admin_id in ADMIN_IDS:
        try:
            if media_file and os.path.exists(media_file) and os.path.getsize(media_file) > 0:
                if media_type == "photo":
                    with open(media_file, 'rb') as photo:
                        bot.send_photo(
                            admin_id,
                            photo,
                            caption=admin_message
                        )
                elif media_type == "video":
                    with open(media_file, 'rb') as video:
                        bot.send_video(
                            admin_id,
                            video,
                            caption=admin_message
                        )

                # Видаляємо тимчасовий файл після відправки
                try:
                    os.remove(media_file)
                except:
                    pass
            else:
                bot.send_message(
                    admin_id,
                    admin_message
                )
        except Exception as e:
            print(f"Не вдалося надіслати повідомлення адміну {admin_id}: {e}")

    # Відповідь користувачу
    bot.send_message(
        message.chat.id,
        "✅ Ваша заявка на рекламу прийнята!\n\n"
        "Адмін розгляне ваше повідомлення і зв'яжеться з вами в найближчий час.\n\n"
        "Будь лапа, не видаляйте і не блокуйте бота поки з вами не зв'яжиться адмін.\n\n"
        "Дякуємо, що обрали наш канал!\n\n"
        "Меню знову доступне:",
        reply_markup=get_main_menu_keyboard()
    )

    # Очищаємо стан користувача
    user_states.pop(message.chat.id, None)


# ================== ОБРОБКА ІНШИХ ПОВІДОМЛЕНЬ ==================
@bot.message_handler(func=lambda message: True)
def handle_other_messages(message: Message):
    """
    Обробка всіх інших повідомлень
    """
    # Якщо це команда, яку ми не обробили
    if message.text and message.text.startswith("/"):
        bot.send_message(
            message.chat.id,
            "ℹ️ Невідома команда. Використовуйте /menu для відкриття меню."
        )
    else:
        # Показуємо меню для будь-якого іншого повідомлення
        handle_start(message)


# ================== ЗАПУСК БОТА ==================
if __name__ == "__main__":
    print("🤖 Бот запущений!")
    print("📱 Користувацький бот для відправки інформації та реклами")
    print("📤 Функції: Поділитися інформацією, Розмістити рекламу")
    print(f"👑 Адміни для сповіщень: {len(ADMIN_IDS)} користувачів")

    bot.infinity_polling()
