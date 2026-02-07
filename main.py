import telebot
import requests

# ================== НАЛАШТУВАННЯ ==================
BOT_TOKEN = "8067473611:AAHaIRuXuCF_SCkiGkg-gfHf2zKPOkT_V9g"
SERP_API_KEY = "5b17fc511645b27655b61507e9fb9c416f87c888a64e5b10e8552478051ff2e3"

bot = telebot.TeleBot(BOT_TOKEN)

# Список дозволених магазинів
ALLOWED_SHOPS = ["rozetka", "prom", "foxtrot", "alo", "yablko", "comfy"]

# ================== ПОШУК ТОВАРУ ==================
def search_product(query):
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_shopping",
        "q": query,
        "hl": "uk",
        "gl": "ua",
        "api_key": SERP_API_KEY
    }

    response = requests.get(url, params=params)
    data = response.json()

    results = []

    if "shopping_results" not in data:
        return results

    seen_shops = set()

    for item in data["shopping_results"]:
        # Тільки нові товари
        condition = item.get("condition", "").lower()
        if condition and condition != "new":
            continue

        title = item.get("title", "No title")
        price = item.get("price", "N/A")

        # Беремо правильний лінк
        link = item.get("link") or item.get("product_link") or item.get("merchant_link") or ""
        source = item.get("source", "Unknown shop")

        # Переводимо назву магазину в нижній регістр
        source_lower = source.lower()

        # Фільтруємо лише дозволені магазини
        if not any(shop in source_lower for shop in ALLOWED_SHOPS):
            continue

        # Не повторювати магазини
        if source_lower in seen_shops:
            continue
        seen_shops.add(source_lower)

        # Фільтр Б/У і Refurbished
        if "бу" in title.lower() or "used" in title.lower() or "refurb" in title.lower():
            continue

        results.append({
            "title": title,
            "price": price,
            "link": link,
            "source": source
        })

    return results

# ================== ЦІНА → FLOAT ==================
def parse_price(price_str):
    try:
        return float(price_str.replace("₴", "").replace("грн", "").replace(" ", "").replace(",", "."))
    except:
        return 9999999

# ================== /start ==================
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "🔎 Напиши назву товару (наприклад: iPhone 15 Pro)\n"
        "Я знайду де дешевше в Україні серед Rozetka, Prom, Foxtrot, Alo, Yablko та Comfy."
    )

# ================== ПОШУК ==================
@bot.message_handler(func=lambda message: True)
def handle_search(message):
    query = message.text
    bot.send_message(message.chat.id, f"🔍 Шукаю: {query}...")

    results = search_product(query)

    if not results:
        bot.send_message(message.chat.id, "❌ Нічого не знайдено серед дозволених магазинів")
        return

    # Сортуємо по ціні
    results.sort(key=lambda x: parse_price(x["price"]))

    text = f"📱 {query}\n\n💸 Пропозиції:\n"

    for item in results:
        text += f"{item['source']}\n{item['link']}\n\n"

    bot.send_message(message.chat.id, text)

# ================== ЗАПУСК ==================
print("✅ Bot started...")
bot.polling(none_stop=True)
