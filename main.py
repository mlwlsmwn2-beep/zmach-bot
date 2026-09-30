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
    "p1": {"name": "פותוס", "price": 45, "category": "עציצי בית", "on_deal": False, "deal_price": None},
    "p2": {"name": "מונסטרה", "price": 120, "category": "עציצי בית", "on_deal": False, "deal_price": None},
    "p3": {"name": "לבנדר", "price": 30, "category": "צמחי גינה", "on_deal": False, "deal_price": None},
    "p4": {"name": "רוזמרין", "price": 25, "category": "צמחי גינה", "on_deal": False, "deal_price": None},
}
next_product_num = 5

user_carts = {}
user_state = {}
user_order_data = {}
all_orders = []
next_order_id = 1

# admin_reply_map: admin message_id -> customer chat_id (for reply-to-chat routing)
admin_reply_map = {}
new_product_data = {}


def is_admin(chat_id):
    return str(chat_id) == str(ADMIN_CHAT_ID)


def product_display_price(p):
    if p.get("on_deal") and p.get("deal_price"):
        return f"~{p['price']}₪~ 🔥{p['deal_price']}₪"
    return f"{p['price']}₪"


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
            f"{p['name']} - {product_display_price(p)} ({p['category']})",
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
    deal_products = [p for p in PRODUCTS.values() if p.get("on_deal")]
    if not deal_products:
        bot.send_message(message.chat.id, "אין כרגע מבצעים פעילים, חזרו לבדוק בקרוב! 🌸")
        return
    text = "המבצעים שלנו כרגע:\n\n"
    for p in deal_products:
        text += f"🌿 {p['name']} - ~{p['price']}₪~ 🔥{p['deal_price']}₪\n"
    bot.send_message(message.chat.id, text)


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
    global next_order_id
    user_id = message.chat.id
    user_order_data[user_id]["phone"] = message.text
    user_state[user_id] = None

    cart = user_carts.get(user_id, [])
    item_names = [PRODUCTS[pid]["name"] for pid in cart]

    def item_price(pid):
        p = PRODUCTS[pid]
        return p["deal_price"] if p.get("on_deal") and p.get("deal_price") else p["price"]

    total = sum(item_price(pid) for pid in cart)
    data = user_order_data[user_id]

    order = {
        "id": next_order_id,
        "user_id": user_id,
        "username": message.from_user.username,
        "items": item_names,
        "total": total,
        "status": "התקבלה",
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "address": data["address"],
        "phone": data["phone"],
    }
    next_order_id += 1
    all_orders.append(order)

    bot.send_message(
        user_id,
        f"תודה {data['first_name']}! ההזמנה התקבלה ✅\n"
        f"מוצרים: {', '.join(item_names)}\n"
        f"סה\"כ: {total}₪ (תשלום במזומן לשליח)\n"
        f"נחזור אליכם בהקדם לתיאום המשלוח.",
        reply_markup=main_menu()
    )

    username_line = f"@{order['username']}" if order['username'] else "אין שם משתמש"
    admin_text = (
        f"🆕 הזמנה חדשה! (#{order['id']})\n\n"
        f"לקוח: {data['first_name']} {data['last_name']}\n"
        f"טלגרם: {username_line}\n"
        f"טלפון: {data['phone']}\n"
        f"כתובת: {data['address']}\n"
        f"מוצרים: {', '.join(item_names)}\n"
        f"סה\"כ: {total}₪ (מזומן)\n\n"
        f"👇 השיבו (Reply) להודעה הזו כדי לכתוב ללקוח ישירות"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ אשר קבלה ללקוח", callback_data=f"confirm_{order['id']}"))
    sent = bot.send_message(ADMIN_CHAT_ID, admin_text, reply_markup=markup)
    admin_reply_map[sent.message_id] = user_id

    user_carts[user_id] = []


@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_"))
def confirm_order(call):
    order_id = int(call.data.replace("confirm_", ""))
    order = next((o for o in all_orders if o["id"] == order_id), None)
    if not order:
        bot.answer_callback_query(call.id, "ההזמנה לא נמצאה")
        return
    order["status"] = "אושרה"
    bot.send_message(order["user_id"], "✅ ההזמנה שלכם אושרה ואנחנו מכינים אותה!")
    bot.answer_callback_query(call.id, "הלקוח קיבל הודעת אישור ✅")
    bot.edit_message_reply_markup(ADMIN_CHAT_ID, call.message.message_id, reply_markup=None)
    bot.edit_message_text(
        call.message.text + "\n\n✅ אושר ללקוח",
        ADMIN_CHAT_ID,
        call.message.message_id
    )


@bot.message_handler(commands=['orders'])
def admin_orders(message):
    if not is_admin(message.chat.id):
        return
    if not all_orders:
        bot.send_message(message.chat.id, "אין הזמנות עדיין.")
        return
    text = "כל ההזמנות:\n\n"
    for o in all_orders:
        text += (
            f"#{o['id']} {o['first_name']} {o['last_name']} | {o['phone']}\n"
            f"   {', '.join(o['items'])} - {o['total']}₪ | סטטוס: {o['status']}\n\n"
        )
    bot.send_message(message.chat.id, text)


# ---------- ADMIN: PRODUCT MANAGEMENT ----------

def admin_products_markup():
    markup = types.InlineKeyboardMarkup()
    for pid, p in PRODUCTS.items():
        markup.add(types.InlineKeyboardButton(
            f"{p['name']} - {product_display_price(p)}",
            callback_data="noop"
        ))
        row = [
            types.InlineKeyboardButton("✏️ שם", callback_data=f"editname_{pid}"),
            types.InlineKeyboardButton("💰 מחיר", callback_data=f"editprice_{pid}"),
        ]
        if p.get("on_deal"):
            row.append(types.InlineKeyboardButton("❌ כבה מבצע", callback_data=f"dealoff_{pid}"))
        else:
            row.append(types.InlineKeyboardButton("🔥 הפעל מבצע", callback_data=f"dealon_{pid}"))
        markup.row(*row)
    return markup


@bot.message_handler(commands=['products'])
def admin_products(message):
    if not is_admin(message.chat.id):
        return
    bot.send_message(message.chat.id, "ניהול מוצרים:", reply_markup=admin_products_markup())


@bot.callback_query_handler(func=lambda call: call.data == "noop")
def noop_callback(call):
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("editname_"))
def edit_name_start(call):
    if not is_admin(call.message.chat.id):
        return
    pid = call.data.replace("editname_", "")
    user_state[call.message.chat.id] = f"editing_name_{pid}"
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"שלח שם חדש עבור {PRODUCTS[pid]['name']}:")


