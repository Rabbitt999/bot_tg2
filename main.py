import telebot
import requests
import json
import os
import time
import threading
from datetime import datetime, timedelta
from telebot import types

# ================== НАЛАШТУВАННЯ ==================
BOT_TOKEN = "8538688126:AAFSWM16hONLKwObwnujl-dPnqJ_yu5XLLU"
SERP_API_KEYS = ["5b17fc511645b27655b61507e9fb9c416f87c888a64e5b10e8552478051ff2e3"]
GROQ_API_KEY = "daabec6e0f5de6e9e5a1502f17a229f9"
ADMIN_ID = 6974875043
STARS_AMOUNT = 50
MAX_CART_ITEMS = 5

bot = telebot.TeleBot(BOT_TOKEN)

# Тимчасове сховище станів для репортів
user_states = {}

# ================== СИСТЕМА АНТИСПАМ ==================
user_clicks = {}
ERROR_COOLDOWN = {}
SEARCH_IN_PROGRESS = {}


def check_anti_spam(user_id):
    current_time = time.time()

    if user_id not in user_clicks:
        user_clicks[user_id] = {
            "count": 1,
            "first_click_time": current_time,
            "blocked_until": 0
        }
        return True, 0

    user_data = user_clicks[user_id]

    if current_time < user_data["blocked_until"]:
        remaining = int(user_data["blocked_until"] - current_time)
        return False, remaining

    if current_time - user_data["first_click_time"] > 30:
        user_data["count"] = 1
        user_data["first_click_time"] = current_time
        return True, 0

    user_data["count"] += 1

    if user_data["count"] > 10:
        user_data["blocked_until"] = current_time + 30
        user_data["count"] = 0
        return False, 30

    return True, 0


def can_send_error(user_id):
    current_time = time.time()
    if user_id not in ERROR_COOLDOWN:
        ERROR_COOLDOWN[user_id] = 0

    if current_time - ERROR_COOLDOWN[user_id] >= 600:
        ERROR_COOLDOWN[user_id] = current_time
        return True
    return False


# ================== СИСТЕМА ДАНИХ ==================
DB_FILE = "users_db.json"
CART_FILE = "user_carts.json"


def load_db():
    if not os.path.exists(DB_FILE):
        return {"total_searches_month": 0, "month": datetime.now().month, "year": datetime.now().year, "users": {}}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            current_month = datetime.now().month
            current_year = datetime.now().year
            if data.get("month") != current_month or data.get("year") != current_year:
                data["total_searches_month"] = 0
                data["month"] = current_month
                data["year"] = current_year
                save_db(data)
            return data
        except:
            return {"total_searches_month": 0, "month": datetime.now().month, "year": datetime.now().year, "users": {}}


def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_carts():
    """Завантажує кошики користувачів"""
    if not os.path.exists(CART_FILE):
        return {}
    with open(CART_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}


def save_carts(carts):
    """Зберігає кошики користувачів"""
    with open(CART_FILE, "w", encoding="utf-8") as f:
        json.dump(carts, f, indent=4, ensure_ascii=False)


def get_user_cart(uid):
    """Отримує кошик користувача"""
    carts = load_carts()
    uid = str(uid)
    if uid not in carts:
        carts[uid] = []
        save_carts(carts)
    return carts[uid]


def add_to_cart(uid, item):
    """Додає товар до кошика"""
    carts = load_carts()
    uid = str(uid)
    if uid not in carts:
        carts[uid] = []

    # Перевіряємо чи досягнуто ліміт
    if len(carts[uid]) >= MAX_CART_ITEMS:
        return "limit"

    # Перевіряємо чи товар вже є в кошику
    for existing_item in carts[uid]:
        if existing_item.get("link") == item.get("link"):
            return "exists"

    carts[uid].append(item)
    save_carts(carts)
    return "success"


