#!/usr/bin/env python3
"""
ZEBRA SMS Telegram Bot (Fully Fixed Version)
"""
import os
import re
import time
import json
import threading
from datetime import datetime
import requests
from flask import Flask, request
from telebot import TeleBot, types

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8252061401:AAFK5wXve9Ut_atSQ937pol3Kf_BhaUH5YI"           # ⚠️ আপনার বট টোকেন
CHANNEL_ID = "@Cypher_HEX_OTP_Channel"                                 # ⚠️ OTP ফরওয়ার্ড চ্যানেল
FORCE_JOIN_CHANNEL = "@zebra_sms"                                     # ⚠️ Force Join চ্যানেল
OWNER_ID = "6915207616"                                                # ⚠️ আপনার Numeric Telegram ID দিন (যেমন 123456789)
WEBHOOK_URL = "https://cypher-hex-otp-bot-2.onrender.com"             # ⚠️ আপনার Render লিংক (শেষে / দিবেন না)
BASE_URL = "https://zebrasms.com/api/v1"
DB_FILE = "user_data.json"
# ===============================================================

bot = TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ডেটাবেস লোড/সেভ
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"users": {}, "stats": {"daily": 0, "weekly": 0, "monthly": 0}}

def save_db():
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

db = load_db()

# স্টেট ম্যানেজমেন্ট
user_states = {}
user_service = {}
user_country = {}
user_active_polling = {}
user_last_number = {}