@bot.callback_query_handler(func=lambda call: call.data.startswith("editprice_"))
def edit_price_start(call):
    if not is_admin(call.message.chat.id):
        return
    pid = call.data.replace("editprice_", "")
    user_state[call.message.chat.id] = f"editing_price_{pid}"
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"שלח מחיר חדש (במספר) עבור {PRODUCTS[pid]['name']}:")


@bot.callback_query_handler(func=lambda call: call.data.startswith("dealon_"))
def deal_on_start(call):
    if not is_admin(call.message.chat.id):
        return
    pid = call.data.replace("dealon_", "")
    user_state[call.message.chat.id] = f"editing_dealprice_{pid}"
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, f"שלח את מחיר המבצע עבור {PRODUCTS[pid]['name']}:")


@bot.callback_query_handler(func=lambda call: call.data.startswith("dealoff_"))
def deal_off(call):
    if not is_admin(call.message.chat.id):
        return
    pid = call.data.replace("dealoff_", "")
    PRODUCTS[pid]["on_deal"] = False
    PRODUCTS[pid]["deal_price"] = None
    bot.answer_callback_query(call.id, "המבצע כובה")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=admin_products_markup())


@bot.message_handler(func=lambda m: is_admin(m.chat.id) and str(user_state.get(m.chat.id, "")).startswith("editing_name_"))
def save_new_name(message):
    pid = user_state[message.chat.id].replace("editing_name_", "")
    PRODUCTS[pid]["name"] = message.text
    user_state[message.chat.id] = None
    bot.send_message(message.chat.id, f"השם עודכן ל: {message.text} ✅", reply_markup=admin_products_markup())