def remove_from_cart(uid, item_index):
    """Видаляє товар з кошика за індексом"""
    carts = load_carts()
    uid = str(uid)
    if uid in carts and 0 <= item_index < len(carts[uid]):
        removed = carts[uid].pop(item_index)
        save_carts(carts)
        return removed
    return None


def get_user(uid, first_name="Користувач"):
    data = load_db()
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {
            "name": first_name,
            "premium_until": None,
            "searches_today": 0,
            "last_search_date": datetime.now().strftime("%Y-%m-%d"),
            "invited_count": 0,
            "total_searches": 0
        }
        save_db(data)
    return data["users"][uid]


def update_user(uid, user_data):
    """Оновлює дані користувача в базі"""
    data = load_db()
    uid = str(uid)
    if uid in data["users"]:
        data["users"][uid] = user_data
        save_db(data)
    return user_data


def add_premium_days(uid, days):
    data = load_db()
    uid = str(uid)
    if uid in data["users"]:
        user = data["users"][uid]
        now = datetime.now()
        if user.get("premium_until"):
            try:
                current_until = datetime.strptime(user["premium_until"], "%Y-%m-%d %H:%M")
                base_date = current_until if current_until > now else now
            except:
                base_date = now
        else:
            base_date = now
        new_date = base_date + timedelta(days=days)
        user["premium_until"] = new_date.strftime("%Y-%m-%d %H:%M")
        save_db(data)

        try:
            bot.send_message(int(uid), f"🎉 Вітаємо! Преміум активовано на {days} днів!")
        except:
            pass


def get_premium_time_left(premium_until_str):
    if not premium_until_str:
        return None

    try:
        until = datetime.strptime(premium_until_str, "%Y-%m-%d %H:%M")
        now = datetime.now()

        if until <= now:
            return None

        diff = until - now
        days = diff.days
        hours = diff.seconds // 3600
        minutes = (diff.seconds % 3600) // 60

        if days >= 1:
            return f"⏱️{days}д {hours}г"
        else:
            return f"⏱️{hours}г {minutes}хв"
    except:
        return None


# ================== ДОПОМІЖНІ ФУНКЦІЇ ==================