# ==================== হেল্পার ফাংশন ====================
def get_liveaccess(api_key):
    """লাইভ ট্র্যাফিক ডেটা ফেচ"""
    try:
        res = requests.get(f"{BASE_URL}/publicapi/liveaccess", headers={"MAuth": api_key}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get("meta", {}).get("code") == 0:
                return data.get("data", {}).get("rows", [])
    except:
        pass
    return []

def get_update(api_key):
    """সর্বশেষ ৫০টি OTP ফেচ"""
    try:
        res = requests.get(f"{BASE_URL}/publicapi/getupdate", headers={"MAuth": api_key}, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if data.get("meta", {}).get("code") == 0:
                return data.get("data", {}).get("rows", [])
    except:
        pass
    return []

def get_number(api_key, range_val):
    """একটি নম্বর বরাদ্দ"""
    try:
        res = requests.post(f"{BASE_URL}/publicapi/getnum", 
                            headers={"MAuth": api_key, "Content-Type": "application/json"},
                            json={"range": range_val}, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("meta", {}).get("code") == 0 and data.get("data", {}).get("rows"):
                return data["data"]["rows"][0]
        return None
    except:
        return None

def get_country_from_range(range_str):
    """রেঞ্জ থেকে দেশ কোড বের করা"""
    prefix = re.sub(r'[Xx*].*$', '', range_str)
    country_map = {
        "225": "CI", "228": "TG", "237": "CM", "234": "NG", 
        "221": "SN", "223": "ML", "226": "BF", "227": "NE",
        "235": "TD", "236": "CF", "241": "GA", "242": "CG",
        "243": "CD", "254": "KE", "255": "TZ", "256": "UG",
        "880": "BD", "91": "IN", "92": "PK", "93": "AF",
    }
    for code, iso in country_map.items():
        if prefix.startswith(code):
            return iso
    return "XX"

def get_country_info(iso_code):
    """দেশের ফ্ল্যাগ ও নাম"""
    flags = {
        "CI": ("🇨🇮", "Ivory Coast"), "TG": ("🇹🇬", "Togo"), "CM": ("🇨🇲", "Cameroon"),
        "NG": ("🇳🇬", "Nigeria"), "SN": ("🇸🇳", "Senegal"), "ML": ("🇲🇱", "Mali"),
        "BF": ("🇧🇫", "Burkina Faso"), "NE": ("🇳🇪", "Niger"), "TD": ("🇹🇩", "Chad"),
        "CF": ("🇨🇫", "Central African Republic"), "GA": ("🇬🇦", "Gabon"),
        "CG": ("🇨🇬", "Congo"), "CD": ("🇨🇩", "DR Congo"), "KE": ("🇰🇪", "Kenya"),
        "TZ": ("🇹🇿", "Tanzania"), "UG": ("🇺🇬", "Uganda"), "BD": ("🇧🇩", "Bangladesh"),
        "IN": ("🇮🇳", "India"), "PK": ("🇵🇰", "Pakistan"), "AF": ("🇦🇫", "Afghanistan"),
        "US": ("🇺🇸", "USA"), "GB": ("🇬🇧", "UK"), "DE": ("🇩🇪", "Germany"),
        "FR": ("🇫🇷", "France"), "ES": ("🇪🇸", "Spain"), "IT": ("🇮🇹", "Italy"),
    }
    return flags.get(iso_code, ("🌍", iso_code))

# ==================== টেলিগ্রাম হ্যান্ডলার ====================
@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    chat_id = message.chat.id

    # ⚠️ Force Join চেক (ভুল চ্যানেল থাকলে এরর না দিয়ে বার্তা দেবে)
    if FORCE_JOIN_CHANNEL:
        try:
            member = bot.get_chat_member(FORCE_JOIN_CHANNEL, chat_id)
            if member.status not in ['member', 'administrator', 'creator']:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_JOIN_CHANNEL.lstrip('@')}"))
                markup.add(types.InlineKeyboardButton("✅ I Have Joined", callback_data="check_join"))
                bot.send_message(chat_id, "🚫 *Access Restricted*\nYou must join our channel to use this bot.", parse_mode="Markdown", reply_markup=markup)
                return
        except Exception:
            bot.send_message(chat_id, f"❌ *Force Join Error:*\nUnable to verify channel `{FORCE_JOIN_CHANNEL}`.\nPlease contact admin.", parse_mode="Markdown")
            return

    # ⚠️ API কী চেক
    user_key = db.get("users", {}).get(str(chat_id), {}).get("api_key")
    if not user_key:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💡 How to get API Key?", url="https://zebrasms.com"))
        bot.send_message(chat_id, "🔑 *No API Key Found!*\n\nPlease set your ZEBRA SMS API Key using:\n<code>/setkey YOUR_API_KEY</code>", parse_mode="Markdown", reply_markup=markup)
        return

    # মূল মেনু (Reply Keyboard)
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("📱 GET NUMBER")
    btn2 = types.KeyboardButton("🔍 SEARCH RANGE")
    btn3 = types.KeyboardButton("🚦 TRAFFIC")
    btn4 = types.KeyboardButton("💰 BALANCE")
    btn5 = types.KeyboardButton("🛠 SUPPORT")
    btn6 = types.KeyboardButton("🔐 2FA SETUP")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    bot.send_message(chat_id, "Welcome to ZEBRA SMS Bot! Select an option below.", reply_markup=markup)

@bot.message_handler(commands=['setkey'])
def set_api_key(message):
    chat_id = message.chat.id
    args = message.text.split()
    if len(args) != 2:
        bot.reply_to(message, "⚠️ Usage: <code>/setkey YOUR_API_KEY</code>", parse_mode="Markdown")
        return
    key = args[1]
    if str(chat_id) not in db["users"]:
        db["users"][str(chat_id)] = {}
    db["users"][str(chat_id)]["api_key"] = key
    save_db()
    bot.reply_to(message, "✅ API Key saved! Use /menu to start.")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    data = call.data
    bot.answer_callback_query(call.id)

    if data == "check_join":
        if FORCE_JOIN_CHANNEL:
            try:
                member = bot.get_chat_member(FORCE_JOIN_CHANNEL, chat_id)
                if member.status in ['member', 'administrator', 'creator']:
                    bot.delete_message(chat_id, call.message.message_id)
                    send_welcome(call.message)
                else:
                    bot.answer_callback_query(call.id, "❌ You haven't joined yet!", show_alert=True)
            except:
                bot.answer_callback_query(call.id, "❌ Error verifying membership.", show_alert=True)
        return

    user_key = db.get("users", {}).get(str(chat_id), {}).get("api_key")
    if not user_key:
        bot.send_message(chat_id, "❌ Please set your API key first with /setkey.")
        return

    # ------------------ GET NUMBER ফ্লো ------------------
    if data == "get_number":
        rows = get_liveaccess(user_key)
        services = {}
        for row in rows:
            sender = row.get("sender", "Unknown")
            if sender not in services:
                services[sender] = {"count": 0, "ranges": []}
            services[sender]["count"] += row.get("count", 0)
            services[sender]["ranges"].extend(row.get("ranges", []))
        markup = types.InlineKeyboardMarkup(row_width=2)
        for srv in services.keys():
            markup.add(types.InlineKeyboardButton(f"{srv}", callback_data=f"srv_{srv}"))
        markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="menu_back"))
        bot.edit_message_text("📱 *Select Service:*", chat_id=chat_id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data.startswith("srv_"):
        service = data.split("_")[1]
        user_service[chat_id] = service
        rows = get_liveaccess(user_key)
        country_hits = {}
        for row in rows:
            if row.get("sender") == service:
                for r in row.get("ranges", []):
                    iso = get_country_from_range(r)
                    if iso not in country_hits:
                        country_hits[iso] = {"hits": 0, "ranges": []}
                    country_hits[iso]["hits"] += row.get("count", 0)
                    country_hits[iso]["ranges"].append(r)
        markup = types.InlineKeyboardMarkup(row_width=1)
        for iso, data in country_hits.items():
            flag, name = get_country_info(iso)
            btn_text = f"{flag} {name} ({iso}) - Hits: {data['hits']}"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"ctry_{iso}"))
        markup.add(types.InlineKeyboardButton("🔙 Back to Services", callback_data="get_number"))
        bot.edit_message_text(f"🌍 *Select Country for {service}*\n━━━━━━━━━━━━━", chat_id=chat_id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data.startswith("ctry_"):
        country = data.split("_")[1]
        user_country[chat_id] = country
        service = user_service.get(chat_id)
        if not service:
            bot.edit_message_text("❌ Service not found. Please restart.", chat_id=chat_id, message_id=call.message.message_id)
            return
        rows = get_liveaccess(user_key)
        ranges = []
        for row in rows:
            if row.get("sender") == service:
                for r in row.get("ranges", []):
                    if get_country_from_range(r) == country:
                        ranges.append(r)
        if not ranges:
            bot.edit_message_text("❌ No ranges available for this country.", chat_id=chat_id, message_id=call.message.message_id)
            return
        selected_range = ranges[0]
        number_data = get_number(user_key, selected_range)
        if not number_data:
            bot.edit_message_text("❌ Failed to allocate number. Try again.", chat_id=chat_id, message_id=call.message.message_id)
            return
        full_number = number_data.get("number")
        country_name = number_data.get("country", "Unknown")
        operator = number_data.get("operator", "Unknown")
        flag, _ = get_country_info(country)
        msg_text = (f"✅ *Number Allocated!*\n\n"
                    f"📞 *Number:* `{full_number}`\n"
                    f"🌍 *Country:* {flag} {country_name}\n"
                    f"📡 *Operator:* {operator}\n\n"
                    f"🕒 *Status:* 🔍 Searching for OTP...")
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔄 Change Number", callback_data=f"change_num_{selected_range}"),
            types.InlineKeyboardButton("🌍 Change Country", callback_data="change_country"),
            types.InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_back")
        )
        bot.edit_message_text(msg_text, chat_id=chat_id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        user_active_polling[chat_id] = True
        user_last_number[chat_id] = (full_number, selected_range, call.message.message_id)
        threading.Thread(target=poll_otp, args=(chat_id, full_number, call.message.message_id)).start()

    elif data == "change_num_" + user_last_number.get(chat_id, ("", ""))[1]:
        _, range_val, msg_id = user_last_number.get(chat_id, ("", "", 0))
        if not range_val:
            bot.edit_message_text("❌ No active number found.", chat_id=chat_id, message_id=call.message.message_id)
            return
        number_data = get_number(user_key, range_val)
        if not number_data:
            bot.edit_message_text("❌ Failed to allocate number.", chat_id=chat_id, message_id=call.message.message_id)
            return
        full_number = number_data.get("number")
        country_name = number_data.get("country", "Unknown")
        operator = number_data.get("operator", "Unknown")
        flag, _ = get_country_info(get_country_from_range(range_val))
        msg_text = (f"✅ *Number Allocated!*\n\n"
                    f"📞 *Number:* `{full_number}`\n"
                    f"🌍 *Country:* {flag} {country_name}\n"
                    f"📡 *Operator:* {operator}\n\n"
                    f"🕒 *Status:* 🔍 Searching for OTP...")
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔄 Change Number", callback_data=f"change_num_{range_val}"),
            types.InlineKeyboardButton("🌍 Change Country", callback_data="change_country"),
            types.InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_back")
        )
        bot.edit_message_text(msg_text, chat_id=chat_id, message_id=msg_id, parse_mode="Markdown", reply_markup=markup)
        user_last_number[chat_id] = (full_number, range_val, msg_id)

    elif data == "change_country":
        service = user_service.get(chat_id)
        if service:
            bot.edit_message_text("🌍 *Select Country*", chat_id=chat_id, message_id=call.message.message_id)
            rows = get_liveaccess(user_key)
            country_hits = {}
            for row in rows:
                if row.get("sender") == service:
                    for r in row.get("ranges", []):
                        iso = get_country_from_range(r)
                        if iso not in country_hits:
                            country_hits[iso] = {"hits": 0, "ranges": []}
                        country_hits[iso]["hits"] += row.get("count", 0)
                        country_hits[iso]["ranges"].append(r)
            markup = types.InlineKeyboardMarkup(row_width=1)
            for iso, data in country_hits.items():
                flag, name = get_country_info(iso)
                btn_text = f"{flag} {name} ({iso}) - Hits: {data['hits']}"
                markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"ctry_{iso}"))
            markup.add(types.InlineKeyboardButton("🔙 Back to Services", callback_data="get_number"))
            bot.edit_message_text(f"🌍 *Select Country for {service}*\n━━━━━━━━━━━━━", chat_id=chat_id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif data == "menu_back":
        send_welcome(call.message)

# ------------------ কাস্টম রেঞ্জ হ্যান্ডলার ------------------
@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id) == "awaiting_custom_range")
def handle_custom_range(message):
    chat_id = message.chat.id
    user_states[chat_id] = None
    range_val = message.text.strip()
    user_key = db.get("users", {}).get(str(chat_id), {}).get("api_key")
    if not user_key:
        bot.reply_to(message, "❌ API Key missing! Use /setkey.")
        return
    number_data = get_number(user_key, range_val)
    if not number_data:
        bot.reply_to(message, "❌ Failed to allocate number. Check your range and try again.")
        return
    full_number = number_data.get("number")
    country_name = number_data.get("country", "Unknown")
    operator = number_data.get("operator", "Unknown")
    flag, _ = get_country_info(get_country_from_range(range_val))
    msg_text = (f"✅ *Number Allocated!*\n\n"
                f"📞 *Number:* `{full_number}`\n"
                f"🌍 *Country:* {flag} {country_name}\n"
                f"📡 *Operator:* {operator}\n\n"
                f"🕒 *Status:* 🔍 Searching for OTP...")
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🔄 Change Number", callback_data=f"change_num_{range_val}"),
        types.InlineKeyboardButton("🌍 Change Country", callback_data="change_country"),
        types.InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_back")
    )
    bot.send_message(chat_id, msg_text, parse_mode="Markdown", reply_markup=markup)
    user_active_polling[chat_id] = True
    user_last_number[chat_id] = (full_number, range_val, None)
    threading.Thread(target=poll_otp, args=(chat_id, full_number, None)).start()