@bot.message_handler(func=lambda m: is_admin(m.chat.id) and str(user_state.get(m.chat.id, "")).startswith("editing_price_"))
def save_new_price(message):
    pid = user_state[message.chat.id].replace("editing_price_", "")
    try:
        PRODUCTS[pid]["price"] = int(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "צריך לשלוח מספר בלבד, נסה שוב:")
        return
    user_state[message.chat.id] = None
    bot.send_message(message.chat.id, "המחיר עודכן ✅", reply_markup=admin_products_markup())


@bot.message_handler(func=lambda m: is_admin(m.chat.id) and str(user_state.get(m.chat.id, "")).startswith("editing_dealprice_"))
def save_deal_price(message):
    pid = user_state[message.chat.id].replace("editing_dealprice_", "")
    try:
        PRODUCTS[pid]["deal_price"] = int(message.text)
        PRODUCTS[pid]["on_deal"] = True
    except ValueError:
        bot.send_message(message.chat.id, "צריך לשלוח מספר בלבד, נסה שוב:")
        return
    user_state[message.chat.id] = None
    bot.send_message(message.chat.id, "המבצע הופעל ✅", reply_markup=admin_products_markup())


@bot.message_handler(commands=['addproduct'])
def add_product_start(message):
    if not is_admin(message.chat.id):
        return
    user_state[message.chat.id] = "newproduct_name"
    new_product_data[message.chat.id] = {}
    bot.send_message(message.chat.id, "שם המוצר החדש:")


@bot.message_handler(func=lambda m: is_admin(m.chat.id) and user_state.get(m.chat.id) == "newproduct_name")
def new_product_name(message):
    new_product_data[message.chat.id]["name"] = message.text
    user_state[message.chat.id] = "newproduct_price"
    bot.send_message(message.chat.id, "מחיר המוצר (מספר):")


@bot.message_handler(func=lambda m: is_admin(m.chat.id) and user_state.get(m.chat.id) == "newproduct_price")
def new_product_price(message):
    try:
        new_product_data[message.chat.id]["price"] = int(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "צריך מספר, נסה שוב:")
        return
    user_state[message.chat.id] = "newproduct_category"
    bot.send_message(message.chat.id, "קטגוריה (למשל: עציצי בית / צמחי גינה):")


@bot.message_handler(func=lambda m: is_admin(m.chat.id) and user_state.get(m.chat.id) == "newproduct_category")
def new_product_category(message):
    global next_product_num
    data = new_product_data[message.chat.id]
    data["category"] = message.text
    pid = f"p{next_product_num}"
    next_product_num += 1
    PRODUCTS[pid] = {
        "name": data["name"],
        "price": data["price"],
        "category": data["category"],
        "on_deal": False,
        "deal_price": None,
    }
    user_state[message.chat.id] = None
    bot.send_message(message.chat.id, f"המוצר {data['name']} נוסף בהצלחה ✅", reply_markup=admin_products_markup())


# ---------- CHAT ROUTING (WhatsApp-style reply) ----------

@bot.message_handler(func=lambda m: is_admin(m.chat.id) and m.reply_to_message is not None)
def admin_reply_to_customer(message):
    customer_id = admin_reply_map.get(message.reply_to_message.message_id)
    if not customer_id:
        return
    bot.send_message(customer_id, f"📩 הודעה מהמשתלה:\n{message.text}")
    bot.send_message(message.chat.id, "נשלח ללקוח ✅")


@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "talking_to_rep")
def forward_to_admin(message):
    fwd = bot.forward_message(ADMIN_CHAT_ID, message.chat.id, message.message_id)
    admin_reply_map[fwd.message_id] = message.chat.id
    info = bot.send_message(ADMIN_CHAT_ID, "👆 השיבו (Reply) להודעה למעלה כדי לענות ללקוח")
    admin_reply_map[info.message_id] = message.chat.id
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