def get_progress_bar(percent):
    filled_length = int(percent // 20)
    bar = "🟩" * filled_length + "⬜" * (5 - filled_length)
    return f"{percent}% {bar}"


def format_rating(rating):
    """Форматує рейтинг товару для відображення"""
    if rating and rating > 0:
        return f"⭐ {rating}"
    return "⭐ Відсутній"


# ================== ЛОГІКА GROQ (AI) ==================

def get_refined_query(user_input):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    prompt = f"""
    Користувач шукає товар: "{user_input}"
    Твоє завдання: Зроби ідеальний короткий пошуковий запит для Google Shopping (марка, модель).
    Відповідь надішли СУВОРО у форматі JSON:
    {{"query": "виправлений запит"}}
    """

    data = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        res_json = response.json()['choices'][0]['message']['content']
        return json.loads(res_json).get("query", user_input)
    except:
        return user_input


# ================== ЛОГІКА ПОШУКУ ==================

def parse_price(price_str):
    try:
        return float("".join(filter(str.isdigit, price_str)))
    except:
        return 9999999


def extract_rating(item):
    """Витягує рейтинг з товару"""
    # Спробуємо різні поля де може бути рейтинг
    rating = item.get("rating", 0)
    if rating:
        try:
            return float(rating)
        except:
            pass

    # Перевіряємо в полі extensions
    extensions = item.get("extensions", [])
    for ext in extensions:
        if "rating" in ext.lower():
            try:
                # Шукаємо число в рядку
                import re
                numbers = re.findall(r"(\d+\.?\d*)", ext)
                if numbers:
                    return float(numbers[0])
            except:
                pass

    return 0


def search_product(query):
    url = "https://serpapi.com/search.json"
    params = {"engine": "google_shopping", "q": query, "hl": "uk", "gl": "ua", "api_key": SERP_API_KEYS[0]}
    try:
        res = requests.get(url, params=params).json()
        raw_results = res.get("shopping_results", [])
        processed = []
        for item in raw_results:
            rating = extract_rating(item)
            processed.append({
                "title": item.get("title", ""),
                "price": item.get("price", "Ціну не вказано"),
                "extracted_price": parse_price(item.get("price", "0")),
                "link": item.get("link") or item.get("product_link"),
                "source": item.get("source", "Магазин"),
                "rating": rating,
                "rating_text": format_rating(rating)
            })
        processed.sort(key=lambda x: x["extracted_price"])
        return processed[:5]
    except:
        return []


# ================== КЛАВІАТУРА ==================

def get_main_menu(uid):
    """Повертає список кнопок для головного меню"""
    buttons = ["👤 Мій профіль", "⚙️ Повідомити про помилку"]
    if uid == ADMIN_ID:
        buttons.append("📊 Адмін Статистика")
    return buttons


def create_main_keyboard(uid):
    """Створює клавіатуру з кнопкою пошуку та іншими кнопками"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)

    # Спочатку додаємо кнопку пошуку
    markup.add(types.KeyboardButton("🔍 Пошук товарів"))

    # Потім додаємо інші кнопки в рядках по 2
    other_buttons = get_main_menu(uid)
    if other_buttons:
        # Якщо кнопок більше 2, розбиваємо на ряди
        if len(other_buttons) == 2:
            markup.row(
                types.KeyboardButton(other_buttons[0]),
                types.KeyboardButton(other_buttons[1])
            )
        elif len(other_buttons) == 3:
            markup.row(
                types.KeyboardButton(other_buttons[0]),
                types.KeyboardButton(other_buttons[1])
            )
            markup.row(types.KeyboardButton(other_buttons[2]))

    return markup


# ================== ОБРОБНИКИ ==================

@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    first_name = message.from_user.first_name
    db = load_db()
    is_new = str(uid) not in db["users"]
    user = get_user(uid, first_name)

    can_click, block_time = check_anti_spam(uid)
    if not can_click:
        bot.send_message(uid, f"⚠️ Ви відправили забагато повідомлень! Зачекайте {block_time} секунд.")
        return

    args = message.text.split()
    if is_new and len(args) > 1 and args[1].isdigit():
        referrer_id = args[1]
        if referrer_id != str(uid) and referrer_id in db["users"]:
            add_premium_days(referrer_id, 5)
            add_premium_days(uid, 3)
            db = load_db()
            db["users"][referrer_id]["invited_count"] += 1
            save_db(db)
            try:
                bot.send_message(referrer_id,
                                 f"🎊 По вашому посиланню прийшов {first_name}! Вам нараховано 5 днів Premium.")
            except:
                pass
            bot.send_message(uid, f"🎁 Ви отримали 3 діб Premium за запрошення!", parse_mode="HTML")

    bot.send_message(
        uid,
        "🔎 Натисніть кнопку пошуку, щоб знайти товар за найкращою ціною.",
        reply_markup=create_main_keyboard(uid)
    )


@bot.message_handler(func=lambda m: m.text == "🔍 Пошук товарів")
def search_button_handler(message):
    uid = message.from_user.id

    can_click, block_time = check_anti_spam(uid)
    if not can_click:
        bot.send_message(uid, f"⚠️ Ви відправили забагато повідомлень! Зачекайте {block_time} секунд.")
        return

    # Встановлюємо стан пошуку для користувача
    user_states[uid] = "waiting_for_search"

    # Створюємо інлайн кнопку для скасування
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Відмінити пошук", callback_data="cancel_search"))

    bot.send_message(
        uid,
        "🔎 Напишіть назву товару для пошуку найкращої ціни.\n\n"
        "Натисніть /cancel щоб відмінити пошук.",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data == "cancel_search")
def cancel_search_callback(call):
    uid = call.from_user.id

    # Видаляємо стан пошуку
    if uid in user_states:
        del user_states[uid]

    bot.edit_message_text(
        "❌ Пошук скасовано.",
        call.message.chat.id,
        call.message.message_id
    )

    bot.send_message(uid, "Оберіть дію:", reply_markup=create_main_keyboard(uid))


@bot.message_handler(commands=['cancel'])
def cancel_command(message):
    uid = message.from_user.id

    # Видаляємо стан пошуку
    if uid in user_states:
        del user_states[uid]

    bot.send_message(uid, "❌ Пошук скасовано.", reply_markup=create_main_keyboard(uid))


@bot.message_handler(func=lambda m: m.text == "👤 Мій профіль")
def profile(message):
    uid = message.from_user.id

    can_click, block_time = check_anti_spam(uid)
    if not can_click:
        bot.send_message(uid, f"⚠️ Ви відправили забагато повідомлень! Зачекайте {block_time} секунд.")
        return

    uid_str = str(uid)
    user = get_user(uid, message.from_user.first_name)
    cart = get_user_cart(uid)

    prem_status = "Неактивний❌"
    prem_time_left = None

    if user["premium_until"]:
        try:
            if datetime.strptime(user["premium_until"], "%Y-%m-%d %H:%M") > datetime.now():
                prem_status = "Активний✅"
                prem_time_left = get_premium_time_left(user["premium_until"])
        except:
            pass

    ref_link = f"https://t.me/{(bot.get_me()).username}?start={uid_str}"
    profile_text = (
        f"👤<b>Профіль</b> — {user['name']}\n\n"
        f"💎<b>Преміум</b> — {prem_status}\n"
    )

    if prem_time_left:
        profile_text += f"<blockquote>{prem_time_left}</blockquote>\n"

    profile_text += (
        f"\n🔍<b>Кількість пошуків:</b> {user['total_searches']}\n\n"
        f"🛒<b>Товарів у кошику:</b> {len(cart)}/{MAX_CART_ITEMS}\n\n"
        f"👥<b>Запрошених користувачів:</b> {user['invited_count']}\n"
        f"<blockquote>• Запрошуйте друзів та знайомих через ваше реферальне посилання та отримуйте 5 діб преміуму\n"
        f"• 1 запрошений користувач = 5 діб преміуму</blockquote>\n"
        f"Ваше реферальне посилання:\n<code>{ref_link}</code>"
    )

    # Додаємо кнопки "Купити Premium" та "Мій кошик" під текстом профілю
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💎 Купити Premium", callback_data="buy_premium_from_profile"),
        types.InlineKeyboardButton("🛒 Мій кошик", callback_data="show_cart_from_profile")
    )

    bot.send_message(message.chat.id, profile_text, parse_mode="HTML", disable_web_page_preview=True,
                     reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data == "buy_premium_from_profile")
def buy_premium_from_profile(call):
    uid = call.from_user.id

    can_click, block_time = check_anti_spam(uid)
    if not can_click:
        bot.answer_callback_query(call.id, f"⚠️ Зачекайте {block_time} секунд!", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(f"Оплатити {STARS_AMOUNT} ⭐️", callback_data="pay_stars")
    )

    bot.edit_message_text(
        "💎 Оплата Premium на 30 днів:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data == "show_cart_from_profile")
def show_cart_from_profile(call):
    uid = call.from_user.id

    can_click, block_time = check_anti_spam(uid)
    if not can_click:
        bot.answer_callback_query(call.id, f"⚠️ Зачекайте {block_time} секунд!", show_alert=True)
        return

    cart = get_user_cart(uid)

    if not cart:
        bot.edit_message_text(
            "🛒 Ваш кошик порожній",
            call.message.chat.id,
            call.message.message_id
        )
        return

    text = f"🛒 <b>Ваш кошик</b> ({len(cart)}/{MAX_CART_ITEMS} товарів):\n\n"

    markup = types.InlineKeyboardMarkup(row_width=1)

    for i, item in enumerate(cart[:5]):
        short_title = item['title'][:30] + "..." if len(item['title']) > 30 else item['title']
        markup.add(types.InlineKeyboardButton(
            f"{i + 1}. {short_title} - {item['price']}",
            callback_data=f"cart_item_{i}"
        ))

    if len(cart) > 5:
        text += f"<i>Показано 5 з {len(cart)} товарів</i>\n"

    # Додаємо кнопку для повернення до профілю
    markup.add(types.InlineKeyboardButton("🔙 Назад до профілю", callback_data="back_to_profile"))

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data == "back_to_profile")
def back_to_profile(call):
    uid = call.from_user.id

    uid_str = str(uid)
    user = get_user(uid)
    cart = get_user_cart(uid)

    prem_status = "Неактивний❌"
    prem_time_left = None

    if user["premium_until"]:
        try:
            if datetime.strptime(user["premium_until"], "%Y-%m-%d %H:%M") > datetime.now():
                prem_status = "Активний✅"
                prem_time_left = get_premium_time_left(user["premium_until"])
        except:
            pass

    ref_link = f"https://t.me/{(bot.get_me()).username}?start={uid_str}"

    profile_text = (
        f"👤<b>Профіль</b> — {user['name']}\n\n"
        f"💎<b>Преміум</b> — {prem_status}\n"
    )

    if prem_time_left:
        profile_text += f"<blockquote>{prem_time_left}</blockquote>\n"

    profile_text += (
        f"\n🔍<b>Кількість пошуків:</b> {user['total_searches']}\n\n"
        f"🛒<b>Товарів у кошику:</b> {len(cart)}/{MAX_CART_ITEMS}\n\n"
        f"👥<b>Запрошених користувачів:</b> {user['invited_count']}\n"
        f"<blockquote>• Запрошуйте друзів та знайомих через ваше реферальне посилання та отримуйте 5 діб преміуму\n"
        f"• 1 запрошений користувач = 5 діб преміуму</blockquote>\n"
        f"Ваше реферальне посилання:\n<code>{ref_link}</code>"
    )

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("💎 Купити Premium", callback_data="buy_premium_from_profile"),
        types.InlineKeyboardButton("🛒 Мій кошик", callback_data="show_cart_from_profile")
    )

    bot.edit_message_text(
        profile_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=markup
    )


@bot.message_handler(func=lambda m: m.text == "⚙️ Повідомити про помилку")
def report_bug(message):
    uid = message.from_user.id

    can_click, block_time = check_anti_spam(uid)
    if not can_click:
        bot.send_message(uid, f"⚠️ Ви відправили забагато повідомлень! Зачекайте {block_time} секунд.")
        return

    if not can_send_error(uid):
        bot.send_message(uid, "⚠️ Ви вже повідомляли про помилку нещодавно. Спробуйте через 10 хвилин.")
        return

    user_states[uid] = "waiting_for_report"
    bot.send_message(message.chat.id, "🛠 Напишіть вашу проблему або надішліть фото помилки:")


@bot.message_handler(content_types=['text', 'photo'],
                     func=lambda m: user_states.get(m.from_user.id) == "waiting_for_report")
def handle_report(message):
    uid = message.from_user.id

    can_click, block_time = check_anti_spam(uid)
    if not can_click:
        bot.send_message(uid, f"⚠️ Ви відправили забагато повідомлень! Зачекайте {block_time} секунд.")
        return

    admin_text = f"🚨 <b>НОВИЙ РЕПОРТ</b> від {uid}\n"
    if message.content_type == 'text':
        admin_text += f"Опис: {message.text}"
        bot.send_message(ADMIN_ID, admin_text, parse_mode="HTML")
    elif message.content_type == 'photo':
        bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=admin_text, parse_mode="HTML")
    user_states[uid] = None
    bot.send_message(message.chat.id, "✅ Дякуємо! Репорт надіслано.")


@bot.message_handler(func=lambda m: m.text == "📊 Адмін Статистика" and m.from_user.id == ADMIN_ID)
def admin_stat(message):
    uid = message.from_user.id

    can_click, block_time = check_anti_spam(uid)
    if not can_click:
        bot.send_message(uid, f"⚠️ Ви відправили забагато повідомлень! Зачекайте {block_time} секунд.")
        return

    db = load_db()
    total_u = len(db["users"])
    carts = load_carts()
    total_cart_items = sum(len(items) for items in carts.values())

    bot.send_message(message.chat.id,
                     f"📊 Всього користувачів: {total_u}\n"
                     f"📦 Товарів у кошиках: {total_cart_items}\n"
                     f"🔍 Пошуків за місяць: {db['total_searches_month']}")


# ================== ГОЛОВНА ЛОГІКА ПОШУКУ ==================

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_for_search", content_types=['text'])
def handle_search_logic(message):
    uid = message.from_user.id

    can_click, block_time = check_anti_spam(uid)
    if not can_click:
        bot.send_message(uid, f"⚠️ Ви відправили забагато повідомлень! Зачекайте {block_time} секунд.")
        return

    if uid in SEARCH_IN_PROGRESS and SEARCH_IN_PROGRESS[uid]:
        bot.send_message(uid, "⚠️ Зачекайте, попередній пошук ще триває!")
        return

    # Видаляємо стан пошуку після отримання запиту
    if uid in user_states:
        del user_states[uid]

    # Отримуємо актуальні дані користувача
    user = get_user(uid, message.from_user.first_name)
    db = load_db()

    now_date = datetime.now().strftime("%Y-%m-%d")
    if user["last_search_date"] != now_date:
        user["searches_today"] = 0
        user["last_search_date"] = now_date

    is_premium = False
    if user["premium_until"]:
        try:
            if datetime.strptime(user["premium_until"], "%Y-%m-%d %H:%M") > datetime.now():
                is_premium = True
        except:
            pass

    limit = 10 if is_premium else 3
    if user["searches_today"] >= limit:
        bot.send_message(message.chat.id, f"❌ Ліміт вичерпано ({limit}/{limit} пошуків).")
        return

    SEARCH_IN_PROGRESS[uid] = True

    try:
        search_query_text = message.text
        status_msg = bot.send_message(message.chat.id, f"🔍 Шукаю {search_query_text}\n{get_progress_bar(20)}")

        refined_query = get_refined_query(search_query_text)
        bot.edit_message_text(f"🔍 Шукаю {refined_query}\n{get_progress_bar(40)}", message.chat.id,
                              status_msg.message_id)

        results = search_product(refined_query)
        bot.edit_message_text(f"🔍 Шукаю {refined_query}\n{get_progress_bar(60)}", message.chat.id,
                              status_msg.message_id)

        if not results:
            bot.edit_message_text(f"❌ Нічого не знайдено за запитом: {refined_query}", message.chat.id,
                                  status_msg.message_id)
            return

        bot.edit_message_text(f"🔍 Шукаю {refined_query}\n{get_progress_bar(80)}", message.chat.id,
                              status_msg.message_id)

        res_text = f"🔎 <b>Результати пошуку</b>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        for i, item in enumerate(results, 1):
            res_text += f"{i}️⃣ <b>{item['source']}</b> — <b>{item['price']}</b>\n"
            res_text += f"📦 {item['title'][:60]}...\n"
            if item['rating_text']:
                res_text += f"{item['rating_text']}\n"
            res_text += f"<a href='{item['link']}'>👉 Перейти</a>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"

        bot.edit_message_text(f"🔍 Шукаю {refined_query}\n{get_progress_bar(100)}", message.chat.id,
                              status_msg.message_id)
        time.sleep(0.4)

        # Оновлюємо дані користувача
        user["searches_today"] += 1
        user["total_searches"] += 1
        db["total_searches_month"] += 1

        # Зберігаємо оновлені дані
        save_db(db)

        # Додаємо кнопку "Додати в кошик" під результатами
        markup = types.InlineKeyboardMarkup(row_width=1)

        # Зберігаємо результати в тимчасовому стані для додавання в кошик
        user_states[f"last_search_{uid}"] = results

        markup.add(types.InlineKeyboardButton(
            "🛒 Додати в кошик",
            callback_data="show_add_to_cart"
        ))

        bot.edit_message_text(
            res_text,
            message.chat.id,
            status_msg.message_id,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup
        )
    finally:
        SEARCH_IN_PROGRESS[uid] = False


# ================== ОПЛАТА ТА КОШИК ==================

@bot.callback_query_handler(func=lambda c: c.data == "show_add_to_cart")
def show_add_to_cart(call):
    uid = call.from_user.id
    last_results = user_states.get(f"last_search_{uid}", [])

    if not last_results:
        bot.answer_callback_query(call.id, "❌ Спочатку виконайте пошук", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, item in enumerate(last_results):
        short_title = item['title'][:30] + "..." if len(item['title']) > 30 else item['title']
        rating_text = f" ⭐ {item['rating']}" if item['rating'] else ""
        markup.add(types.InlineKeyboardButton(
            f"{i + 1}. {short_title} - {item['price']}{rating_text}",
            callback_data=f"add_to_cart_{i}"
        ))

    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_results"))

    bot.edit_message_text(
        "🛒 Виберіть товар для додавання в кошик:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("add_to_cart_"))
def add_to_cart_callback(call):
    uid = call.from_user.id
    item_index = int(call.data.replace("add_to_cart_", ""))

    last_results = user_states.get(f"last_search_{uid}", [])

    if 0 <= item_index < len(last_results):
        item = last_results[item_index]
        cart = get_user_cart(uid)

        if len(cart) >= MAX_CART_ITEMS:
            bot.answer_callback_query(call.id, f"❌ Кошик переповнений! Максимум {MAX_CART_ITEMS} товарів",
                                      show_alert=True)
            return

        result = add_to_cart(uid, item)
        if result == "success":
            bot.answer_callback_query(call.id, f"✅ Товар додано в кошик! ({len(cart) + 1}/{MAX_CART_ITEMS})",
                                      show_alert=True)
        elif result == "exists":
            bot.answer_callback_query(call.id, "ℹ️ Товар вже є в кошику", show_alert=True)
        elif result == "limit":
            bot.answer_callback_query(call.id, f"❌ Кошик переповнений! Максимум {MAX_CART_ITEMS} товарів",
                                      show_alert=True)
    else:
        bot.answer_callback_query(call.id, "❌ Помилка додавання", show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data == "back_to_results")
def back_to_results(call):
    uid = call.from_user.id
    last_results = user_states.get(f"last_search_{uid}", [])

    if not last_results:
        bot.answer_callback_query(call.id, "❌ Результати пошуку застаріли", show_alert=True)
        return

    res_text = f"🔎 <b>Результати пошуку</b>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    for i, item in enumerate(last_results, 1):
        res_text += f"{i}️⃣ <b>{item['source']}</b> — <b>{item['price']}</b>\n"
        res_text += f"📦 {item['title'][:60]}...\n"
        if item['rating_text']:
            res_text += f"{item['rating_text']}\n"
        res_text += f"<a href='{item['link']}'>👉 Перейти</a>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🛒 Додати в кошик", callback_data="show_add_to_cart"))

    bot.edit_message_text(
        res_text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("cart_item_"))
def show_cart_item(call):
    uid = call.from_user.id
    item_index = int(call.data.replace("cart_item_", ""))

    cart = get_user_cart(uid)

    if 0 <= item_index < len(cart):
        item = cart[item_index]

        item_text = f"📦 <b>{item['title']}</b>\n\n"
        item_text += f"🏷 <b>Ціна:</b> {item['price']}\n"
        item_text += f"🏪 <b>Магазин:</b> {item['source']}\n"
        if item['rating_text']:
            item_text += f"{item['rating_text']}\n"
        item_text += f"🔗 <b>Посилання:</b> <a href='{item['link']}'>Перейти</a>"

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("❌ Видалити з кошика", callback_data=f"remove_from_cart_{item_index}"),
            types.InlineKeyboardButton("🔙 Назад до кошика", callback_data="back_to_cart_from_item")
        )

        bot.edit_message_text(
            item_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup
        )
    else:
        bot.answer_callback_query(call.id, "❌ Товар не знайдено", show_alert=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("remove_from_cart_"))
def remove_from_cart_callback(call):
    uid = call.from_user.id
    item_index = int(call.data.replace("remove_from_cart_", ""))

    removed = remove_from_cart(uid, item_index)

    if removed:
        bot.answer_callback_query(call.id, "✅ Товар видалено з кошика", show_alert=True)
        # Показуємо оновлений кошик
        show_cart_after_remove(call)
    else:
        bot.answer_callback_query(call.id, "❌ Помилка видалення", show_alert=True)


def show_cart_after_remove(call):
    uid = call.from_user.id
    cart = get_user_cart(uid)

    if not cart:
        bot.edit_message_text(
            "🛒 Ваш кошик порожній",
            call.message.chat.id,
            call.message.message_id
        )
        return

    text = f"🛒 <b>Ваш кошик</b> ({len(cart)}/{MAX_CART_ITEMS} товарів):\n\n"

    markup = types.InlineKeyboardMarkup(row_width=1)

    for i, item in enumerate(cart[:5]):
        short_title = item['title'][:30] + "..." if len(item['title']) > 30 else item['title']
        markup.add(types.InlineKeyboardButton(
            f"{i + 1}. {short_title} - {item['price']}",
            callback_data=f"cart_item_{i}"
        ))

    if len(cart) > 5:
        text += f"<i>Показано 5 з {len(cart)} товарів</i>\n"

    # Додаємо кнопку для повернення до профілю
    markup.add(types.InlineKeyboardButton("🔙 Назад до профілю", callback_data="back_to_profile"))

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data == "back_to_cart_from_item")
def back_to_cart_from_item(call):
    show_cart_after_remove(call)


@bot.callback_query_handler(func=lambda c: c.data == "pay_stars")
def pay_stars(call):
    uid = call.from_user.id

    can_click, block_time = check_anti_spam(uid)
    if not can_click:
        bot.answer_callback_query(call.id, f"⚠️ Зачекайте {block_time} секунд!", show_alert=True)
        return

    bot.send_invoice(
        call.message.chat.id,
        title="Premium доступ (Зірки)",
        description="Активація преміум функцій на 30 днів через зірки",
        invoice_payload="premium_subscription",
        provider_token="",
        currency="XTR",
        prices=[types.LabeledPrice(label="Premium", amount=STARS_AMOUNT)]
    )


@bot.pre_checkout_query_handler(func=lambda q: True)
def checkout(q):
    bot.answer_pre_checkout_query(q.id, ok=True)


@bot.message_handler(content_types=['successful_payment'])
def pay_ok(message):
    uid = message.from_user.id

    can_click, block_time = check_anti_spam(uid)
    if not can_click:
        bot.send_message(uid, f"⚠️ Ви відправили забагато повідомлень! Зачекайте {block_time} секунд.")
        return

    add_premium_days(uid, 30)
    bot.send_message(message.chat.id, "🎉 Вітаємо! Преміум активовано через зірки.")


if __name__ == "__main__":
    print("🚀 Бот запущено. Доступна тільки оплата зірками.")
    bot.infinity_polling()