# ------------------ টেক্সট মেনু হ্যান্ডলার ------------------
@bot.message_handler(func=lambda msg: msg.text in ["📱 GET NUMBER", "🔍 SEARCH RANGE", "🚦 TRAFFIC", "💰 BALANCE", "🛠 SUPPORT", "🔐 2FA SETUP"])
def handle_menu_buttons(message):
    chat_id = message.chat.id
    text = message.text
    if text == "📱 GET NUMBER":
        handle_callback(types.CallbackQuery(id="dummy", from_user=message.from_user, data="get_number", message=message))
    elif text == "🔍 SEARCH RANGE":
        user_states[chat_id] = "awaiting_custom_range"
        bot.send_message(chat_id, "✍️ *Enter custom range (e.g., 22501XXX):*", parse_mode="Markdown")
    elif text == "🚦 TRAFFIC":
        user_key = db.get("users", {}).get(str(chat_id), {}).get("api_key")
        if not user_key:
            bot.reply_to(message, "❌ API Key missing! Use /setkey.")
            return
        rows = get_liveaccess(user_key)
        if not rows:
            bot.send_message(chat_id, "❌ No traffic data available.")
            return
        grouped = {}
        for row in rows:
            sender = row.get("sender", "Unknown")
            if sender not in grouped:
                grouped[sender] = {"count": 0, "ranges": []}
            grouped[sender]["count"] += row.get("count", 0)
            grouped[sender]["ranges"].extend(row.get("ranges", []))
        text = "🔥 *Live Traffic*\n━━━━━━━━━━━\n"
        for srv, data in grouped.items():
            text += f"📱 *{srv}* | 📦 Stock: {data['count']}\n"
            ranges_display = ", ".join(data["ranges"][:3])
            text += f"└ {ranges_display}\n\n"
        bot.send_message(chat_id, text, parse_mode="Markdown")
    elif text == "💰 BALANCE":
        bal = db.get("users", {}).get(str(chat_id), {}).get("balance", 0.0)
        bot.send_message(chat_id, f"💰 *Your Balance:* {bal} ৳", parse_mode="Markdown")
    elif text == "🛠 SUPPORT":
        bot.send_message(chat_id, "👨‍💻 Contact: @your_support")
    elif text == "🔐 2FA SETUP":
        bot.send_message(chat_id, "2FA setup is not yet implemented. Please contact admin.")

