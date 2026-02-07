import telebot
from serpapi import GoogleSearch

# Налаштування
SERP_API_KEY = "5b17fc511645b27655b61507e9fb9c416f87c888a64e5b10e8552478051ff2e3"
TELEGRAM_TOKEN = "8067473611:AAHaIRuXuCF_SCkiGkg-gfHf2zKPOkT_V9g"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def get_best_prices(query):
    # Використовуємо двигун google_shopping
    params = {
        "engine": "google_shopping",
        "q": query,
        "location": "Ukraine",
        "hl": "uk",
        "gl": "ua",
        "direct_link": True, # Намагатися отримати пряме посилання
        "api_key": SERP_API_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()
    
    products = []
    
    # Отримуємо результати з торгового пошуку
    if "shopping_results" in results:
        for res in results["shopping_results"]:
            # Фільтр: шукаємо тільки НОВІ товари
            # SerpApi зазвичай віддає стан товару в полі 'condition'
            condition = res.get("condition", "new").lower()
            if "used" in condition or "б/у" in condition or "вжива" in condition:
                continue

            # Список магазинів, які ти вказав (можна розширити)
            target_shops = ["rozetka", "allo", "comfy", "foxtrot", "prom", "yabko"]
            source = res.get("source", "").lower()
            
            # Перевіряємо, чи магазин є у нашому списку
            is_target = any(shop in source for shop in target_shops)

            price_str = res.get("price", "Ціну не знайдено")
            
            # Очищуємо ціну від символів, щоб можна було сортувати
            numeric_price = 0
            if price_str != "Ціну не знайдено":
                # Видаляємо пробіли, грн, $, тощо
                clean_price = "".join(filter(str.isdigit, price_str))
                numeric_price = int(clean_price) if clean_price else 0

            products.append({
                "shop": res.get("source", "Магазин"),
                "title": res.get("title"),
                "price": price_str,
                "numeric_price": numeric_price,
                "link": res.get("link"),
                "is_target": is_target
            })

    # 1. Сортуємо: спочатку ті магазини, що ми обрали, потім інші
    # 2. Всередині цих груп сортуємо за ціною (від дешевих до дорогих)
    products.sort(key=lambda x: (not x['is_target'], x['numeric_price']))
    
    return products[:10] # Повертаємо топ-10 результатів

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привіт! Я шукаю тільки НОВУ техніку в магазинах Rozetka, Алло, Comfy та інших. Введіть назву товару:")

@bot.message_handler(func=lambda message: True)
def handle_search(message):
    query = message.text
    msg = bot.send_message(message.chat.id, f"🔎 Шукаю нові {query} за найкращою ціною...")

    try:
        results = get_best_prices(query)
        
        if not results:
            bot.edit_message_text("На жаль, нових товарів за цим запитом не знайдено.", message.chat.id, msg.message_id)
            return

        response_text = f"💰 **Найдешевші нові пропозиції для {query}:**\n\n"
        
        for i, res in enumerate(results, 1):
            shop_name = f"✅ {res['shop']}" if res['is_target'] else res['shop']
            response_text += f"{i}. **{shop_name}** — `{res['price']}`\n"
            response_text += f"📦 {res['title']}\n"
            response_text += f"🔗 [Купити зараз]({res['link']})\n\n"

        # Telegram має ліміт на довжину повідомлення, тому обрізаємо якщо треба
        if len(response_text) > 4096:
            response_text = response_text[:4000] + "..."

        bot.edit_message_text(response_text, message.chat.id, msg.message_id, parse_mode="Markdown", disable_web_page_preview=True)
    
    except Exception as e:
        print(f"Error: {e}")
        bot.edit_message_text("Сталася помилка при пошуку. Спробуйте інший запит.", message.chat.id, msg.message_id)

bot.polling(none_stop=True)
