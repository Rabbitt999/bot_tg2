import telebot
from serpapi import GoogleSearch

# Налаштування
SERP_API_KEY = "5b17fc511645b27655b61507e9fb9c416f87c888a64e5b10e8552478051ff2e3"
TELEGRAM_TOKEN = "8067473611:AAHaIRuXuCF_SCkiGkg-gfHf2zKPOkT_V9g"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Список дозволених магазинів
ALLOWED_SHOPS = ["rozetka", "prom", "foxtrot", "allo", "yabko", "comfy", "citrus"]

def get_best_prices(query):
    params = {
        "engine": "google_shopping",
        "q": query,
        "location": "Ukraine",
        "hl": "uk",
        "gl": "ua",
        "api_key": SERP_API_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()
    
    # Словник для зберігання найкращої ціни для кожного магазину (щоб уникнути дублікатів)
    best_offers = {}
    
    if "shopping_results" in results:
        for res in results["shopping_results"]:
            # 1. Перевірка стану (тільки нове)
            condition = res.get("condition", "new").lower()
            if any(word in condition for word in ["used", "б/у", "вжива", "refurbished"]):
                continue

            # 2. Фільтр по магазинах
            source = res.get("source", "").lower()
            found_shop = None
            for shop in ALLOWED_SHOPS:
                if shop in source:
                    found_shop = shop
                    break
            
            if not found_shop:
                continue # Пропускаємо магазин, якщо його немає в списку

            # 3. Обробка ціни
            price_str = res.get("price", "0")
            clean_price = "".join(filter(str.isdigit, price_str))
            numeric_price = int(clean_price) if clean_price else 9999999

            # 4. Зберігаємо тільки найдешевшу пропозицію від кожного магазину
            if found_shop not in best_offers or numeric_price < best_offers[found_shop]['numeric_price']:
                best_offers[found_shop] = {
                    "shop": found_shop.capitalize(),
                    "title": res.get("title"),
                    "price": price_str,
                    "numeric_price": numeric_price,
                    "link": res.get("link")
                }

    # Сортуємо за ціною
    sorted_offers = sorted(best_offers.values(), key=lambda x: x['numeric_price'])
    
    return sorted_offers[:5] # Повертаємо топ-5

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привіт! Я знайду найнижчі ціни на **нову** техніку в топ-магазинах (Rozetka, Comfy, Alo тощо).\n\nВведіть назву товару:")

@bot.message_handler(func=lambda message: True)
def handle_search(message):
    query = message.text
    msg = bot.send_message(message.chat.id, f"🔎 Шукаю `{query}` у перевірених магазинах...")

    try:
        results = get_best_prices(query)
        
        if not results:
            bot.edit_message_text("На жаль, у вказаних магазинах нічого не знайдено. Спробуйте уточнити назву.", message.chat.id, msg.message_id)
            return

        response_text = f"✅ **Найдешевші нові пропозиції для:**\n_{query}_\n\n"
        
        for i, res in enumerate(results, 1):
            response_text += f"{i}. 🏪 **{res['shop']}**\n"
            response_text += f"💰 Ціна: `{res['price']}`\n"
            response_text += f"📦 {res['title'][:60]}...\n"
            response_text += f"🔗 [ПОСИЛАННЯ НА ТОВАР]({res['link']})\n\n"

        bot.edit_message_text(response_text, message.chat.id, msg.message_id, parse_mode="Markdown", disable_web_page_preview=True)
    
    except Exception as e:
        print(f"Error: {e}")
        bot.edit_message_text("❌ Сталася помилка. Спробуйте ще раз за хвилину.", message.chat.id, msg.message_id)

bot.polling(none_stop=True)