# ==================== OTP পোলিং (ব্যাকগ্রাউন্ড) ====================
def poll_otp(chat_id, expected_number, message_id):
    while user_active_polling.get(chat_id, False):
        user_key = db.get("users", {}).get(str(chat_id), {}).get("api_key")
        if not user_key:
            break
        rows = get_update(user_key)
        for row in rows:
            num = row.get("number", "").replace("+", "")
            if num == expected_number:
                sms = row.get("message", "")
                sender = row.get("sender", "Unknown")
                otp_match = re.search(r'\b\d{4,8}\b', sms)
                otp = otp_match.group(0) if otp_match else "No OTP Found"
                msg = (f"🎉 *NEW OTP RECEIVED!*\n━━━━━━━━━━━\n"
                       f"📱 *Service:* {sender}\n"
                       f"📞 *Number:* +{expected_number}\n"
                       f"🔑 *OTP:* `{otp}`\n"
                       f"✉️ *SMS:* {sms}")
                bot.send_message(chat_id, msg, parse_mode="Markdown")
                if CHANNEL_ID:
                    masked = expected_number[:4] + "***" + expected_number[-3:]
                    channel_msg = (f"🔥 LIVE OTP\n━━━━━━━━━\n"
                                   f"📱 Service: {sender}\n"
                                   f"📞 Number: +{masked}\n"
                                   f"🔑 OTP: `{otp}`")
                    bot.send_message(CHANNEL_ID, channel_msg, parse_mode="Markdown")
                if otp != "No OTP Found":
                    reward = 0.5
                    if str(chat_id) not in db["users"]:
                        db["users"][str(chat_id)] = {"balance": 0.0}
                    db["users"][str(chat_id)]["balance"] = db["users"][str(chat_id)].get("balance", 0.0) + reward
                    save_db()
                user_active_polling[chat_id] = False
                if message_id:
                    try:
                        bot.edit_message_text(f"✅ *OTP FOUND!*\n\n📞 Number: +{expected_number}\n🔑 OTP: `{otp}`", chat_id=chat_id, message_id=message_id, parse_mode="Markdown")
                    except:
                        pass
                return
        time.sleep(2)

# ==================== ফ্লাস্ক ওয়েবহুক ====================
@app.route('/')
def home():
    return "Bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == "POST":
        update = request.get_json()
        if update:
            bot.process_new_updates([update])
        return "OK", 200
    return "Method not allowed", 405

# ==================== মেইন এক্সিকিউটর (Webhook) ====================
if __name__ == "__main__":
    # পূর্ববর্তী ওয়েবহুক মুছে ফেলা
    bot.remove_webhook()
    
    # Render লিংকে নতুন ওয়েবহুক সেট করা
    if WEBHOOK_URL:
        bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
        print(f"✅ Webhook set to: {WEBHOOK_URL}/webhook")
    else:
        print("❌ Error: WEBHOOK_URL is not set.")

    print("🚀 ZEBRA SMS Bot started with Webhook!")
    app.run(host='0.0.0.0', port=8080)