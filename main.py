import telebot
from serpapi import GoogleSearch

# Налаштування
SERP_API_KEY = "5b17fc511645b27655b61507e9fb9c416f87c888a64e5b10e8552478051ff2e3"
TELEGRAM_TOKEN = "8067473611:AAHaIRuXuCF_SCkiGkg-gfHf2zKPOkT_V9g"

bot = telebot.TeleBot(TELEGRAM_TOKEN)

def get_best_prices(query):
    # Сайти, на яких ми хочемо шукати
    shops = "site:rozetka.com.ua OR site:allo.ua OR site:comfy.ua OR site:foxtrot.com.ua OR site:yabko.ua"
    full_query = f"{query} {shops}"

    params = {
        "engine": "google",
        "q": full_query,
        "location": "Ukraine",
        "hl": "uk",
        "gl": "ua",
        "google_domain": "google.com.ua",
        "api_key": SERP_API_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()
    
    products = []
    
    # Перевіряємо результати "Organic Results"
    if "organic_results" in results:
        for res in results["organic_results"][:6]: # Беремо топ-6 результатів
            # SerpApi часто підтягує ціну в rich_snippet
            price = "Ціну не знайдено"
            if "rich_snippet" in res:
                extension = res["rich_snippet"].get("top", {}).get("detected_extensions", {})
                if "price" in extension:
                    price = f"{extension['price']} {extension.get('currency', 'грн')}"
            
            products.append({
                "shop": res.get("displayed_link", "").split('.')[0].replace("https://", ""),
                "title": res.get("title"),
                "price": price,
                "link": res.get("link")
            })
    return products

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привіт! Напиши назву техніки, і я знайду ціни через SerpApi.")

@bot.message_handler(func=lambda message: True)
def handle_search(message):
    query = message.text
    msg = bot.send_message(message.chat.id, "🔍 Аналізую ринок...")

    try:
        results = get_best_prices(query)
        
        if not results:
            bot.edit_message_text("Нічого не знайдено за цим запитом.", message.chat.id, msg.message_id)
            return

        response_text = f"💰 **Ціни на {query}:**\n\n"
        for i, res in enumerate(results, 1):
            response_text += f"{i}. **{res['shop'].capitalize()}** — {res['price']}\n"
            response_text += f"📦 {res['title']}\n"
            response_text += f"🔗 [Перейти до магазину]({res['link']})\n\n"

        bot.edit_message_text(response_text, message.chat.id, msg.message_id, parse_mode="Markdown", disable_web_page_preview=True)
    
    except Exception as e:
        bot.edit_message_text(f"Сталася помилка: {e}", message.chat.id, msg.message_id)

bot.polling(none_stop=True)
