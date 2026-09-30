import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")

if not BOT_TOKEN:
    raise ValueError("חסר BOT_TOKEN במשתני הסביבה")
if not ADMIN_CHAT_ID:
    raise ValueError("חסר ADMIN_CHAT_ID במשתני הסביבה")

bot = telebot.TeleBot(BOT_TOKEN)

PRODUCTS = {
    "p1": {"name": "פותוס", "price": 45, "category": "עציצי בית"},
    "p2": {"name": "מונסטרה", "price": 120, "category": "עציצי בית"},
    "p3": {"name": "לבנדר", "price": 30, "category": "צמחי גינה"},
    "p4": {"name": "רוזמרין", "price": 25, "category": "צמחי גינה"},
}

user_carts = {}
user_state = {}
user_order_data = {}
all_orders = []


def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🌱 מוצרים"))
    markup.add(types.KeyboardButton("⭐ הנבחרים שלנו"), types.KeyboardButton("🔥 מבצעים"))
    markup.add(types.KeyboardButton("💬 לדבר עם נציג"))
    markup.add(types.KeyboardButton("📦 ההזמנות שלי"))
    return markup


@bot.message_handler(commands=['start'])
def start(message):
    user_carts[message.chat.id] = []
    user_state[message.chat.id] = None
    bot.send_message(
        message.chat.id,
        "ברוכים הבאים למשתלה! 🌿\nבחרו אפשרות מהתפריט:",
        reply_markup=main_menu()
    )


@bot.message_handler(func=lambda m: m.text == "🌱 מוצרים")
def show_products(message):
    markup = types.InlineKeyboardMarkup()
    for pid, p in PRODUCTS.items():
        markup.add(types.InlineKeyboardButton(
            f"{p['name']} - {p['price']}₪ ({p['category']})",
            callback_data=f"add_{pid}"
        ))
    bot.send_message(message.chat.id, "בחרו מוצרים להוספה להזמנה:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("add_"))
def add_to_cart(call):
    pid = call.data.replace("add_", "")
    user_id = call.message.chat.id
    user_carts.setdefault(user_id, []).append(pid)
    product = PRODUCTS[pid]
    bot.answer_callback_query(call.id, f"{product['name']} נוסף להזמנה ✅")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🛒 סיום הזמנה", callback_data="checkout"))
    markup.add(types.InlineKeyboardButton("➕ להמשיך לבחור מוצרים", callback_data="continue_shopping"))
    bot.send_message(user_id, "מה תרצו לעשות עכשיו?", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "continue_shopping")
def continue_shopping(call):
    show_products(call.message)


@bot.message_handler(func=lambda m: m.text == "⭐ הנבחרים שלנו")
def featured(message):
    bot.send_message(message.chat.id, "הנבחרים שלנו כרגע:\n🌿 מונסטרה - 120₪\n🌿 פותוס - 45₪")


@bot.message_handler(func=lambda m: m.text == "🔥 מבצעים")
def deals(message):
    bot.send_message(message.chat.id, "אין כרגע מבצעים פעילים, חזרו לבדוק בקרוב! 🌸")


@bot.message_handler(func=lambda m: m.text == "💬 לדבר עם נציג")
def talk_to_rep(message):
    bot.send_message(
        message.chat.id,
        "אפשר לכתוב כאן את השאלה שלכם ונחזור אליכם בהקדם 🙋"
    )
    user_state[message.chat.id] = "talking_to_rep"


@bot.message_handler(func=lambda m: m.text == "📦 ההזמנות שלי")
def my_orders(message):
    user_id = message.chat.id
    my_list = [o for o in all_orders if o["user_id"] == user_id]
    if not my_list:
        bot.send_message(user_id, "עדיין אין לכם הזמנות 🙂")
        return
    text = "ההזמנות שלכם:\n\n"
    for i, o in enumerate(my_list, 1):
        items = ", ".join(o["items"])
        text += f"{i}. {items} - סטטוס: {o['status']}\n"
    bot.send_message(user_id, text)


@bot.callback_query_handler(func=lambda call: call.data == "checkout")
def checkout(call):
    user_id = call.message.chat.id
    if not user_carts.get(user_id):
        bot.send_message(user_id, "העגלה שלכם ריקה, בחרו קודם מוצרים 🙂")
        return
    user_state[user_id] = "waiting_first_name"
    user_order_data[user_id] = {}
    bot.send_message(user_id, "מה השם הפרטי שלכם?")


@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_first_name")
def get_first_name(message):
    user_id = message.chat.id
    user_order_data[user_id]["first_name"] = message.text
    user_state[user_id] = "waiting_last_name"
    bot.send_message(user_id, "ומה שם המשפחה?")


@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_last_name")
def get_last_name(message):
    user_id = message.chat.id
    user_order_data[user_id]["last_name"] = message.text
    user_state[user_id] = "waiting_address"
    bot.send_message(user_id, "מה כתובת המשלוח? (רחוב, מספר, עיר)")


@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_address")
def get_address(message):
    user_id = message.chat.id
    user_order_data[user_id]["address"] = message.text
    user_state[user_id] = "waiting_phone"
    bot.send_message(user_id, "ומספר טלפון ליצירת קשר?")


@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "waiting_phone")
def get_phone(message):
    user_id = message.chat.id
    user_order_data[user_id]["phone"] = message.text
    user_state[user_id] = None

    cart = user_carts.get(user_id, [])
    item_names = [PRODUCTS[pid]["name"] for pid in cart]
    total = sum(PRODUCTS[pid]["price"] for pid in cart)
    data = user_order_data[user_id]

    order = {
        "user_id": user_id,
        "items": item_names,
        "total": total,
        "status": "התקבלה",
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "address": data["address"],
        "phone": data["phone"],
    }
    all_orders.append(order)

    bot.send_message(
        user_id,
        f"תודה {data['first_name']}! ההזמנה התקבלה ✅\n"
        f"מוצרים: {', '.join(item_names)}\n"
        f"סה\"כ: {total}₪ (תשלום במזומן לשליח)\n"
        f"נחזור אליכם בהקדם לתיאום המשלוח.",
        reply_markup=main_menu()
    )

    admin_text = (
        f"🆕 הזמנה חדשה!\n\n"
        f"לקוח: {data['first_name']} {data['last_name']}\n"
        f"טלפון: {data['phone']}\n"
        f"כתובת: {data['address']}\n"
        f"מוצרים: {', '.join(item_names)}\n"
        f"סה\"כ: {total}₪ (מזומן)"
    )
    bot.send_message(ADMIN_CHAT_ID, admin_text)

    user_carts[user_id] = []


@bot.message_handler(commands=['orders'])
def admin_orders(message):
    if str(message.chat.id) != str(ADMIN_CHAT_ID):
        return
    if not all_orders:
        bot.send_message(message.chat.id, "אין הזמנות עדיין.")
        return
    text = "כל ההזמנות:\n\n"
    for i, o in enumerate(all_orders, 1):
        text += (
            f"{i}. {o['first_name']} {o['last_name']} | {o['phone']}\n"
            f"   {', '.join(o['items'])} - {o['total']}₪ | סטטוס: {o['status']}\n\n"
        )
    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "talking_to_rep")
def forward_to_admin(message):
    bot.forward_message(ADMIN_CHAT_ID, message.chat.id, message.message_id)
    bot.send_message(message.chat.id, "ההודעה נשלחה לנציג, נחזור אליכם בהקדם 🙂")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")


def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()


threading.Thread(target=run_health_server, daemon=True).start()

print("הבוט פעיל ומאזין...")
bot.infinity_polling()
