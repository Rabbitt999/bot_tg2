import telebot
from serpapi import GoogleSearch

# Налаштування
SERP_API_KEY = "5b17fc511645b27655b61507e9fb9c416f87c888a64e5b10e8552478051ff2e3"
TELEGRAM_TOKEN = "8067473611:AAHaIRuXuCF_SCkiGkg-gfHf2zKPOkT_V9g"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Твої ID наліпок
SHOP_ICONS = {
    "rozetka": "5208692064618845639",
    "foxtrot": "5206164837142400502",
    "allo": "5208607565432263411",
    "comfy": "5206301838009209388",
    "prom": "5208794980625190065",
    "yabko": "5206344461264653043",
    "citrus": "🍊"
}

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
    best_offers = {}
    
    if "shopping_results" in results:
        for res in results["shopping_results"]:
            # Тільки нове
            condition = res.get("condition", "new").lower()
            if any(word in condition for word in ["used", "б/у", "вжива"]): continue

            source = res.get("source", "").lower()
            found_shop = next((s for s in ALLOWED_SHOPS if s in source), None)
            if not found_shop: continue

            price_str = res.get("price", "0")
            clean_price = "".join(filter(str.isdigit, price_str))
            numeric_price = int(clean_price) if clean_price else 9999999

            # Унікальність магазину (найдешевша пропозиція)
            if found_shop not in best_offers or numeric_price < best_offers[found_shop]['numeric_price']:
                best_offers[found_shop] = {
                    "shop_key": found_shop,
                    "shop_name": found_shop.capitalize(),
                    "title": res.get("title"),
                    "price": price_str,
                    "numeric_price": numeric_price,
                    "link": res.get("link")
                }
    
    return sorted(best_offers.values(), key=lambda x: x['numeric_price'])[:5]

@bot.message_handler(func=lambda message: True)
def handle_search(message):
    query = message.text
    msg = bot.send_message(message.chat.id, f"🔎 Шукаю <b>{query}</b>...", parse_mode="HTML")

    try:
        results = get_best_prices(query)
        if not results:
            bot.edit_message_text("❌ Нічого не знайдено в обраних магазинах.", message.chat.id, msg.message_id)
            return

        response_text = f"💰 <b>Топ-5 цін для:</b> <i>{query}</i>\n\n"
        medals = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣", 5: "5️⃣"}

        for i, res in enumerate(results, 1):
            medal = medals.get(i, f"{i}.")
            emoji_id = SHOP_ICONS.get(res['shop_key'])
            
            # Спроба відобразити кастомний емодзі
            if emoji_id and emoji_id.isdigit():
                icon = f'<tg-emoji emoji-id="{emoji_id}">🏪</tg-emoji>'
            else:
                icon = emoji_id if emoji_id else "🏪"

            response_text += f"{medal} {icon} <b>{res['shop_name']}</b>\n"
            response_text += f"💵 Ціна: <b>{res['price']}</b>\n"
            response_text += f"📦 {res['title'][:40]}...\n"
            response_text += f"🔗 <a href='{res['link']}'>ПОСИЛАННЯ</a>\n\n"

        bot.edit_message_text(response_text, message.chat.id, msg.message_id, parse_mode="HTML", disable_web_page_preview=True)
    
    except Exception as e:
        bot.edit_message_text(f"❌ Помилка: {e}", message.chat.id, msg.message_id)

bot.polling(none_stop=True)
