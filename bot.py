import asyncio
import io
import re
import json
import html
import os
import httpx
import pyotp
import random
import string
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

# ==================== CONFIG SECTION ====================

import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8876104251:AAHBLfQ8AZQ_d5SvqiHh8kHYC5T0kItpcG0")
API_KEY = os.environ.get("API_KEY", "8U73CV8X4LT")
BASE_URL = os.environ.get("BASE_URL", "https://zebrasms.com/api/v1")           # প্যানেল ডোমেন
USER_DATA_FILE = "users.json"
PAID_SMS_FILE = "paid_sms.json"
STATS_FILE = "user_stats.json"
REFERRAL_DATA_FILE = "referral_data.json"
BANNED_USERS_FILE = "banned_users.json"
WITHDRAW_DATA_FILE = "withdraw_requests.json"
ACTIVITY_LOGS_FILE = "activity_logs.json"
DATA_RANGE_FILE = "datarange.json"
CUSTOM_SERVICES_FILE = "custom_services.json"

# ==================== MULTIPLE ADMINS CONFIGURATION ====================
ADMINS = [int(x.strip()) for x in os.environ.get("ADMINS", "6915207616").split(",") if x.strip()]

OTP_GROUP_ID = int(os.environ.get("OTP_GROUP_ID", "-5547400032"))

# ==================== WELCOME MESSAGE CONFIGURATION ====================
WELCOME_MESSAGE = """⚡ 𝗭𝗘𝗕𝗥𝗔 𝗦𝗠𝗦 𝗣𝗔𝗡𝗘𝗟 𝗕𝗢𝗧 ⚡ 
━━━━━━━━━━━━━━━━━━━━━━
🟢 𝗣𝗿𝗲𝗺𝗶𝘂𝗺 & ⚡ 𝗙𝗮𝘀𝘁 𝗦𝗲𝗿𝘃𝗶𝗰𝗲 🟢"""

# ==================== OTP RATE CONFIGURATION ====================
OTP_RATE = 0.00

# ==================== REFERRAL / WITHDRAW CONFIGURATION ====================
REFERRAL_PRICE = 0
MIN_WITHDRAW = 50
MAX_WITHDRAW = 10000

# ==================== SUPPORT LINK (EDITABLE) ====================
SUPPORT_LINK = os.environ.get("SUPPORT_LINK", "https://t.me/cypher_hex")      # সাপোর্ট লিংক পরিবর্তনযোগ্য

request_queue = asyncio.Queue()
MAX_WORKERS = 50000000000000000000000000000

# অত্যন্ত দ্রুত এপিআই রিকোয়েস্ট নিশ্চিত করতে অপ্টিমাইজড ক্লায়েন্ট সেটিংস ও টাইমআউট বৃদ্ধি
client_async = httpx.AsyncClient(
    http2=True,
    timeout=httpx.Timeout(connect=3.0, read=30.0, write=5.0, pool=15.0),
    headers={
        "MAuth": API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Connection": "keep-alive"
    },
    limits=httpx.Limits(max_connections=3000, max_keepalive_connections=1000)
)

active_numbers = {}
last_range = {}
CHECK_INTERVAL = 0.2

# ==================== HELPERS SECTION ====================

def get_bangladesh_time():
    """সার্ভার যেখানেই থাকুক, এটি সর্বদা সঠিক বাংলাদেশি সময় রিটার্ন করবে।"""
    return datetime.utcnow() + timedelta(hours=6)

def normalize_number(number):
    if not number:
        return ""
    return re.sub(r'\D', '', str(number))

def mask_number(number):
    num_str = str(number)
    if len(num_str) <= 6:
        return num_str
    return num_str[:4] + "****" + num_str[-2:]

def is_valid_bangladesh_number(number):
    clean = re.sub(r'\D', '', str(number))
    if len(clean) == 11 and clean.startswith("01"):
        return True
    if len(clean) == 13 and clean.startswith("8801"):
        return True
    return False

def format_balance(balance):
    try:
        return f"{float(balance):.2f}"
    except:
        return "0.00"

def get_date_reset_time():
    bd_now = get_bangladesh_time()
    return datetime(bd_now.year, bd_now.month, bd_now.day)

def is_range_request(param):
    if re.match(r'^\d+[xX]+$', str(param)):
        return True
    return False

def is_referral_request(param):
    if str(param).isdigit():
        return True
    return False

def extract_link_and_otp(full_sms):
    if not full_sms:
        return None, None
    otp_match = re.search(r'\b\d{4,8}\b', full_sms)
    otp = otp_match.group(0) if otp_match else None
    
    link_match = re.search(r'https?://[^\s]+', full_sms)
    link = link_match.group(0) if link_match else None
    
    return otp, link

def numbers_match(num1, num2):
    n1 = re.sub(r'\D', '', str(num1))
    n2 = re.sub(r'\D', '', str(num2))
    if not n1 or not n2:
        return False
    return n1 in n2 or n2 in n1

# ==================== TEXT BOLD / STYLIZED UNICODE HELPER ====================

def make_bold_unicode(text):
    out = []
    for char in text:
        codepoint = ord(char)
        if 65 <= codepoint <= 90:  # A-Z
            out.append(chr(codepoint - 65 + 0x1D5D4))
        elif 97 <= codepoint <= 122:  # a-z
            out.append(chr(codepoint - 97 + 0x1D5EE))
        elif 48 <= codepoint <= 57:  # 0-9
            out.append(chr(codepoint - 48 + 0x1D7EC))
        else:
            out.append(char)
    return "".join(out)

def normalize_stylized_text(text):
    if not text:
        return ""
    out = []
    for char in text:
        cp = ord(char)
        # Mathematical Bold Sans-Serif Capital (A-Z)
        if 0x1D5D4 <= cp <= 0x1D5ED:
            out.append(chr(cp - 0x1D5D4 + 65))
        # Mathematical Bold Sans-Serif Lowercase (a-z)
        elif 0x1D5EE <= cp <= 0x1D607:
            out.append(chr(cp - 0x1D5EE + 97))
        # Mathematical Bold Sans-Serif Digits (0-9)
        elif 0x1D7EC <= cp <= 0x1D7F5:
            out.append(chr(cp - 0x1D7EC + 48))
        else:
            out.append(char)
    return "".join(out)

def clean_country_display(val):
    if not val:
        return ""
    return re.sub(r'\s+', ' ', str(val)).strip().lower()

# ==================== CHECK IF USER IS ADMIN ====================

def is_admin(user_id):
    return user_id in ADMINS

# ==================== WITHDRAW DATA FUNCTIONS ====================

def load_withdraw_requests():
    if not os.path.exists(WITHDRAW_DATA_FILE):
        with open(WITHDRAW_DATA_FILE, "w") as f:
            json.dump({}, f)
        return {}
    try:
        with open(WITHDRAW_DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_withdraw_requests(data):
    with open(WITHDRAW_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def generate_payment_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))

# ==================== BANNED USERS FUNCTIONS ====================

def load_banned_users():
    if not os.path.exists(BANNED_USERS_FILE):
        with open(BANNED_USERS_FILE, "w") as f:
            json.dump([], f)
        return []
    try:
        with open(BANNED_USERS_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_banned_users(banned_list):
    with open(BANNED_USERS_FILE, "w") as f:
        json.dump(banned_list, f, indent=4)

def is_user_banned(uid):
    banned_list = load_banned_users()
    return str(uid) in banned_list

def ban_user(uid):
    banned_list = load_banned_users()
    uid_str = str(uid)
    if uid_str not in banned_list:
        banned_list.append(uid_str)
        save_banned_users(banned_list)
        return True
    return False

def unban_user(uid):
    banned_list = load_banned_users()
    uid_str = str(uid)
    if uid_str in banned_list:
        banned_list.remove(uid_str)
        save_banned_users(banned_list)
        return True
    return False

# ==================== REFERRAL DATA FUNCTIONS ====================

def load_referral_data():
    if not os.path.exists(REFERRAL_DATA_FILE):
        with open(REFERRAL_DATA_FILE, "w") as f:
            json.dump({}, f)
        return {}
    try:
        with open(REFERRAL_DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_referral_data(data):
    with open(REFERRAL_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def update_referral_count(uid, count):
    referral_data = load_referral_data()
    uid_str = str(uid)
    if uid_str not in referral_data:
        referral_data[uid_str] = {"referral_count": 0}
    referral_data[uid_str]["referral_count"] = count
    save_referral_data(referral_data)

def get_referral_count(uid):
    referral_data = load_referral_data()
    uid_str = str(uid)
    return referral_data.get(uid_str, {}).get("referral_count", 0)

# ==================== DATA RANGE FILE ====================

def load_range_db():
    if not os.path.exists(DATA_RANGE_FILE):
        return {}
    try:
        with open(DATA_RANGE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_range_db(data):
    with open(DATA_RANGE_FILE, "w") as f:
        json.dump(data, f, indent=4)

def save_number_range_info(uid, number, range_text):
    db = load_range_db()
    flag, name = get_country_info(number)
    db[normalize_number(number)] = {
        "user_id": str(uid),
        "number": f"+{normalize_number(number)}",
        "range": range_text,
        "country": f"{flag} {name}"
    }
    save_range_db(db)

# ==================== CUSTOM SERVICE CONFIG ====================

def load_custom_services():
    if not os.path.exists(CUSTOM_SERVICES_FILE):
        with open(CUSTOM_SERVICES_FILE, "w") as f:
            json.dump([], f)
        return []
    try:
        with open(CUSTOM_SERVICES_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_custom_services(data):
    with open(CUSTOM_SERVICES_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ==================== COUNTRY MAPPING SECTION ====================

def get_country_info(number):
    number = str(number).strip()

    country_map = {
        "2376": ("🇨🇲", "Cameroon"),
        "2250": ("🇨🇮", "Ivory Coast"),
        "2613": ("🇲🇬", "Madagascar"),
        "4077": ("🇷🇴", "Romania"),
        "237": ("🇨🇲", "Cameroon"),
        "225": ("🇨🇮", "Ivory Coast"),
        "261": ("🇲🇬", "Madagascar"),
        "20": ("🇪🇬", "Egypt"),
        "27": ("🇿🇦", "South Africa"),
        "234": ("🇳🇬", "Nigeria"),
        "254": ("🇰🇪", "Kenya"),
        "233": ("🇬🇭", "Ghana"),
        "212": ("🇲🇦", "Morocco"),
        "213": ("🇩🇿", "Algeria"),
        "216": ("🇹🇳", "Tunisia"),
        "218": ("🇱🇾", "Libya"),
        "249": ("🇸🇩", "Sudan"),
        "251": ("🇪🇹", "Ethiopia"),
        "252": ("🇸🇴", "Somalia"),
        "253": ("🇩🇯", "Djibouti"),
        "255": ("🇹🇿", "Tanzania"),
        "256": ("🇺🇬", "Uganda"),
        "257": ("🇧🇮", "Burundi"),
        "258": ("🇲🇿", "Mozambique"),
        "260": ("🇿🇲", "Zambia"),
        "263": ("🇿🇼", "Zimbabwe"),
        "264": ("🇳🇦", "Namibia"),
        "265": ("🇲🇼", "Malawi"),
        "266": ("🇱🇸", "Lesotho"),
        "267": ("🇧🇼", "Botswana"),
        "268": ("🇸🇿", "Swaziland"),
        "269": ("🇰🇲", "Comoros"),
        "220": ("🇬🇲", "Gambia"),
        "221": ("🇸🇳", "Senegal"),
        "222": ("🇲🇷", "Mauritania"),
        "223": ("🇲🇱", "Mali"),
        "224": ("🇬🇳", "Guinea"),
        "226": ("🇧🇫", "Burkina Faso"),
        "227": ("🇳🇪", "Niger"),
        "228": ("🇹🇬", "Togo"),
        "229": ("🇧🇯", "Benin"),
        "230": ("🇲🇺", "Mauritius"),
        "231": ("🇱🇷", "Liberia"),
        "232": ("🇸🇱", "Sierra Leone"),
        "235": ("🇹🇩", "Chad"),
        "236": ("🇨🇫", "Central African Republic"),
        "238": ("🇨🇻", "Cape Verde"),
        "239": ("🇸🇹", "Sao Tome and Principe"),
        "240": ("🇬🇶", "Equatorial Guinea"),
        "241": ("🇬🇦", "Gabon"),
        "242": ("🇨🇬", "Congo"),
        "243": ("🇨🇩", "DR Congo"),
        "244": ("🇦🇴", "Angola"),
        "245": ("🇬🇼", "Guinea-Bissau"),
        "247": ("🇸🇭", "Saint Helena"),
        "248": ("🇸🇨", "Seychelles"),
        "250": ("🇷🇼", "Rwanda"),
        "290": ("🇸🇭", "Saint Helena"),
        "291": ("🇪🇷", "Eritrea"),
        "40": ("🇷🇴", "Romania"),
        "44": ("🇬🇧", "United Kingdom"),
        "33": ("🇫🇷", "France"),
        "49": ("🇩🇪", "Germany"),
        "39": ("🇮🇹", "Italy"),
        "34": ("🇪🇸", "Spain"),
        "31": ("🇳🇱", "Netherlands"),
        "32": ("🇧🇪", "Belgium"),
        "41": ("🇨🇭", "Switzerland"),
        "43": ("🇦🇹", "Austria"),
        "46": ("🇸🇪", "Sweden"),
        "47": ("🇳🇴", "Norway"),
        "45": ("🇩👑", "Denmark"),
        "358": ("🇫🇮", "Finland"),
        "351": ("🇵🇹", "Portugal"),
        "353": ("🇮🇪", "Ireland"),
        "36": ("🇭🇺", "Hungary"),
        "48": ("🇵🇱", "Poland"),
        "380": ("🇺🇦", "Ukraine"),
        "370": ("🇱🇹", "Lithuania"),
        "371": ("🇱🇻", "Latvia"),
        "372": ("🇪🇪", "Estonia"),
        "373": ("🇲🇩", "Moldova"),
        "374": ("🇦🇲", "Armenia"),
        "375": ("🇧🇾", "Belarus"),
        "376": ("🇦🇩", "Andorra"),
        "377": ("🇲🇨", "Monaco"),
        "381": ("🇷🇸", "Serbia"),
        "382": ("🇲🇪", "Montenegro"),
        "385": ("🇭🇷", "Croatia"),
        "386": ("🇸🇮", "Slovenia"),
        "387": ("🇧🇦", "Bosnia and Herzegovina"),
        "389": ("🇲🇰", "North Macedonia"),
        "350": ("🇬🇮", "Gibraltar"),
        "352": ("🇱🇺", "Luxembourg"),
        "354": ("🇮🇸", "Iceland"),
        "355": ("🇦🇱", "Albania"),
        "356": ("🇲🇹", "Malta"),
        "357": ("🇨🇾", "Cyprus"),
        "359": ("🇧🇬", "Bulgaria"),
        "421": ("🇸🇰", "Slovakia"),
        "420": ("🇨🇿", "Czech Republic"),
        "298": ("🇫🇴", "Faroe Islands"),
        "299": ("🇬🇱", "Greenland"),
        "1": ("🇺🇸", "United States"),
        "7": ("🇷🇺", "Russia"),
        "91": ("🇮🇳", "India"),
        "92": ("🇵🇰", "Pakistan"),
        "880": ("🇧🇩", "Bangladesh"),
        "86": ("🇨🇳", "China"),
        "81": ("🇯🇵", "Japan"),
        "82": ("🇰🇷", "South Korea"),
        "84": ("🇻🇳", "Vietnam"),
        "66": ("🇹🇭", "Thailand"),
        "62": ("🇮🇩", "Indonesia"),
        "60": ("🇲🇾", "Malaysia"),
        "65": ("🇸🇬", "Singapore"),
        "63": ("🇵🇭", "Philippines"),
        "95": ("🇲🇲", "Myanmar"),
        "94": ("🇱🇰", "Sri Lanka"),
        "977": ("🇳🇵", "Nepal"),
        "93": ("🇦𝒇", "Afghanistan"),
        "98": ("🇮🇷", "Iran"),
        "90": ("🇹🇷", "Turkey"),
        "964": ("🇮🇶", "Iraq"),
        "963": ("🇸🇾", "Syria"),
        "961": ("🇱🇧", "Lebanon"),
        "962": ("🇯🇴", "Jordan"),
        "965": ("🇰🇼", "Kuwait"),
        "966": ("🇸🇦", "Saudi Arabia"),
        "967": ("🇾🇲", "Yemen"),
        "968": ("🇴🇲", "Oman"),
        "971": ("🇦🇪", "United Arab Emirates"),
        "972": ("🇮🇱", "Israel"),
        "973": ("🇧🇭", "Bahrain"),
        "974": ("🇶🇦", "Qatar"),
        "994": ("🇦🇿", "Azerbaijan"),
        "995": ("🇬🇪", "Georgia"),
        "996": ("🇰🇬", "Kyrgyzstan"),
        "992": ("🇹𝒋", "Tajikistan"),
        "993": ("🇹🇲", "Turkmenistan"),
        "998": ("🇺🇿", "Uzbekistan"),
        "855": ("🇰🇭", "Cambodia"),
        "856": ("🇱🇦", "Laos"),
        "976": ("🇲🇳", "Mongolia"),
        "850": ("🇰🇵", "North Korea"),
        "55": ("🇧🇷", "Brazil"),
        "52": ("🇲🇽", "Mexico"),
        "54": ("🇦🇷", "Argentina"),
        "57": ("🇨🇴", "Colombia"),
        "51": ("🇵🇪", "Peru"),
        "58": ("🇻🇪", "Venezuela"),
        "56": ("🇨🇱", "Chile"),
        "593": ("🇪🇨", "Ecuador"),
        "591": ("🇧🇴", "Bolivia"),
        "595": ("🇵🇾", "Paraguay"),
        "598": ("🇺🇾", "Uruguay"),
        "502": ("🇬🇹", "Guatemala"),
        "503": ("🇸𝑽", "El Salvador"),
        "504": ("🇭🇳", "Honduras"),
        "506": ("🇨🇷", "Costa Rica"),
        "507": ("🇵🇦", "Panama"),
        "509": ("🇭🇹", "Haiti"),
        "501": ("🇧🇿", "Belize"),
        "61": ("🇦🇺", "Australia"),
        "64": ("🇳🇿", "New Zealand"),
        "675": ("🇵🇬", "Papua New Guinea"),
        "679": ("🇫يج", "Fiji"),
        "1246": ("🇧🇧", "Barbados"),
        "1876": ("🇯🇲", "Jamaica"),
        "53": ("🇨🇺", "Cuba"),
        "592": ("🇬🇾", "Guyana"),
    }

    clean_num = str(number).replace('+', '').replace(' ', '').replace('-', '').strip()
    sorted_prefixes = sorted(country_map.keys(), key=len, reverse=True)

    for prefix in sorted_prefixes:
        if clean_num.startswith(prefix):
            return country_map[prefix]

    return ("🌍", "Unknown")

# ==================== SERVICE DETECTION SECTION ====================

def detect_service(full_sms):
    if not full_sms:
        return "SMS SERVICE"

    sms_lower = full_sms.lower()

    service_keywords = {
        "facebook": "FACEBOOK", "fb": "FACEBOOK",
        "instagram": "INSTAGRAM", "insta": "INSTAGRAM",
        "tiktok": "TIKTOK",
        "twitter": "TWITTER", "x.com": "TWITTER",
        "snapchat": "SNAPCHAT", "snap": "SNAPCHAT",
        "whatsapp": "WHATSAPP",
        "telegram": "TELEGRAM",
        "discord": "DISCORD",
        "messenger": "MESSENGER",
        "linkedin": "LINKEDIN",
        "google": "GOOGLE", "gmail": "GOOGLE",
        "amazon": "AMAZON",
        "microsoft": "MICROSOFT", "outlook": "MICROSOFT",
        "yahoo": "YAHOO",
        "paypal": "PAYPAL",
        "binance": "BINANCE",
        "coinbase": "COINBASE",
        "spotify": "SPOTIFY",
        "netflix": "NETFLIX",
        "uber": "UBER",
        "apple": "APPLE", "icloud": "APPLE",
        "bkash": "BKASH",
        "nagad": "NAGAD",
        "stripe": "STRIPE",
        "line": "LINE",
        "wechat": "WECHAT",
        "viber": "VIBER",
        "signal": "SIGNAL",
        "pubg": "PUBG",
        "free fire": "FREE FIRE",
    }

    for keyword, service_name in sorted(service_keywords.items(), key=lambda x: len(x[0]), reverse=True):
        if keyword in sms_lower:
            return service_name

    return "SMS SERVICE"

# ==================== KEYBOARDS SECTION ====================

def main_keyboard(user_id):
    keyboard = [
        [KeyboardButton(text=f"📞 {make_bold_unicode('GET NUMBER')}", style="primary")],
        [
            KeyboardButton(text=f"👥 {make_bold_unicode('REFER AND EARN')}", style="primary"),
            KeyboardButton(text=f"👤 {make_bold_unicode('PROFILE')}", style="primary")
        ],
        [KeyboardButton(text=f"🏆 {make_bold_unicode('LEADERBOARD')}", style="primary")],
        [KeyboardButton(text=f"💬 {make_bold_unicode('SUPPORT')}", style="primary")]
    ]

    if is_admin(user_id):
        keyboard.append([KeyboardButton(text=f"⚙️ {make_bold_unicode('ADMIN PANEL')} ⚙️", style="danger")])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def cancel_keyboard():
    keyboard = [[KeyboardButton(f"❌ {make_bold_unicode('CANCEL')}", style="danger")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def withdraw_method_keyboard():
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton(f"📱 {make_bold_unicode('BKASH')}", style="primary"), KeyboardButton(f"💵 {make_bold_unicode('NAGAD')}", style="primary")],
        [KeyboardButton(f"🚀 {make_bold_unicode('ROCKET')}", style="primary"), KeyboardButton(f"🏦 {make_bold_unicode('BINANCE')}", style="primary")],
        [KeyboardButton(f"❌ {make_bold_unicode('CANCEL')}", style="danger")]
    ], resize_keyboard=True)
    return keyboard

# ==================== DYNAMIC SERVICE COLOR MATCHING ====================

def get_service_button_style(service_name):
    return "primary"

# ==================== COMPREHENSIVE INLINE ADMIN PANEL FLOW ====================

def get_grouped_countries_for_service(service):
    grouped = {}
    for r in service.get("ranges", []):
        r_text = r.get("range", "")
        country_display = r.get("country", "")
        
        match = re.match(r'^([^\w\s]*)\s*(.*)$', country_display)
        if match:
            flag = match.group(1).strip()
            cname = match.group(2).strip()
        else:
            flag = "🌍"
            cname = "Unknown"
            
        if not cname:
            cname = "Unknown"
            
        if cname not in grouped:
            grouped[cname] = {"flag": flag, "ranges": []}
        if r_text not in grouped[cname]["ranges"]:
            grouped[cname]["ranges"].append(r_text)
    return grouped

def build_admin_main_inline_keyboard():
    buttons = [
        [InlineKeyboardButton(make_bold_unicode("👥 USER MANAGEMENT"), callback_data="adm_menu_user_mgnt", style="primary")],
        [InlineKeyboardButton(make_bold_unicode("⚙️ SYSTEM CONFIGURATION"), callback_data="adm_menu_sys_config", style="primary")],
        [InlineKeyboardButton(make_bold_unicode("🛠️ MANAGE SERVICES"), callback_data="manage_svc_back_to_list", style="primary")],
        [InlineKeyboardButton(make_bold_unicode("🔙 BACK TO MAIN MENU"), callback_data="adm_menu_back_to_main", style="danger")]
    ]
    return InlineKeyboardMarkup(buttons)

def build_user_management_inline_keyboard():
    buttons = [
        [InlineKeyboardButton(make_bold_unicode("📢 BROADCAST TO ALL"), callback_data="adm_usermgnt_broadcast", style="primary")],
        [InlineKeyboardButton(make_bold_unicode("🆔 GET ALL USER ID"), callback_data="adm_usermgnt_get_ids", style="primary")],
        [InlineKeyboardButton(make_bold_unicode("💰 ALL USER BALANCE"), callback_data="adm_usermgnt_all_balance", style="primary")],
        [InlineKeyboardButton(make_bold_unicode("🔙 BACK"), callback_data="adm_menu_back_to_admin", style="danger")]
    ]
    return InlineKeyboardMarkup(buttons)

def build_system_config_inline_keyboard():
    buttons = [
        [
            InlineKeyboardButton(make_bold_unicode("📈 SYSTEM STATS"), callback_data="adm_sys_stats", style="primary"),
            InlineKeyboardButton(make_bold_unicode("👤 USER CHECK"), callback_data="adm_sys_user_check", style="primary")
        ],
        [
            InlineKeyboardButton(make_bold_unicode("⛔ BAN USER"), callback_data="adm_sys_ban", style="danger"),
            InlineKeyboardButton(make_bold_unicode("🔓 UNBAN USER"), callback_data="adm_sys_unban", style="success")
        ],
        [InlineKeyboardButton(make_bold_unicode("📜 BANNED LIST"), callback_data="adm_sys_banned_list", style="primary")],
        [
            InlineKeyboardButton(make_bold_unicode("➕ ADD BALANCE"), callback_data="adm_sys_add_bal", style="success"),
            InlineKeyboardButton(make_bold_unicode("➖ REMOVE BALANCE"), callback_data="adm_sys_rem_bal", style="danger")
        ],
        [InlineKeyboardButton(make_bold_unicode("🔙 BACK"), callback_data="adm_menu_back_to_admin", style="danger")]
    ]
    return InlineKeyboardMarkup(buttons)

def build_manage_services_inline_keyboard():
    custom_svcs = load_custom_services()
    buttons = []
    for s in custom_svcs:
        sid = s.get("sid", "UNKNOWN")
        buttons.append([InlineKeyboardButton(make_bold_unicode(f"📁 {sid.upper()}"), callback_data=f"manage_svc_view_{sid}", style="primary")])
    buttons.append([InlineKeyboardButton(make_bold_unicode("➕ ADD SERVICE"), callback_data="manage_svc_add", style="success")])
    buttons.append([InlineKeyboardButton(make_bold_unicode("🔙 BACK"), callback_data="adm_menu_back_to_admin", style="danger")])
    return InlineKeyboardMarkup(buttons)

def build_service_detail_keyboard(service_name):
    custom_svcs = load_custom_services()
    target_svc = next((s for s in custom_svcs if s.get("sid", "").upper() == service_name.upper()), None)
    if not target_svc:
        return None
        
    grouped = get_grouped_countries_for_service(target_svc)
    buttons = []
    
    for cname, info in grouped.items():
        flag = info["flag"]
        buttons.append([InlineKeyboardButton(make_bold_unicode(f"{flag} {cname.upper()}"), callback_data=f"manage_svc_country_view_{service_name}_{cname}", style="primary")])
        
    buttons.append([
        InlineKeyboardButton(make_bold_unicode("➕ ADD RANGE"), callback_data=f"manage_svc_add_range_{service_name}", style="success"),
        InlineKeyboardButton(make_bold_unicode("✏️ RENAME"), callback_data=f"manage_svc_rename_init_{service_name}", style="primary")
    ])
    buttons.append([
        InlineKeyboardButton(make_bold_unicode("🗑️ DELETE SERVICE"), callback_data=f"manage_svc_delete_init_{service_name}", style="danger")
    ])
    buttons.append([InlineKeyboardButton(make_bold_unicode("🔙 BACK"), callback_data="manage_svc_back_to_list", style="danger")])
    return InlineKeyboardMarkup(buttons)

def build_country_detail_keyboard(service_name, country_name):
    custom_svcs = load_custom_services()
    target_svc = next((s for s in custom_svcs if s.get("sid", "").upper() == service_name.upper()), None)
    if not target_svc:
        return None
        
    grouped = get_grouped_countries_for_service(target_svc)
    info = grouped.get(country_name, {"flag": "🌍", "ranges": []})
    
    buttons = []
    for r_val in info["ranges"]:
        buttons.append([
            InlineKeyboardButton(make_bold_unicode(f"❌ {r_val}"), callback_data=f"manage_svc_delete_range_{service_name}_{country_name}_{r_val}", style="danger"),
            InlineKeyboardButton(make_bold_unicode("✏️ EDIT"), callback_data=f"manage_svc_edit_range_init_{service_name}_{country_name}_{r_val}", style="primary")
        ])
        
    buttons.append([
        InlineKeyboardButton(make_bold_unicode("➕ ADD RANGE"), callback_data=f"manage_svc_add_range_{service_name}_{country_name}", style="success"),
        InlineKeyboardButton(make_bold_unicode("✏️ RENAME COUNTRY"), callback_data=f"manage_svc_rename_country_init_{service_name}_{country_name}", style="primary")
    ])
    buttons.append([InlineKeyboardButton(make_bold_unicode("🗑️ DELETE COUNTRY"), callback_data=f"manage_svc_delete_country_confirm_{service_name}_{country_name}", style="danger")])
    buttons.append([InlineKeyboardButton(make_bold_unicode("🔙 BACK"), callback_data=f"manage_svc_view_{service_name}", style="primary")])
    return InlineKeyboardMarkup(buttons)

def get_admin_panel_text():
    users_list = get_all_users()
    users = len(users_list)
    banned = len(load_banned_users())
    
    custom_svcs = load_custom_services()
    total_ranges = sum(len(s.get("ranges", [])) for s in custom_svcs)
    
    stats_data = load_stats()
    total_otps = 0
    for u in stats_data.values():
        total_otps += len(u.get("otps_received", []))
    
    text = (
        "👑 <b>ADMIN CONTROL PANEL</b> 👑\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 <b>REAL-TIME DATABASE STATS</b>\n\n"
        f"👥 <b>Total Users:</b> <code>{users}</code>\n"
        f"📶 <b>Active Ranges:</b> <code>{total_ranges}</code>\n"
        f"🔑 <b>Processed OTPs:</b> <code>{total_otps}</code>\n"
        f"🚫 <b>Banned Accounts:</b> <code>{banned}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 <i>ZEBRA SMS Bot • Live & Operating</i>"
    )
    return text

# ==================== CHAT GUARD AND SAFETY FILTER ====================

def is_state_cancelling_input(text_input):
    if not text_input:
        return False
    clean_text = text_input.strip().upper()
    if clean_text.startswith("/"):
        return True
    
    cancelling_keywords = [
        "👥 USER MANAGEMENT", "⚙️ SYSTEM CONFIGURATION", "🛠️ MANAGE SERVICES",
        "🔙 BACK TO MAIN", "⚙️ ADMIN PANEL ⚙️", "📞 GET NUMBER", "💰 BALANCE",
        "👥 REFER AND EARN", "👤 PROFILE", "🏆 LEADERBOARD", "💬 SUPPORT", "❌ CANCEL"
    ]
    return clean_text in cancelling_keywords

# ==================== DATABASE FUNCTIONS SECTION ====================

def load_data(filename=USER_DATA_FILE):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump({}, f)
        return {}
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data, filename=USER_DATA_FILE):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

def get_user(uid):
    uid = str(uid)
    data = load_data()
    if uid not in data:
        data[uid] = {"user_id": uid, "balance": 0.0, "total_numbers": 0, "referral_count": 0}
        save_data(data)
    return data[uid]

async def update_db_balance(uid, amount):
    uid = str(uid)
    data = load_data()
    if uid in data:
        data[uid]["balance"] = round(data[uid].get("balance", 0.0) + amount, 2)
        save_data(data)
        return data[uid]["balance"]
    return 0.0

def get_all_users():
    data = load_data(USER_DATA_FILE)
    return list(data.keys()) if data else []

def user_exists(uid):
    data = load_data(USER_DATA_FILE)
    return str(uid) in data

# ==================== STATS FUNCTIONS SECTION ====================

def load_stats():
    if not os.path.exists(STATS_FILE):
        with open(STATS_FILE, "w") as f:
            json.dump({}, f)
        return {}
    try:
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_stats(stats):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=4)

def add_number_taken(uid, count=1):
    uid = str(uid)
    stats = load_stats()
    if uid not in stats:
        stats[uid] = {"numbers_taken": [], "otps_received": []}
    if "numbers_taken" not in stats[uid]:
        stats[uid]["numbers_taken"] = []
    now = get_bangladesh_time().isoformat()
    for _ in range(count):
        stats[uid]["numbers_taken"].append(now)
    log_global_activity(uid, "NUMBER_TAKEN", {"count": count})
    save_stats(stats)

def add_otp_received(uid):
    uid = str(uid)
    stats = load_stats()
    if uid not in stats:
        stats[uid] = {"numbers_taken": [], "otps_received": []}
    if "otps_received" not in stats[uid]:
        stats[uid]["otps_received"] = []
    stats[uid]["otps_received"].append(get_bangladesh_time().isoformat())
    save_stats(stats)

def get_user_stats(uid):
    uid = str(uid)
    stats = load_stats()
    user_stats = stats.get(uid, {"numbers_taken": [], "otps_received": []})

    now = get_bangladesh_time()
    today_midnight = get_date_reset_time()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    numbers_taken = user_stats.get("numbers_taken", [])
    otps_received = user_stats.get("otps_received", [])

    today_numbers = 0
    today_otps = 0
    last24h_numbers = 0
    last24h_otps = 0
    last7d_numbers = 0
    last7d_otps = 0

    for t in numbers_taken:
        try:
            dt = datetime.fromisoformat(t)
            if dt >= today_midnight: today_numbers += 1
            if dt > last_24h: last24h_numbers += 1
            if dt > last_7d: last7d_numbers += 1
        except:
            continue

    for t in otps_received:
        try:
            dt = datetime.fromisoformat(t)
            if dt >= today_midnight: today_otps += 1
            if dt > last_24h: last24h_otps += 1
            if dt > last_7d: last7d_otps += 1
        except:
            continue

    total_numbers = len(numbers_taken)
    total_otps = len(otps_received)

    return {
        "total_numbers": total_numbers, "total_otps": total_otps,
        "today_numbers": today_numbers, "today_otps": today_otps,
        "last24h_numbers": last24h_numbers, "last24h_otps": last24h_otps,
        "last7d_numbers": last7d_numbers, "last7d_otps": last7d_otps
    }

def log_global_activity(uid, action, details):
    if not os.path.exists(ACTIVITY_LOGS_FILE):
        with open(ACTIVITY_LOGS_FILE, "w") as f:
            json.dump([], f)
    try:
        with open(ACTIVITY_LOGS_FILE, "r") as f:
            logs = json.load(f)
    except:
        logs = []
    now = get_bangladesh_time()
    logs.append({
        "uid": str(uid), "action": action, "details": details,
        "timestamp": now.isoformat(),
        "date": now.strftime("%d/%m/%Y"),
        "time": now.strftime("%H:%M:%S")
    })
    with open(ACTIVITY_LOGS_FILE, "w") as f:
        json.dump(logs, f, indent=4)

def get_global_system_stats():
    stats = load_stats()
    now = get_bangladesh_time()
    today_midnight = datetime(now.year, now.month, now.day)
    last_7d = now - timedelta(days=7)
    total_n = total_o = today_n = today_o = seven_n = seven_o = 0
    for uid in stats:
        u = stats[uid]
        n_list = u.get("numbers_taken", [])
        o_list = u.get("otps_received", [])
        total_n += len(n_list)
        total_o += len(o_list)
        for t in n_list:
            try:
                dt = datetime.fromisoformat(t)
                if dt >= today_midnight: today_n += 1
                if dt >= last_7d: seven_n += 1
            except:
                continue
        for t in o_list:
            try:
                dt = datetime.fromisoformat(t)
                if dt >= today_midnight: today_o += 1
                if dt >= last_7d: seven_o += 1
            except:
                continue
    return today_n, today_o, seven_n, seven_o, total_n, total_o

# ==================== LEADERBOARD SECTION ====================

async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_user_banned(uid):
        await update.message.reply_text("🚫 YOU ARE BANNED 🚫", reply_markup=main_keyboard(uid))
        return

    stats_data = load_stats()
    today_midnight = get_date_reset_time()
    user_data_all = load_data(USER_DATA_FILE)

    user_today_counts = []

    for uid_str, user_stats in stats_data.items():
        otps_received = user_stats.get("otps_received", [])
        today_count = 0
        for ts in otps_received:
            try:
                dt = datetime.fromisoformat(ts)
                if dt >= today_midnight:
                    today_count += 1
            except:
                continue
        if today_count > 0:
            name = user_data_all.get(uid_str, {}).get("full_name")
            if not name:
                name = user_data_all.get(uid_str, {}).get("username")
            if not name:
                name = f"User {uid_str}"
            user_today_counts.append((uid_str, today_count, html.escape(name)))

    user_today_counts.sort(key=lambda x: x[1], reverse=True)
    top10 = user_today_counts[:10]

    if not top10:
        msg = (
            "<b>🏆 TOP 10 OTP LEADERBOARD 🏆</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "❌ আজ পর্যন্ত কেউ OTP পায়নি।\n"
        )
    else:
        msg = (
            "<b>🏆 TOP 10 OTP RECEIVERS (TODAY) 🏆</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        for idx, (uid_str, count, name) in enumerate(top10, 1):
            if idx == 1:
                medal = "🥇"
            elif idx == 2:
                medal = "🥈"
            elif idx == 3:
                medal = "🥉"
            else:
                medal = f"{idx}️⃣"
            msg += f"{medal} <b>{name}</b>\n   🔑 <code>{count}</code> OTPs\n\n"
        msg += (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📊 <i>প্রতিদিন রাত ১২টায় রিসেট হয়</i>"
        )

    await update.message.reply_text(msg, parse_mode="HTML", reply_markup=main_keyboard(uid))

# ==================== GET NUMBER — SERVICE SELECTION ====================

def _build_services_keyboard(services):
    temp_btns = []
    for i, svc in enumerate(services):
        sid   = svc.get("sid", f"Service {i+1}")
        ranges = svc.get("ranges", [])
        label  = f"🚀 {sid} ({len(ranges)})"
        
        temp_btns.append(InlineKeyboardButton(label, callback_data=f"svc_{i}", style="primary"))
        
    rows = [temp_btns[j:j+2] for j in range(0, len(temp_btns), 2)]
    return InlineKeyboardMarkup(rows)

def _build_countries_keyboard(ranges, service_idx):
    btns = []
    seen = {}
    for i, r_item in enumerate(ranges[:24]):
        r_text = r_item.get("range", "")
        country_display = r_item.get("country", "")
        if not country_display:
            prefix = re.sub(r'[xX]+$', '', str(r_text)).strip()
            prefix_clean = re.sub(r'\D', '', prefix)
            flag, cname = get_country_info(prefix_clean)
            country_display = f"{flag} {cname}"

        label = f"{country_display}"
        if label not in seen:
            seen[label] = i
            btns.append(InlineKeyboardButton(label, callback_data=f"rng_{i}", style="primary"))
    rows = [btns[j:j+2] for j in range(0, len(btns), 2)]
    rows.append([InlineKeyboardButton("◀️ BACK", callback_data="back_services", style="danger")])
    return InlineKeyboardMarkup(rows)

async def show_app_selection(update, context):
    uid = update.effective_user.id
    if is_user_banned(uid):
        await update.message.reply_text("🚫 YOU ARE BANNED 🚫", reply_markup=main_keyboard(uid))
        return

    services = load_custom_services()

    if not services:
        await update.message.reply_text(
            "⚠️ <b>দুঃখিত, এই মুহূর্তে কোনো সার্ভিস উপলব্ধ নেই।</b>\n⏳ অ্যাডমিন কর্তৃক সার্ভিস অ্যাড করার জন্য অপেক্ষা করুন।",
            parse_mode="HTML",
            reply_markup=main_keyboard(uid)
        )
        return

    context.user_data["la_services"] = services
    keyboard = _build_services_keyboard(services)
    await update.message.reply_text(
        "📞 <b>GET NUMBER</b>\n\n"
        "<blockquote>✨ নিচ থেকে আপনার পছন্দের <b>Service</b> নির্বাচন করুন:</blockquote>",
        parse_mode="HTML",
        reply_markup=keyboard
    )

# ==================== AUTO OTP MONITOR SECTION ====================

async def monitor_loop(app):
    while True:
        try:
            r = await client_async.get(f"{BASE_URL}/success_otp?api_key={API_KEY}")
            if r.status_code != 200:
                print(f"Monitor API Error: HTTP Status {r.status_code}")
                await asyncio.sleep(CHECK_INTERVAL)
                continue
                
            try:
                res = r.json()
            except json.JSONDecodeError:
                raw_text = r.text.strip()
                if raw_text and raw_text != "no_otp":
                    print(f"Monitor raw API non-JSON response: {raw_text[:100]}")
                await asyncio.sleep(CHECK_INTERVAL)
                continue
            
            otps = []
            if isinstance(res, dict):
                if "data" in res and isinstance(res["data"], dict) and "otps" in res["data"]:
                    otps = res["data"]["otps"]
                elif "otps" in res:
                    otps = res["otps"]
                elif "data" in res and isinstance(res["data"], list):
                    otps = res["data"]
            elif isinstance(res, list):
                otps = res

            if otps:
                paid_data = load_data(PAID_SMS_FILE)
                range_db = load_data(DATA_RANGE_FILE)
                paid_keys_set = set(paid_data.keys())
                processed_in_session = set()

                for otp in otps:
                    num = normalize_number(otp.get("number") or otp.get("phone") or otp.get("to") or "")
                    full_sms = (
                        otp.get('message') or 
                        otp.get('otp') or 
                        otp.get('sms') or 
                        otp.get('text') or 
                        otp.get('msg') or 
                        otp.get('content') or 
                        "No SMS Content"
                    )
                    
                    ext_otp, ext_link = extract_link_and_otp(full_sms)
                    otp_code = otp.get("otp_code") or otp.get("otp") or ext_otp
                    
                    otp_id = str(otp.get("otp_id", ""))
                    sms_key = otp_id if otp_id else f"{num}_{full_sms}"

                    matched_key = None
                    for active_num in active_numbers.keys():
                        if numbers_match(num, active_num):
                            matched_key = active_num
                            break

                    if (matched_key is not None and
                            sms_key not in paid_keys_set and
                            sms_key not in processed_in_session):

                        details = active_numbers[matched_key]
                        paid_keys_set.add(sms_key)
                        processed_in_session.add(sms_key)
                        paid_data[sms_key] = {"uid": details["uid"], "otp": otp_code}

                        # রিয়েল-টাইম ব্যালেন্স ও ওটিপি স্ট্যাটস রাইট
                        await update_db_balance(details["uid"], OTP_RATE)
                        add_otp_received(details["uid"])
                        log_global_activity(details["uid"], "OTP_RECEIVED", {"number": matched_key, "otp": otp_code, "sms": full_sms})

                        num_range_info = range_db.get(matched_key, {}).get("range", "")
                        if not num_range_info:
                            num_range_info = active_numbers.get(matched_key, {}).get("range", "")
                        if not num_range_info and matched_key:
                            _d = re.sub(r'\D', '', str(matched_key))
                            num_range_info = (_d[:-3] + 'XXX') if len(_d) > 3 else (_d + 'XXX')

                        country_flag, country_name = get_country_info(matched_key)
                        service_name = detect_service(full_sms)
                        clean_num = matched_key.replace('+', '').strip()
                        full_number = f"+{clean_num}"
                        masked_number = f"+{mask_number(clean_num)}"

                        safe_full_sms = html.escape(str(full_sms))
                        safe_otp_code = html.escape(str(otp_code))

                        link_section = ""
                        if ext_link:
                            link_section = f"<blockquote>🔗 <b>LINK:</b> <a href='{ext_link}'>{ext_link}</a></blockquote>\n"

                        user_msg = (
                            f"✅ <b>OTP RECEIVE SUCCESSFUL</b> ✅\n\n"
                            f"<blockquote>🌍 COUNTRY: <code>{country_flag} {country_name}</code></blockquote>\n"
                            f"<blockquote>📱 SERVICE: <code>{service_name}</code></blockquote>\n"
                            f"<blockquote>📞 NUMBER: <code>{full_number}</code></blockquote>\n"
                            f"<blockquote>🔑 OTP: <code>{safe_otp_code}</code></blockquote>\n"
                            f"{link_section}\n"
                            f"<blockquote>📩 FULL SMS:\n<code>{safe_full_sms}</code></blockquote>\n\n"
                            f"<b>💵 ADD BALANCE FOR {OTP_RATE:.2f} BDT</b>"
                        )

                        group_msg = (
                            f"✅ <b>OTP RECEIVE SUCCESSFUL</b> ✅\n\n"
                            f"<blockquote>📶 RANGE: <code>{num_range_info}</code></blockquote>\n"
                            f"<blockquote>🌍 COUNTRY: <code>{country_flag} {country_name}</code></blockquote>\n"
                            f"<blockquote>📱 SERVICE: <code>{service_name}</code></blockquote>\n"
                            f"<blockquote>📞 NUMBER: <code>{masked_number}</code></blockquote>\n"
                            f"<blockquote>🔑 OTP: <code>{safe_otp_code}</code></blockquote>\n"
                            f"{link_section}\n"
                            f"<blockquote>📩 FULL SMS:\n<code>{safe_full_sms}</code></blockquote>"
                        )

                        group_buttons = InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("‼️ PANEL", url="https://t.me/ZebraXSupport0", style="primary"),
                                InlineKeyboardButton("📢 CHANNEL", url="https://t.me/ZebraXSupport0", style="primary")
                            ]
                        ])

                        try:
                            await app.bot.send_message(details["uid"], user_msg, parse_mode="HTML")
                        except Exception as e:
                            print(f"❌ User Message Send Fail: {e}")

                        try:
                            await app.bot.send_message(OTP_GROUP_ID, group_msg, parse_mode="HTML", reply_markup=group_buttons)
                        except Exception as e:
                            print(f"❌ Group Send Fail: {e}")

                        save_data(paid_data, PAID_SMS_FILE)

                current_time = datetime.now()
                for num_key in list(active_numbers.keys()):
                    entry = active_numbers[num_key]
                    if 'timestamp' not in entry:
                        entry['timestamp'] = current_time
                    elif (current_time - entry['timestamp']).total_seconds() > 3600:
                        del active_numbers[num_key]

        except Exception as e:
            print(f"Monitor Error: {e}")
        await asyncio.sleep(CHECK_INTERVAL)

# ==================== WORKER & API SECTION ====================

async def fetch_number_async(range_str):
    """
    যেকোনো এপিআই রেসপন্স (JSON, colon, pipe separated) অত্যন্ত দ্রুততার সাথে পার্স করে 
    সঠিক অ্যাক্টিভ নম্বরটি রিটার্ন করার জন্য অপ্টিমাইজড এপিআই পার্সার।
    """
    try:
        url = f"{BASE_URL}/getnumber?api_key={API_KEY}&rid={range_str}&range={range_str}&target={range_str}&national=1&remove_plus=1"
        r = await client_async.get(url)
        
        if r.status_code != 200:
            print(f"fetch_number_async Error: HTTP {r.status_code}")
            return None
            
        raw_text = r.text.strip()
        if not raw_text:
            return None
            
        # প্যানেলের বিভিন্ন এরর কীওয়ার্ডস স্কিপ করা
        err_keywords = ["NO_NUMBERS", "NO_NUMBER", "OUT_OF_STOCK", "BANNED", "LIMIT", "ERROR", "BALANCE", "EMPTY", "SQL"]
        if any(err in raw_text.upper() for err in err_keywords):
            return None

        # ১. JSON রেসপন্স পার্সিং
        try:
            data = r.json()
            if isinstance(data, dict):
                if str(data.get("status")).lower() in ["error", "fail", "false"]:
                    return None
                
                d = data.get("data") if isinstance(data.get("data"), dict) else data
                number = d.get("full_number") or d.get("number") or d.get("phone") or d.get("phoneNumber") or d.get("mobile")
                if number:
                    return {
                        "number": str(number),
                        "otp_now": bool(d.get("otp_now", False) or d.get("otp")),
                        "otp": d.get("otp"),
                        "sms": d.get("sms") or d.get("message"),
                    }
        except:
            pass

        # ২. টেক্সট রেসপন্স পার্সিং (ACCESS_NUMBER:ID:NUMBER বা ID|NUMBER বা ডিরেক্ট নম্বর)
        parts = re.split(r'[:|]', raw_text)
        for part in reversed(parts):
            clean_part = re.sub(r'\D', '', part.strip())
            # সাধারণত দেশীয়/আন্তর্জাতিক নম্বর ৭ থেকে ১৫ ডিজিট হয়ে থাকে
            if len(clean_part) >= 7 and len(clean_part) <= 15 and clean_part.isdigit():
                return {"number": clean_part, "otp_now": False, "otp": None, "sms": None}
                    
        # ৩. যদি স্প্লিট ছাড়া র টেক্সটেই শুধু নম্বর থাকে
        clean_all = re.sub(r'\D', '', raw_text)
        if len(clean_all) >= 7 and len(clean_all) <= 15 and clean_all.isdigit():
            return {"number": clean_all, "otp_now": False, "otp": None, "sms": None}

    except httpx.ReadTimeout:
        print(f"Fetch number error: ReadTimeout for range {range_str}. Server took too long to respond.")
    except Exception as e:
        print(f"Fetch number error: {e}")
    return None

async def fast_allocate_number_multi(query, context, ranges_list, sid):
    """
    ইউজার ক্লিক করার সাথে সাথে ইউআই-তে তাৎক্ষণিক লোডিং স্ট্যাটাস প্রদানের মাধ্যমে 
    ভুল বোঝাবুঝি দূর করে নম্বর এলোকেশন করার অপ্টিমাইজড মেথড।
    """
    uid = query.from_user.id

    if is_user_banned(uid):
        await query.message.edit_text("🚫 YOU ARE BANNED 🚫")
        return

    # কাজ করে না কিন্তু ঠিকই কাজ করে সমস্যাটি সমাধানের জন্য তাৎক্ষণিক ইউজার ফিডব্যাক লোডিং
    try:
        await query.message.edit_text(
            "⚡ <b>ALLOCATING YOUR NUMBER</b> ⚡\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔍 <i>Searching active pool... Please wait.</i>",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Edit loading state error: {e}")

    res = None
    successful_range = None
    for r_text in ranges_list:
        try:
            res = await fetch_number_async(r_text)
            if res and res.get("number"):
                successful_range = r_text
                break
        except Exception as e:
            print(f"Error trying range {r_text}: {e}")
            continue

    if not res or not res.get("number"):
        try:
            await query.message.edit_text(
                "❌ <b>Number পাওয়া যায়নি।</b>\n\n"
                "<blockquote>⚠️ এই range/country-তে এখন number নেই বা server busy।\n"
                "অন্য কোনো সার্ভিস বা কান্ট্রি চেষ্টা করুন।</blockquote>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 BACK", callback_data="back_services", style="danger")
                ]])
            )
        except:
            pass
        return

    clean_num = normalize_number(res["number"])
    add_number_taken(uid, 1)
    last_range[uid] = successful_range
    active_numbers[clean_num] = {"uid": uid, "range": successful_range, "timestamp": datetime.now()}
    save_number_range_info(uid, clean_num, successful_range)

    country_flag, country_name = get_country_info(clean_num)

    if res.get("otp_now") and res.get("otp"):
        otp_safe = html.escape(str(res["otp"]))
        sms_safe  = html.escape(str(res.get("sms") or ""))
        add_otp_received(uid)
        text = (
            f"✅ <b>YOUR NUMBER</b> ✅\n\n"
            f"<blockquote>🌍 COUNTRY: <code>{country_flag} {html.escape(country_name)}</code></blockquote>\n"
            f"<blockquote>📶 RANGE: <code>{successful_range}</code></blockquote>\n"
            f"<blockquote>📞 NUMBER: <code>+{clean_num}</code></blockquote>\n"
            f"<blockquote>🔑 OTP: <code>{otp_safe}</code></blockquote>"
            + (f"\n<blockquote>📩 SMS: <code>{sms_safe}</code></blockquote>" if sms_safe else "")
            + "\n\n<b>✅ OTP RECEIVED INSTANTLY!</b>"
        )
    else:
        text = (
            f"✅ <b>YOUR NUMBER</b> ✅\n\n"
            f"<blockquote>🌍 COUNTRY: <code>{country_flag} {html.escape(country_name)}</code></blockquote>\n"
            f"<blockquote>📶 RANGE: <code>{successful_range}</code></blockquote>\n"
            f"<blockquote>📞 NUMBER: <code>+{clean_num}</code></blockquote>\n\n"
            f"<b>📩 SMS STATUS: ⏳ WAITING...</b>"
        )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 SAME RANGE", callback_data="same_range", style="primary")],
        [InlineKeyboardButton("📢 OTP GROUP", url="https://t.me/ZebraXSupport0", style="primary")]
    ])
    try:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        print(f"fast_allocate edit error: {e}")

async def worker():
    while True:
        task = await request_queue.get()
        try:
            if task['type'] == 'process_numbers':
                await process_numbers(task['update'], task['context'], task['range_text'], task['count'])
            elif task['type'] == 'auto_number':
                await process_auto_number(task['update'], task['context'], task['range_text'])
        except Exception as e:
            print(f"Worker Error: {e}")
        finally:
            request_queue.task_done()

# ==================== AUTO NUMBER FROM LINK / DEEP LINK ====================

async def process_auto_number(update, context, range_text):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    if is_user_banned(uid):
        await context.bot.send_message(chat_id=chat_id, text="🚫 YOU ARE BANNED 🚫", reply_markup=main_keyboard(uid))
        return

    status_msg = await context.bot.send_message(chat_id=chat_id, text="🔍 SEARCHING...")

    try:
        res = await fetch_number_async(range_text)
        if not res:
            await status_msg.edit_text("❌ NO NUMBERS FOUND. TRY A VALID RANGE.")
            return

        generated_num = normalize_number(res["number"]) if res else None
        if not generated_num:
            await status_msg.edit_text("❌ NO NUMBERS FOUND. TRY A VALID RANGE.")
            return

        add_number_taken(uid, 1)
        last_range[uid] = range_text
        active_numbers[generated_num] = {"uid": uid, "range": range_text, "timestamp": datetime.now()}
        save_number_range_info(uid, generated_num, range_text)

        country_flag, country_name = get_country_info(generated_num)

        if res.get("otp_now") and res.get("otp"):
            instant_otp = html.escape(str(res["otp"]))
            instant_sms = html.escape(str(res.get("sms") or ""))
            add_otp_received(uid)
            final_text = (
                f"✅ <b>YOUR NUMBER DETAILS</b> ✅\n\n"
                f"<blockquote>🌍 COUNTRY: <code>{country_flag} {country_name}</code></blockquote>\n"
                f"<blockquote>📶 RANGE: <code>{range_text}</code></blockquote>\n\n"
                f"<blockquote>📞 NUMBER: <code>+{generated_num}</code></blockquote>\n\n"
                f"<blockquote>🔑 OTP: <code>{instant_otp}</code></blockquote>\n"
                + (f"<blockquote>📩 SMS: <code>{instant_sms}</code></blockquote>\n" if instant_sms else "")
                + f"\n<b>✅ OTP RECEIVED INSTANTLY!</b>"
            )
        else:
            final_text = (
                f"✅ <b>YOUR NUMBER DETAILS</b> ✅\n\n"
                f"<blockquote>🌍 COUNTRY: <code>{country_flag} {country_name}</code></blockquote>\n"
                f"<blockquote>📶 RANGE: <code>{range_text}</code></blockquote>\n\n"
                f"<blockquote>📞 NUMBER: <code>+{generated_num}</code></blockquote>\n\n"
                f"<b>📩 SMS STATUS: ⏳ WAITING...</b>"
            )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 SAME RANGE", callback_data="same_range", style="primary")],
            [InlineKeyboardButton("📢 OTP GROUP", url="https://t.me/ZebraXSupport0", style="primary")]
        ])
        await status_msg.edit_text(final_text, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        print(f"Auto Number Error: {e}")
        await status_msg.edit_text(f"❌ Error: {str(e)}")

# ==================== USER PANEL — PROCESS NUMBERS ====================

async def process_numbers(update_or_query, context, range_text, count):
    if isinstance(update_or_query, Update) and update_or_query.callback_query:
        uid = update_or_query.callback_query.from_user.id
        chat_id = update_or_query.callback_query.message.chat_id
    else:
        uid = update_or_query.effective_user.id
        chat_id = update_or_query.effective_chat.id

    if is_user_banned(uid):
        await context.bot.send_message(chat_id=chat_id, text="🚫 YOU ARE BANNED 🚫", reply_markup=main_keyboard(uid))
        return

    status_msg = await context.bot.send_message(chat_id=chat_id, text="🔍 SEARCHING . . .")

    try:
        add_number_taken(uid, count)
        last_range[uid] = range_text

        tasks = [fetch_number_async(range_text) for _ in range(count)]
        results = await asyncio.gather(*tasks)
        valid_results = [r for r in results if r and r.get("number")]

        if not valid_results:
            await status_msg.edit_text("❌ NO NUMBERS FOUND. TRY A VALID RANGE.")
            return

        num_entries = []
        for r in valid_results:
            clean_num = normalize_number(r["number"])
            if clean_num:
                active_numbers[clean_num] = {"uid": uid, "range": range_text, "timestamp": datetime.now()}
                save_number_range_info(uid, clean_num, range_text)
                num_entries.append({
                    "num":     clean_num,
                    "otp_now": r.get("otp_now", False),
                    "otp":     r.get("otp"),
                    "sms":     r.get("sms"),
                })

        if not num_entries:
            await status_msg.edit_text("❌ NO NUMBERS FOUND. TRY A VALID RANGE.")
            return

        country_flag, country_name = get_country_info(num_entries[0]["num"])

        num_lines = []
        for entry in num_entries:
            if entry["otp_now"] and entry["otp"]:
                otp_safe = html.escape(str(entry["otp"]))
                sms_safe = html.escape(str(entry.get("sms") or ""))
                add_otp_received(uid)
                line = (
                    f"<blockquote>📞 NUMBER: <code>+{entry['num']}</code>\n"
                    f"🔑 OTP: <code>{otp_safe}</code>"
                    + (f"\n📩 SMS: <code>{sms_safe}</code>" if sms_safe else "")
                    + "</blockquote>"
                )
            else:
                line = f"<blockquote>📞 NUMBER: <code>+{entry['num']}</code></blockquote>"
            num_lines.append(line)

        num_list_text = "\n".join(num_lines)
        any_instant = any(e["otp_now"] and e["otp"] for e in num_entries)
        sms_status = "✅ OTP RECEIVED INSTANTLY!" if any_instant else "📩 SMS STATUS: ⏳ WAITING..."

        final_text = (
            f"✅ <b>YOUR NUMBER DETAILS</b> ✅\n\n"
            f"<blockquote>🌍 COUNTRY: <code>{country_flag} {country_name}</code></blockquote>\n"
            f"<blockquote>📶 RANGE: <code>{range_text}</code></blockquote>\n\n"
            f"{num_list_text}\n\n"
            f"<b>{sms_status}</b>"
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 SAME RANGE", callback_data="same_range", style="primary")],
            [InlineKeyboardButton("📢 OTP GROUP", url="https://t.me/ZebraXSupport0", style="primary")]
        ])

        await status_msg.edit_text(final_text, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        print(f"Process Number Error: {e}")
        await status_msg.edit_text(f"❌ System Error: {str(e)}")

# ==================== REFER AND EARN SECTION ====================

async def refer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if is_user_banned(uid):
        await update.message.reply_text("🚫 YOU ARE BANNED 🚫", reply_markup=main_keyboard(uid))
        return

    user_data = get_user(uid)
    bot_info = await context.bot.get_me()

    referral_link = f"https://t.me/{bot_info.username}?start={uid}"
    successful_refers = get_referral_count(uid)
    total_reward = float(successful_refers) * REFERRAL_PRICE

    refer_msg = (
        f"🎁 <b>REFER AND EARN SYSTEM</b> 🎁\n\n"
        f"<blockquote>🚀 INVITE FRIENDS &amp; EARN {int(REFERRAL_PRICE)} BDT EACH! 💸</blockquote>\n\n"
        f"<b>🔗 YOUR REFERRAL LINK:</b>\n"
        f"<blockquote><code>{referral_link}</code></blockquote>\n\n"
        f"<b>📊 YOUR STATS:</b>\n"
        f"<blockquote>👥 TOTAL REFERS: {successful_refers}\n"
        f"💰 TOTAL EARNED: {format_balance(total_reward)} BDT</blockquote>\n\n"
        f"✨ <b>SHARE LINK &amp; EARN MONEY!</b> ✨"
    )

    await update.message.reply_text(
        refer_msg,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("👥 YOUR REFERRAL", callback_data=f"my_ref_{uid}", style="primary")
        ]])
    )

# ==================== WITHDRAW FUNCTIONS ====================

async def withdraw_method_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id

    if text == "❌ CANCEL":
        context.user_data["withdraw_mode"] = None
        await update.message.reply_text("❌ WITHDRAW CANCELLED", reply_markup=main_keyboard(uid))
        return

    method_map = {"📱 BKASH": "BKASH", "💵 NAGAD": "NAGAD", "🚀 ROCKET": "ROCKET", "🏦 BINANCE": "BINANCE"}
    if text in method_map:
        balance = get_user(uid)['balance']
        context.user_data["withdraw_method"] = method_map[text]
        context.user_data["withdraw_mode"] = "amount"
        msg = (
            f"<blockquote>💸 SEND YOUR AMOUNT!\n"
            f"💵 TOTAL BALANCE: {format_balance(balance)} BDT</blockquote>\n\n"
            f"<blockquote>📉 MINIMUM WITHDRAW {MIN_WITHDRAW} BDT</blockquote>"
        )
        await update.message.reply_text(msg, parse_mode="HTML", reply_markup=cancel_keyboard())
    else:
        await update.message.reply_text("⚠️ PLEASE SELECT A VALID PAYMENT METHOD!", reply_markup=withdraw_method_keyboard())

async def withdraw_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id

    if text == "❌ CANCEL":
        context.user_data["withdraw_mode"] = None
        await update.message.reply_text("❌ WITHDRAW CANCELLED", reply_markup=main_keyboard(uid))
        return

    try:
        amount = float(text)
    except:
        await update.message.reply_text("⚠️ PLEASE SEND A VALID AMOUNT!", reply_markup=cancel_keyboard())
        return

    balance = get_user(uid)['balance']
    if amount < MIN_WITHDRAW or amount > MAX_WITHDRAW:
        await update.message.reply_text(f"📉 MIN: {MIN_WITHDRAW} BDT | MAX: {MAX_WITHDRAW} BDT", reply_markup=cancel_keyboard())
        return
    if amount > balance:
        await update.message.reply_text("🚫 INSUFFICIENT BALANCE!", reply_markup=cancel_keyboard())
        return

    context.user_data["withdraw_amount"] = amount
    context.user_data["withdraw_mode"] = "number"
    await update.message.reply_text(
        "📞 PLEASE SEND YOUR PAYMENT NUMBER!\n\n<blockquote>🔢 EXAMPLE: 017XXXXXXXX</blockquote>",
        parse_mode="HTML", reply_markup=cancel_keyboard()
    )

async def withdraw_number_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid = update.effective_user.id

    if text == "❌ CANCEL":
        context.user_data["withdraw_mode"] = None
        await update.message.reply_text("❌ WITHDRAW CANCELLED", reply_markup=main_keyboard(uid))
        return

    if not is_valid_bangladesh_number(text):
        await update.message.reply_text("⚠️ PLEASE SEND VALID NUMBER! 017XXXXXXXX", reply_markup=cancel_keyboard())
        return

    method = context.user_data.get("withdraw_method")
    amount = context.user_data.get("withdraw_amount")
    payment_number = text
    payment_id = generate_payment_id()

    context.user_data["temp_withdraw"] = {
        "method": method, "amount": amount,
        "number": payment_number, "payment_id": payment_id
    }

    msg = (
        "✨ <b>YOUR PAYMENT DETAILS!</b> ✨\n\n"
        f"<blockquote>📝 METHOD: {method}\n"
        f"📞 NUMBER: {payment_number}\n\n"
        f"✅ CORRECT → CONFIRM\n❌ WRONG → CANCEL</blockquote>"
    )
    await update.message.reply_text(
        msg, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ CANCEL", callback_data="withdraw_cancel", style="danger"),
            InlineKeyboardButton("✅ CONFIRM", callback_data="withdraw_confirm", style="success")
        ]])
    )

async def process_withdraw_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    temp_data = context.user_data.get("temp_withdraw")
    if not temp_data:
        await query.message.reply_text("⚠️ SESSION EXPIRED.", reply_markup=main_keyboard(uid))
        return

    method = temp_data["method"]
    amount = temp_data["amount"]
    payment_number = temp_data["number"]
    payment_id = temp_data["payment_id"]

    new_balance = await update_db_balance(uid, -amount)
    wr = load_withdraw_requests()
    wr[str(payment_id)] = {
        "user_id": uid, "method": method, "amount": amount,
        "number": payment_number, "payment_id": payment_id,
        "status": "pending", "timestamp": datetime.now().isoformat()
    }
    save_withdraw_requests(wr)

    await query.message.edit_text(
        f"✅ <b>WITHDRAWAL REQUEST SUBMITTED</b> ✅\n\n"
        f"<blockquote>📝 METHOD: <code>{method}</code>\n"
        f"📞 NUMBER: <code>{payment_number}</code>\n"
        f"💰 AMOUNT: <code>{format_balance(amount)} BDT</code>\n"
        f"🆔 ID: <code>{payment_id}</code></blockquote>",
        parse_mode="HTML"
    )
    await context.bot.send_message(uid, "🎉 <b>WITHDRAW REQUEST SUBMITTED!</b>", parse_mode="HTML", reply_markup=main_keyboard(uid))

    admin_msg = (
        f"✅ <b>NEW WITHDRAWAL REQUEST</b>\n\n"
        f"<blockquote>🆔 USER: <code>{uid}</code>\n"
        f"📝 METHOD: <code>{method}</code>\n"
        f"📞 NUMBER: <code>{payment_number}</code>\n"
        f"💰 AMOUNT: <code>{format_balance(amount)} BDT</code>\n"
        f"🆔 ID: <code>{payment_id}</code></blockquote>"
    )
    admin_kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("❌ REJECT", callback_data=f"admin_reject_{payment_id}", style="danger"),
        InlineKeyboardButton("✅ APPROVE", callback_data=f"admin_approve_{payment_id}", style="success")
    ]])
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(admin_id, admin_msg, parse_mode="HTML", reply_markup=admin_kb)
        except Exception as e:
            print(f"Admin notify fail {admin_id}: {e}")

    context.user_data["temp_withdraw"] = None
    context.user_data["withdraw_mode"] = None

async def process_withdraw_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()
    context.user_data["temp_withdraw"] = None
    context.user_data["withdraw_mode"] = None
    await query.message.edit_text("❌ WITHDRAW CANCELLED")
    await context.bot.send_message(uid, "🔹 PLEASE USE THE BUTTONS BELOW:", reply_markup=main_keyboard(uid))

# ==================== ADMIN PANEL - WITHDRAW APPROVAL ====================

async def admin_approve_withdraw(update, context, payment_id):
    query = update.callback_query
    await query.answer()
    wr = load_withdraw_requests()
    if payment_id not in wr:
        await query.message.reply_text("⚠️ REQUEST NOT FOUND!")
        return
    rd = wr[payment_id]
    uid = rd["user_id"]
    method = rd["method"]
    amount = rd["amount"]
    payment_number = rd["number"]
    wr[payment_id]["status"] = "approved"
    save_withdraw_requests(wr)

    try:
        await context.bot.send_message(
            uid,
            f"🎉 <b>WITHDRAWAL APPROVED!</b>\n\n"
            f"<blockquote>📝 METHOD: <code>{method}</code>\n"
            f"📞 NUMBER: <code>{payment_number}</code>\n"
            f"💰 AMOUNT: <code>{format_balance(amount)} BDT</code></blockquote>",
            parse_mode="HTML"
        )
    except:
        pass
    await query.message.edit_text(f"✅ APPROVED | User: {uid} | Amount: {format_balance(amount)} BDT")

async def admin_reject_withdraw(update, context, payment_id):
    query = update.callback_query
    await query.answer()
    wr = load_withdraw_requests()
    if payment_id not in wr:
        await query.message.reply_text("⚠️ REQUEST NOT FOUND!")
        return
    rd = wr[payment_id]
    uid = rd["user_id"]
    amount = rd["amount"]
    wr[payment_id]["status"] = "rejected"
    save_withdraw_requests(wr)

    try:
        await context.bot.send_message(uid, "❌ **WITHDRAWAL REQUEST REJECTED**\n\nContact admin for more info.", parse_mode="Markdown")
    except:
        pass
    await query.message.edit_text(f"❌ REJECTED | User: {uid} | Amount: {format_balance(amount)} BDT")

# ==================== ADMIN PANEL - BAN/UNBAN & BALANCE ====================

async def process_add_balance_user(update, context):
    uid_to_add = update.message.text.strip()
    if not uid_to_add.isdigit():
        await update.message.reply_text("❌ INVALID USER ID!")
        return
    uid_to_add_int = int(uid_to_add)
    if not user_exists(uid_to_add_int):
        await update.message.reply_text("❌ USER NOT FOUND!")
        context.user_data["add_balance_mode"] = False
        return
    context.user_data["pending_add_user"] = uid_to_add_int
    await update.message.reply_text("💵 SEND AMOUNT TO ADD:")

async def process_remove_balance_user(update, context):
    uid_to_remove = update.message.text.strip()
    if not uid_to_remove.isdigit():
        await update.message.reply_text("❌ INVALID USER ID!")
        return
    uid_to_remove_int = int(uid_to_remove)
    if not user_exists(uid_to_remove_int):
        await update.message.reply_text("❌ USER NOT FOUND!")
        context.user_data["remove_balance_mode"] = False
        return
    context.user_data["pending_remove_user"] = uid_to_remove_int
    await update.message.reply_text("💸 SEND AMOUNT TO REMOVE:")

async def process_add_balance_amount(update, context):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ INVALID AMOUNT!")
        return
    uid = context.user_data.get("pending_add_user")
    if not uid:
        context.user_data["add_balance_mode"] = False
        await update.message.reply_text("⚠️ SESSION EXPIRED.")
        return
    old_balance = get_user(uid).get("balance", 0)
    new_balance = await update_db_balance(uid, amount)
    await update.message.reply_text(
        f"✅ **ADD BALANCE SUCCESSFUL**\n🆔 USER: `{uid}`\n"
        f"💰 ADDED: `{format_balance(amount)} BDT`\n"
        f"📈 NEW BALANCE: `{format_balance(new_balance)} BDT`",
        parse_mode="Markdown"
    )
    try:
        await context.bot.send_message(uid, f"🎉 ADMIN ADDED `{format_balance(amount)} BDT` TO YOUR ACCOUNT!\n💵 NEW BALANCE: `{format_balance(new_balance)} BDT`", parse_mode="Markdown")
    except:
        pass
    context.user_data["add_balance_mode"] = False
    context.user_data["pending_add_user"] = None

async def process_remove_balance_amount(update, context):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0: raise ValueError
    except:
        await update.message.reply_text("❌ INVALID AMOUNT!")
        return
    uid = context.user_data.get("pending_remove_user")
    if not uid:
        context.user_data["remove_balance_mode"] = False
        await update.message.reply_text("⚠️ SESSION EXPIRED.")
        return
    old_balance = get_user(uid).get("balance", 0)
    if amount > old_balance:
        await update.message.reply_text(f"❌ INSUFFICIENT BALANCE! Current: {format_balance(old_balance)} BDT")
        context.user_data["remove_balance_mode"] = False
        context.user_data["pending_remove_user"] = None
        return
    new_balance = await update_db_balance(uid, -amount)
    await update.message.reply_text(
        f"✅ **REMOVE BALANCE SUCCESSFUL**\n🆔 USER: `{uid}`\n"
        f"💸 REMOVED: `{format_balance(amount)} BDT`\n"
        f"📉 NEW BALANCE: `{format_balance(new_balance)} BDT`",
        parse_mode="Markdown"
    )
    try:
        await context.bot.send_message(uid, f"⚠️ ADMIN REMOVED `{format_balance(amount)} BDT` FROM YOUR ACCOUNT!\n💵 NEW BALANCE: `{format_balance(new_balance)} BDT`", parse_mode="Markdown")
    except:
        pass
    context.user_data["remove_balance_mode"] = False
    context.user_data["pending_remove_user"] = None

async def process_ban_user(update, context):
    uid_to_ban = update.message.text.strip()
    if not uid_to_ban.isdigit():
        await update.message.reply_text("❌ INVALID USER ID!")
        return
    uid_to_ban_int = int(uid_to_ban)
    if not user_exists(uid_to_ban_int):
        await update.message.reply_text("❌ USER NOT FOUND!")
        context.user_data["admin_ban_mode"] = False
        return
    if is_user_banned(uid_to_ban_int):
        await update.message.reply_text("⚠️ USER IS ALREADY BANNED!")
        context.user_data["admin_ban_mode"] = False
        return
    ban_user(uid_to_ban_int)
    try:
        await context.bot.send_message(uid_to_ban_int, "🚫 **YOU HAVE BEEN BANNED**\n📞 Contact support.", parse_mode="Markdown")
    except:
        pass
    await update.message.reply_text(f"✅ USER `{uid_to_ban}` BANNED!", parse_mode="Markdown")
    context.user_data["admin_ban_mode"] = False

async def process_unban_user(update, context):
    uid_to_unban = update.message.text.strip()
    if not uid_to_unban.isdigit():
        await update.message.reply_text("❌ INVALID USER ID!")
        return
    uid_to_unban_int = int(uid_to_unban)
    if not is_user_banned(uid_to_unban_int):
        await update.message.reply_text("⚠️ THIS USER IS NOT BANNED!")
        context.user_data["admin_unban_mode"] = False
        return
    unban_user(uid_to_unban_int)
    try:
        await context.bot.send_message(uid_to_unban_int, "✅ **YOU HAVE BEEN UNBANNED!** Use /start", parse_mode="Markdown")
    except:
        pass
    await update.message.reply_text(f"✅ USER `{uid_to_unban}` UNBANNED!", parse_mode="Markdown")
    context.user_data["admin_unban_mode"] = False

# ==================== MESSAGE HANDLER SECTION ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    uid = update.effective_user.id
    raw_text = update.message.text.strip() if update.message.text else ""
    
    # হোয়াইট বোল্ড স্টাইলিস্ট ইউনিকোড লেখাকে নরমাল ডিকোড করার স্মার্ট মেথড
    text = normalize_stylized_text(raw_text).strip()

    # 🛡️ SMART CHAT GUARD
    if is_state_cancelling_input(text):
        context.user_data["admin_state"] = None
        context.user_data["temp_target_service"] = None
        context.user_data["temp_target_country"] = None
        context.user_data["temp_target_range"] = None
        context.user_data["add_balance_mode"] = False
        context.user_data["remove_balance_mode"] = False
        context.user_data["pending_add_user"] = None
        context.user_data["pending_remove_user"] = None
        context.user_data["admin_ban_mode"] = False
        context.user_data["admin_unban_mode"] = False
        context.user_data["withdraw_mode"] = None
        context.user_data["broadcast_mode"] = False
        context.user_data["mode"] = None

    admin_state = context.user_data.get("admin_state")
    if admin_state and is_admin(uid):
        # 1. ADD SERVICE (Inline Flow)
        if admin_state == "waiting_for_add_service_name_inline":
            svc_name = text.strip().upper()
            custom_svcs = load_custom_services()
            exists = any(s.get("sid", "").upper() == svc_name for s in custom_svcs)
            if exists:
                await update.message.reply_text(f"❌ **Service '{svc_name}' already exists!**", parse_mode="Markdown")
            else:
                custom_svcs.append({"sid": svc_name, "ranges": []})
                save_custom_services(custom_svcs)
                await update.message.reply_text(f"✅ **Service '{svc_name}' added successfully!**", parse_mode="Markdown")
            
            context.user_data["admin_state"] = None
            kb = build_manage_services_inline_keyboard()
            await update.message.reply_text(
                "⚙️ MANAGE SERVICES\n"
                "───────────────────\n"
                "SELECT A SERVICE:",
                reply_markup=kb
            )
            return

        # 2. RENAME SERVICE (Inline Flow)
        elif admin_state == "waiting_for_rename_service_inline":
            new_name = text.strip().upper()
            old_name = context.user_data.get("temp_target_service")
            
            custom_svcs = load_custom_services()
            for s in custom_svcs:
                if s.get("sid", "").upper() == old_name.upper():
                    s["sid"] = new_name
                    break
            save_custom_services(custom_svcs)
            
            await update.message.reply_text(f"✅ **Service renamed from '{old_name}' to '{new_name}' successfully!**", parse_mode="Markdown")
            context.user_data["admin_state"] = None
            context.user_data["temp_target_service"] = None
            
            kb = build_manage_services_inline_keyboard()
            await update.message.reply_text(
                "⚙️ MANAGE SERVICES\n"
                "───────────────────\n"
                "SELECT A SERVICE:",
                reply_markup=kb
            )
            return

        # 3. ADD RANGE (Inline Flow)
        elif admin_state == "waiting_for_add_range_inline":
            range_val = text.strip().upper()
            svc_name = context.user_data.get("temp_target_service")
            country_name = context.user_data.get("temp_target_country")
            
            custom_svcs = load_custom_services()
            target_svc = next((s for s in custom_svcs if s.get("sid", "").upper() == svc_name.upper()), None)
            
            if not target_svc:
                await update.message.reply_text("❌ Service not found!")
                context.user_data["admin_state"] = None
                return
                
            dup = any(r.get("range", "").upper() == range_val for r in target_svc.get("ranges", []))
            if dup:
                await update.message.reply_text(f"❌ **Range '{range_val}' already exists under '{svc_name}'!**", parse_mode="Markdown")
            else:
                prefix = re.sub(r'[xX]+$', '', range_val).strip()
                prefix_clean = re.sub(r'\D', '', prefix)
                
                if country_name:
                    cname = country_name
                    flag, _ = get_country_info(prefix_clean)
                else:
                    flag, cname = get_country_info(prefix_clean)
                
                target_svc["ranges"].append({
                    "range": range_val,
                    "country": f"{flag} {cname}"
                })
                save_custom_services(custom_svcs)
                await update.message.reply_text(f"✅ **Range '{range_val}' ({flag} {cname}) added to '{svc_name}' successfully!**", parse_mode="Markdown")
                
            context.user_data["admin_state"] = None
            context.user_data["temp_target_service"] = None
            context.user_data["temp_target_country"] = None
            
            kb = build_country_detail_keyboard(svc_name, cname)
            if kb:
                await update.message.reply_text(
                    f"RANGES → {svc_name.upper()} → {cname.upper()}\n"
                    f"───────────────────\n"
                    f"TAP TO DELETE / EDIT:",
                    reply_markup=kb
                )
            return

        # 4. RENAME COUNTRY (Inline Flow)
        elif admin_state == "waiting_for_rename_country_inline":
            new_country_name = text.strip()
            svc_name = context.user_data.get("temp_target_service")
            old_country_name = context.user_data.get("temp_target_country")
            
            custom_svcs = load_custom_services()
            target_svc = next((s for s in custom_svcs if s.get("sid", "").upper() == svc_name.upper()), None)
            
            if target_svc:
                flag = "🌍"
                for r in target_svc.get("ranges", []):
                    country_display = r.get("country", "")
                    match = re.match(r'^([^\w\s]*)\s*(.*)$', country_display)
                    cname = match.group(2).strip() if match else "Unknown"
                    if cname.upper() == old_country_name.upper():
                        flag = match.group(1).strip() if match else "🌍"
                        r["country"] = f"{flag} {new_country_name}"
                
                save_custom_services(custom_svcs)
                await update.message.reply_text(f"✅ **Country renamed from '{old_country_name}' to '{new_country_name}' successfully!**", parse_mode="Markdown")
                
            context.user_data["admin_state"] = None
            context.user_data["temp_target_service"] = None
            context.user_data["temp_target_country"] = None
            
            kb = build_country_detail_keyboard(svc_name, new_country_name)
            if kb:
                await update.message.reply_text(
                    f"RANGES → {svc_name.upper()} → {new_country_name.upper()}\n"
                    f"───────────────────\n"
                    f"TAP TO DELETE / EDIT:",
                    reply_markup=kb
                )
            return

        # 5. EDIT RANGE (Inline Flow)
        elif admin_state == "waiting_for_edit_range_inline":
            new_range = text.strip().upper()
            svc_name = context.user_data.get("temp_target_service")
            country_name = context.user_data.get("temp_target_country")
            old_range = context.user_data.get("temp_target_range")
            
            custom_svcs = load_custom_services()
            target_svc = next((s for s in custom_svcs if s.get("sid", "").upper() == svc_name.upper()), None)
            
            if target_svc:
                for r in target_svc.get("ranges", []):
                    if r.get("range", "").upper() == old_range.upper():
                        r["range"] = new_range
                        prefix = re.sub(r'[xX]+$', '', new_range).strip()
                        prefix_clean = re.sub(r'\D', '', prefix)
                        flag, _ = get_country_info(prefix_clean)
                        r["country"] = f"{flag} {country_name}"
                        break
                
                save_custom_services(custom_svcs)
                await update.message.reply_text(f"✅ **Range edited from '{old_range}' to '{new_range}' successfully!**", parse_mode="Markdown")
                
            context.user_data["admin_state"] = None
            context.user_data["temp_target_service"] = None
            context.user_data["temp_target_country"] = None
            context.user_data["temp_target_range"] = None
            
            kb = build_country_detail_keyboard(svc_name, country_name)
            if kb:
                await update.message.reply_text(
                    f"RANGES → {svc_name.upper()} → {country_name.upper()}\n"
                    f"───────────────────\n"
                    f"TAP TO DELETE / EDIT:",
                    reply_markup=kb
                )
            return

    # Withdraw flow
    if context.user_data.get("withdraw_mode") == "select_method":
        await withdraw_method_selected(update, context)
        return
    if context.user_data.get("withdraw_mode") == "amount":
        await withdraw_amount_received(update, context)
        return
    if context.user_data.get("withdraw_mode") == "number":
        await withdraw_number_received(update, context)
        return

    # Admin Balance & Ban configuration
    if context.user_data.get("add_balance_mode") and is_admin(uid):
        if context.user_data.get("pending_add_user"):
            await process_add_balance_amount(update, context)
        else:
            await process_add_balance_user(update, context)
        return
    if context.user_data.get("remove_balance_mode") and is_admin(uid):
        if context.user_data.get("pending_remove_user"):
            await process_remove_balance_amount(update, context)
        else:
            await process_remove_balance_user(update, context)
        return
    if context.user_data.get("admin_ban_mode") and is_admin(uid):
        await process_ban_user(update, context)
        return
    if context.user_data.get("admin_unban_mode") and is_admin(uid):
        await process_unban_user(update, context)
        return

    # User Status Checking
    if context.user_data.get("mode") == "input_user_id" and is_admin(uid):
        target_uid = text.strip()
        if not target_uid.isdigit():
            await update.message.reply_text("❌ INVALID ID!")
            return
        context.user_data["mode"] = None
        stats = get_user_stats(target_uid)
        msg = (
            f"👤 <b>USER STATUS</b> — <code>{target_uid}</code>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✨ TODAY: 📱 {stats['today_numbers']} | 🔑 {stats['today_otps']}\n"
            f"🔥 7 DAYS: 📱 {stats['last7d_numbers']} | 🔑 {stats['last7d_otps']}\n"
            f"🌐 ALL TIME: 📱 {stats['total_numbers']} | 🔑 {stats['total_otps']}"
        )
        await update.message.reply_text(
            msg, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(make_bold_unicode("📂 CHECK ALL DATA"), callback_data=f"full_logs_{target_uid}", style="primary")],
                [InlineKeyboardButton(make_bold_unicode("🔙 BACK"), callback_data="adm_menu_back_to_admin", style="danger")]
            ])
        )
        return

    # Ban check
    if not is_admin(uid) and is_user_banned(uid):
        await update.message.reply_text("🚫 YOU ARE BANNED 🚫", reply_markup=main_keyboard(uid))
        return

    # Cancel
    if text == "❌ CANCEL":
        context.user_data.clear()
        await update.message.reply_text("❌ CANCELLED", reply_markup=main_keyboard(uid))
        return

    # PROFILE বাটন ডিটেকশন (এখান থেকেই ব্যালেন্স এবং উইথড্র ইনলাইন বাটন হ্যান্ডেল করা হয়েছে)
    if "PROFILE" in text:
        user_data = get_user(uid)
        stats = get_user_stats(uid)
        user = update.effective_user
        full_name = html.escape(user.full_name)
        username = html.escape(user.username or "No username")
        balance = user_data.get('balance', 0)
        
        profile_text = (
            f"👤 <b>ACCOUNT PROFILE</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>Name:</b> <code>{full_name}</code>\n"
            f"🆔 <b>Username:</b> <code>@{username}</code>\n"
            f"🗝 <b>ID:</b> <code>{uid}</code>\n\n"
            f"💰 <b>Current Balance:</b> <code>{format_balance(balance)} BDT</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 <b>ACTIVITY STATS:</b>\n\n"
            f"📅 <b>Today:</b>\n"
            f"├ 📱 Numbers: <code>{stats['today_numbers']}</code>\n"
            f"└ 🔑 Received OTPs: <code>{stats['today_otps']}</code>\n\n"
            f"🔥 <b>Last 7 Days:</b>\n"
            f"├ 📱 Numbers: <code>{stats['last7d_numbers']}</code>\n"
            f"└ 🔑 Received OTPs: <code>{stats['last7d_otps']}</code>\n\n"
            f"🌐 <b>All-Time:</b>\n"
            f"├ 📱 Numbers: <code>{stats['total_numbers']}</code>\n"
            f"└ 🔑 Received OTPs: <code>{stats['total_otps']}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"💸 {make_bold_unicode('WITHDRAW')}", callback_data="withdraw_start")]
        ])
        
        await update.message.reply_text(profile_text, parse_mode="HTML", reply_markup=keyboard)
        return

    if "REFER AND EARN" in text:
        await refer_command(update, context)
        return

    if "GET NUMBER" in text:
        await show_app_selection(update, context)
        return

    if "LEADERBOARD" in text:
        await leaderboard_command(update, context)
        return

    if "SUPPORT" in text:
        support_text = "💬 SUPPORT PANEL 🎧\n\nCLICK THE BUTTONS BELOW TO CONTACT SUPPORT"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 SUPPORT", url=SUPPORT_LINK, style="primary")],
            [InlineKeyboardButton("👨‍💻 DEVELOPER", url="https://t.me/ZebraXSupport0", style="danger")]
        ])
        await update.message.reply_text(support_text, reply_markup=keyboard, parse_mode="Markdown")
        return

    # Admin Panel (Pure Inline Transition)
    if "ADMIN PANEL" in text and is_admin(uid):
        context.user_data["admin_mode"] = "main"
        admin_text = get_admin_panel_text()
        await update.message.reply_text(
            admin_text,
            parse_mode="HTML",
            reply_markup=build_admin_main_inline_keyboard()
        )
        return

    # ==================== BROADCAST ====================
    if context.user_data.get("broadcast_mode") and is_admin(uid):
        context.user_data["broadcast_mode"] = False
        
        user_db = load_data(USER_DATA_FILE)
        all_uids = list(user_db.keys())
        
        if not all_uids:
            await update.message.reply_text("❌ পাঠানোর জন্য কোনো ইউজার পাওয়া যায়নি!")
            return

        success_ids, fail_ids = [], []
        status_msg = await update.message.reply_text(f"🚀 <b>ব্রডকাস্ট শুরু হয়েছে...</b>\n🎯 টার্গেট: {len(all_uids)} জন ইউজার।", parse_mode="HTML")

        def format_broadcast_caption(caption_text):
            if not caption_text:
                return "<blockquote>📢 <b>ADMIN NOTICE :</b></blockquote>"
            formatted = re.sub(r'(\d{3,}[xX]{3,})', r'<code>\1</code>', str(caption_text))
            return f"<blockquote>📢 <b>ADMIN NOTICE :</b></blockquote>\n\n{formatted}"

        for user_id_str in all_uids:
            try:
                target_id = int(user_id_str)
                
                # টেক্সট মেসেজ
                if update.message.text:
                    await context.bot.send_message(
                        chat_id=target_id, 
                        text=format_broadcast_caption(update.message.text), 
                        parse_mode="HTML"
                    )
                # ফটো
                elif update.message.photo:
                    caption = format_broadcast_caption(update.message.caption) if update.message.caption else None
                    await context.bot.send_photo(
                        chat_id=target_id,
                        photo=update.message.photo[-1].file_id,
                        caption=caption,
                        parse_mode="HTML" if caption else None
                    )
                # ভিডিও
                elif update.message.video:
                    caption = format_broadcast_caption(update.message.caption) if update.message.caption else None
                    await context.bot.send_video(
                        chat_id=target_id,
                        video=update.message.video.file_id,
                        caption=caption,
                        parse_mode="HTML" if caption else None
                    )
                # ডকুমেন্ট
                elif update.message.document:
                    caption = format_broadcast_caption(update.message.caption) if update.message.caption else None
                    await context.bot.send_document(
                        chat_id=target_id,
                        document=update.message.document.file_id,
                        caption=caption,
                        parse_mode="HTML" if caption else None
                    )
                # অডিও
                elif update.message.audio:
                    caption = format_broadcast_caption(update.message.caption) if update.message.caption else None
                    await context.bot.send_audio(
                        chat_id=target_id,
                        audio=update.message.audio.file_id,
                        caption=caption,
                        parse_mode="HTML" if caption else None
                    )
                # ভয়েস
                elif update.message.voice:
                    caption = format_broadcast_caption(update.message.caption) if update.message.caption else None
                    await context.bot.send_voice(
                        chat_id=target_id,
                        voice=update.message.voice.file_id,
                        caption=caption,
                        parse_mode="HTML" if caption else None
                    )
                # অ্যানিমেশন
                elif update.message.animation:
                    caption = format_broadcast_caption(update.message.caption) if update.message.caption else None
                    await context.bot.send_animation(
                        chat_id=target_id,
                        animation=update.message.animation.file_id,
                        caption=caption,
                        parse_mode="HTML" if caption else None
                    )
                # স্টিকার
                elif update.message.sticker:
                    await context.bot.send_sticker(
                        chat_id=target_id,
                        sticker=update.message.sticker.file_id
                    )
                else:
                    try:
                        await context.bot.copy_message(
                            chat_id=target_id,
                            from_chat_id=update.message.chat_id,
                            message_id=update.message.message_id
                        )
                    except:
                        await context.bot.send_message(
                            chat_id=target_id,
                            text="📢 <b>ADMIN NOTICE :</b>\n\nআপনার জন্য একটি নতুন বার্তা আছে, কিন্তু এটি প্রদর্শন করা সম্ভব হয়নি।",
                            parse_mode="HTML"
                        )
                success_ids.append(user_id_str)
            except Exception as e:
                print(f"Broadcast fail to {user_id_str}: {e}")
                fail_ids.append(user_id_str)
            
            await asyncio.sleep(0.05)

        report_text = (
            f"✅ <b>ADMIN NOTICE COMPLETE !</b>\n\n"
            f"📊 <b>BROADCAST REPORT:</b>\n\n"
            f"<blockquote>✅ SUCCESSFULLY SENT: {len(success_ids)} USERS !</blockquote>\n"
            f"<blockquote>❌ FAILED TO SEND: {len(fail_ids)} USERS !</blockquote>"
        )
        
        await status_msg.delete()
        await context.bot.send_message(chat_id=uid, text=report_text, parse_mode="HTML", reply_markup=main_keyboard(uid))

        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if success_ids:
            s_file = io.BytesIO(("\n".join(success_ids)).encode()); s_file.name = f"SUCCESS_{random_suffix}.txt"
            await context.bot.send_document(chat_id=uid, document=s_file, caption="✅ Success User List")
        if fail_ids:
            f_file = io.BytesIO(("\n".join(fail_ids)).encode()); f_file.name = f"FAILED_{random_suffix}.txt"
            await context.bot.send_document(chat_id=uid, document=f_file, caption="❌ Failed User List")
        
        return

    await update.message.reply_text("🔹 PLEASE USE THE BUTTONS BELOW:", reply_markup=main_keyboard(uid))

# ==================== COMMAND HANDLERS SECTION ====================

async def get1number_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_user_banned(uid):
        await update.message.reply_text("🚫 YOU ARE BANNED 🚫", reply_markup=main_keyboard(uid))
        return
    await show_app_selection(update, context)

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_user_banned(uid):
        await update.message.reply_text("🚫 YOU ARE BANNED 🚫", reply_markup=main_keyboard(uid))
        return
    balance = get_user(uid)['balance']
    await update.message.reply_text(f"💰 BALANCE: `{format_balance(balance)} BDT`", parse_mode="Markdown", reply_markup=main_keyboard(uid))

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_user_banned(uid):
        await update.message.reply_text("🚫 YOU ARE BANNED 🚫", reply_markup=main_keyboard(uid))
        return
    user_data = get_user(uid)
    stats = get_user_stats(uid)
    user = update.effective_user
    profile_text = (
        f"👤 **YOUR PROFILE**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏷️ NAME: `{user.full_name}`\n"
        f"🆔 USERNAME: @{user.username or 'No username'}\n"
        f"🗝️ ID: `{uid}`\n\n"
        f"💵 BALANCE: {format_balance(user_data.get('balance', 0))} BDT\n\n"
        f"✨ TODAY: 📱 {stats['today_numbers']} | 🔑 {stats['today_otps']}\n"
        f"🔥 7 DAYS: 📱 {stats['last7d_numbers']} | 🔑 {stats['last7d_otps']}\n"
        f"🌐 ALL TIME: 📱 {stats['total_numbers']} | 🔑 {stats['total_otps']}"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💸 {make_bold_unicode('WITHDRAW')}", callback_data="withdraw_start")]
    ])
    await update.message.reply_text(profile_text, parse_mode="Markdown", reply_markup=keyboard)

async def refer_command_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_user_banned(uid):
        await update.message.reply_text("🚫 YOU ARE BANNED 🚫", reply_markup=main_keyboard(uid))
        return
    await refer_command(update, context)

async def leaderboard_command_slash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_user_banned(uid):
        await update.message.reply_text("🚫 YOU ARE BANNED 🚫", reply_markup=main_keyboard(uid))
        return
    await leaderboard_command(update, context)

# ==================== START & CALLBACK SECTION ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uid_str = str(uid)

    existing_data = load_data(USER_DATA_FILE)
    is_new_user = uid_str not in existing_data
    if is_new_user:
        get_user(uid)

    args = context.args
    if args:
        param = args[0]
        if is_range_request(param):
            await request_queue.put({'type': 'auto_number', 'update': update, 'context': context, 'range_text': param})
            return
        elif is_referral_request(param) and is_new_user:
            try:
                referrer_id = int(param)
                if referrer_id != uid and str(referrer_id) in existing_data:
                    current_count = get_referral_count(referrer_id)
                    new_count = current_count + 1
                    update_referral_count(referrer_id, new_count)
                    await update_db_balance(referrer_id, REFERRAL_PRICE)
                    log_global_activity(referrer_id, "REFERRAL_JOINED", {"referred_user": uid})
                    try:
                        await context.bot.send_message(
                            referrer_id,
                            f"🎉 <b>NEW REFERRAL!</b>\n\n<blockquote>🗝️ ID: <code>{uid}</code>\n💰 REWARD: {format_balance(REFERRAL_PRICE)} BDT\n👥 TOTAL REFERS: {new_count}</blockquote>",
                            parse_mode="HTML"
                        )
                    except:
                        pass
            except Exception as e:
                print(f"Referral error: {e}")

    context.user_data.clear()
    await update.message.reply_text(WELCOME_MESSAGE, parse_mode="Markdown")
    await update.message.reply_text("🔹 PLEASE USE THE BUTTONS BELOW:", reply_markup=main_keyboard(uid))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = query.from_user.id
    data = query.data
    await query.answer()

    if not is_admin(uid) and is_user_banned(uid):
        await query.edit_message_text("🚫 YOU ARE BANNED 🚫")
        return

    # 🛡️ SMART INLINE GUARD
    context.user_data["admin_state"] = None
    context.user_data["add_balance_mode"] = False
    context.user_data["remove_balance_mode"] = False
    context.user_data["admin_ban_mode"] = False
    context.user_data["admin_unban_mode"] = False
    context.user_data["withdraw_mode"] = None
    context.user_data["broadcast_mode"] = False
    context.user_data["mode"] = None

    # ==================== COHERENT INLINE ADMIN ROUTING ====================

    # ১. ব্যাক টু অ্যাডমিন মেইন মেনু
    if data == "adm_menu_back_to_admin":
        admin_text = get_admin_panel_text()
        await query.message.edit_text(
            admin_text,
            parse_mode="HTML",
            reply_markup=build_admin_main_inline_keyboard()
        )
        return

    # ২. ব্যাক টু নরমাল ইউজার কীবোর্ড
    if data == "adm_menu_back_to_main":
        await query.message.delete()
        await context.bot.send_message(
            chat_id=uid,
            text="🔙 Returned to main user panel.",
            reply_markup=main_keyboard(uid)
        )
        return

    # ৩. ইনলাইন ইউজার ম্যানেজমেন্ট সাব-মেনু
    if data == "adm_menu_user_mgnt":
        await query.message.edit_text(
            "👥 <b>USER MANAGEMENT PANEL</b>\n───────────────────\nSelect an action from below:",
            parse_mode="HTML",
            reply_markup=build_user_management_inline_keyboard()
        )
        return

    # ৪. ইনলাইন সিস্টেম কনফিগারেশন সাব-মেনু
    if data == "adm_menu_sys_config":
        await query.message.edit_text(
            "⚙️ <b>SYSTEM CONFIGURATION PANEL</b>\n───────────────────\nSelect an action from below:",
            parse_mode="HTML",
            reply_markup=build_system_config_inline_keyboard()
        )
        return

    # ৫. ইউজার ম্যানেজমেন্ট অপশনস
    if data == "adm_usermgnt_broadcast":
        context.user_data["broadcast_mode"] = True
        await query.message.edit_text(
            "📢 <b>ADMIN BROADCAST SYSTEM</b>\n───────────────────\n"
            "💬 Please send the message (Text/Photo/Video/Document etc.) - which will be sent to all users with a professional notification header.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("❌ CANCEL"), callback_data="adm_menu_user_mgnt", style="danger")]])
        )
        return

    if data == "adm_usermgnt_get_ids":
        users = get_all_users()
        if users:
            content = "\n".join(f"{i}. {u}" for i, u in enumerate(users, 1))
            f = io.BytesIO(content.encode()); f.name = f"ALL_USERS_{len(users)}.txt"
            await context.bot.send_document(chat_id=uid, document=f, caption=f"👥 Total Users: {len(users)}")
        else:
            await query.message.reply_text("No users found.")
        return

    if data == "adm_usermgnt_all_balance":
        user_db = load_data(USER_DATA_FILE)
        if user_db:
            total_bal = sum(v.get("balance", 0) for v in user_db.values())
            lines = [f"{i}. {uid_}: {v.get('balance', 0):.2f} BDT" for i, (uid_, v) in enumerate(user_db.items(), 1)]
            content = f"💰 TOTAL BALANCE: {total_bal:.2f} BDT\n\n" + "\n".join(lines)
            f = io.BytesIO(content.encode()); f.name = f"BALANCES_{total_bal:.0f}.txt"
            await context.bot.send_document(chat_id=uid, document=f, caption=f"💵 Total Balance: {total_bal:.2f} BDT")
        else:
            await query.message.reply_text("No data.")
        return

    # ৬. সিস্টেম কনফিগারেশন অপশনস
    if data == "adm_sys_stats":
        t_n, t_o, s_n, s_o, tot_n, tot_o = get_global_system_stats()
        msg = (
            f"📊 <b>SYSTEM STATUS</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✨ <b>TODAY</b>\n📱 NUMBERS: {t_n}\n🔑 OTPS: {t_o}\n\n"
            f"🔥 <b>LAST 7 DAYS</b>\n📱 NUMBERS: {s_n}\n🔑 OTPS: {s_o}\n\n"
            f"🌐 <b>ALL TIME</b>\n📱 NUMBERS: {tot_n}\n🔑 OTPS: {tot_o}"
        )
        await query.message.edit_text(msg, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("🔙 BACK"), callback_data="adm_menu_sys_config", style="danger")]]))
        return

    if data == "adm_sys_user_check":
        context.user_data["mode"] = "input_user_id"
        await query.message.edit_text(
            "🔍 <b>USER STATUS CHECK</b>\n───────────────────\nPlease send the target Telegram ID:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("❌ CANCEL"), callback_data="adm_menu_sys_config", style="danger")]])
        )
        return

    if data == "adm_sys_ban":
        context.user_data["admin_ban_mode"] = True
        await query.message.edit_text(
            "🚫 <b>BAN USER</b>\n───────────────────\nPlease send the Telegram ID to BAN:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("❌ CANCEL"), callback_data="adm_menu_sys_config", style="danger")]])
        )
        return

    if data == "adm_sys_unban":
        context.user_data["admin_unban_mode"] = True
        await query.message.edit_text(
            "🔓 <b>UNBAN USER</b>\n───────────────────\nPlease send the Telegram ID to UNBAN:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("❌ CANCEL"), callback_data="adm_menu_sys_config", style="danger")]])
        )
        return

    if data == "adm_sys_banned_list":
        banned_list = load_banned_users()
        if not banned_list:
            await query.message.edit_text("📜 NO BANNED USERS.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("🔙 BACK"), callback_data="adm_menu_sys_config", style="danger")]]))
            return
        text = "📜 <b>BANNED USER LIST</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for i, b_id in enumerate(banned_list, 1):
            text += f"{i}. <code>{b_id}</code>\n"
        text += f"\n📊 Total: {len(banned_list)}"
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("🔙 BACK"), callback_data="adm_menu_sys_config", style="danger")]]))
        return

    if data == "adm_sys_add_bal":
        context.user_data["add_balance_mode"] = True
        await query.message.edit_text(
            "💰 <b>ADD BALANCE</b>\n───────────────────\nPlease send the Telegram ID to add balance:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("❌ CANCEL"), callback_data="adm_menu_sys_config", style="danger")]])
        )
        return

    if data == "adm_sys_rem_bal":
        context.user_data["remove_balance_mode"] = True
        await query.message.edit_text(
            "💸 <b>REMOVE BALANCE</b>\n───────────────────\nPlease send the Telegram ID to remove balance:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("❌ CANCEL"), callback_data="adm_menu_sys_config", style="danger")]])
        )
        return

    # ৭. সার্ভিস ব্যাক-টু-লিস্ট
    if data == "manage_svc_back_to_list":
        kb = build_manage_services_inline_keyboard()
        await query.message.edit_text(
            "⚙️ MANAGE SERVICES\n"
            "───────────────────\n"
            "SELECT A SERVICE:",
            reply_markup=kb
        )
        return

    # ৮. সার্ভিস অ্যাড করার ইনপুট ট্রিগার
    if data == "manage_svc_add":
        context.user_data["admin_state"] = "waiting_for_add_service_name_inline"
        await query.message.edit_text(
            "📝 <b>Send the new service name (e.g. FACEBOOK):</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("❌ CANCEL"), callback_data="manage_svc_back_to_list", style="danger")]])
        )
        return

    # ৯. সার্ভিস রেনেম ইনিশিয়েট
    if data.startswith("manage_svc_rename_init_"):
        svc_name = data.replace("manage_svc_rename_init_", "")
        context.user_data["admin_state"] = "waiting_for_rename_service_inline"
        context.user_data["temp_target_service"] = svc_name
        await query.message.edit_text(
            f"✏️ <b>RENAME SERVICE: {svc_name.upper()}</b>\n───────────────────\n"
            f"Please send the new name for this service:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("❌ CANCEL"), callback_data=f"manage_svc_view_{svc_name}", style="danger")]])
        )
        return

    # ১০. সার্ভিস ডিলিট ইনিশিয়েট
    if data.startswith("manage_svc_delete_init_"):
        svc_name = data.replace("manage_svc_delete_init_", "")
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(make_bold_unicode("✅ CONFIRM"), callback_data=f"manage_svc_delete_do_{svc_name}", style="danger"),
                InlineKeyboardButton(make_bold_unicode("❌ CANCEL"), callback_data=f"manage_svc_view_{svc_name}", style="primary")
            ]
        ])
        await query.message.edit_text(
            f"🗑️ <b>Are you sure you want to delete service {svc_name.upper()} and all of its countries/ranges?</b>",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    # ১১. চূড়ান্ত সার্ভিস ডিলিট প্রসেস
    if data.startswith("manage_svc_delete_do_"):
        svc_name = data.replace("manage_svc_delete_do_", "")
        custom_svcs = load_custom_services()
        custom_svcs = [s for s in custom_svcs if s.get("sid", "").upper() != svc_name.upper()]
        save_custom_services(custom_svcs)
        await query.answer(f"Deleted {svc_name}", show_alert=True)
        
        kb = build_manage_services_inline_keyboard()
        await query.message.edit_text(
            "⚙️ MANAGE SERVICES\n"
            "───────────────────\n"
            "SELECT A SERVICE:",
            reply_markup=kb
        )
        return

    # ১২. সার্ভিস ডিটেইলস ভিউ
    if data.startswith("manage_svc_view_"):
        svc_name = data.replace("manage_svc_view_", "")
        kb = build_service_detail_keyboard(svc_name)
        if not kb:
            await query.answer("Service not found!", show_alert=True)
            return
            
        await query.message.edit_text(
            f"📁 SERVICE: <b>{svc_name.upper()}</b>\n"
            f"───────────────────\n"
            f"SELECT A COUNTRY TO MANAGE RANGES:",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    # ১৩. দেশের আন্ডারে থাকা রেঞ্জ সমূহের ভিউ
    if data.startswith("manage_svc_country_view_"):
        parts = data.replace("manage_svc_country_view_", "").split("_", 1)
        svc_name = parts[0]
        country_name = parts[1]
        
        custom_svcs = load_custom_services()
        target_svc = next((s for s in custom_svcs if s.get("sid", "").upper() == svc_name.upper()), None)
        if not target_svc:
            await query.answer("Service not found!", show_alert=True)
            return
            
        grouped = get_grouped_countries_for_service(target_svc)
        info = grouped.get(country_name, {"flag": "🌍", "ranges": []})
        flag = info["flag"]
        
        kb = build_country_detail_keyboard(svc_name, country_name)
        await query.message.edit_text(
            f"{flag} RANGES → {svc_name.upper()} → {country_name.upper()}\n"
            f"───────────────────\n"
            f"TAP TO DELETE / EDIT:",
            reply_markup=kb
        )
        return

    # ১৪. রেঞ্জ অ্যাড করার প্রম্পট
    if data.startswith("manage_svc_add_range_"):
        parts = data.replace("manage_svc_add_range_", "").split("_", 1)
        svc_name = parts[0]
        country_name = parts[1] if len(parts) > 1 else None
        
        context.user_data["admin_state"] = "waiting_for_add_range_inline"
        context.user_data["temp_target_service"] = svc_name
        context.user_data["temp_target_country"] = country_name
        
        cancel_cb = f"manage_svc_country_view_{svc_name}_{country_name}" if country_name else f"manage_svc_view_{svc_name}"
        
        await query.message.edit_text(
            f"📶 <b>SERVICE: {svc_name.upper()}</b>\n"
            f"───────────────────\n"
            f"Please send the new range value (e.g. <code>23672XXX</code>):\n"
            f"<i>(Country and flag will be auto-detected instantly)</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("❌ CANCEL"), callback_data=cancel_cb, style="danger")]])
        )
        return

    # ১৫. রেঞ্জ ডিলিট অ্যাকশন
    if data.startswith("manage_svc_delete_range_"):
        parts = data.replace("manage_svc_delete_range_", "").rsplit("_", 2)
        if len(parts) < 3:
            await query.answer("Invalid request!", show_alert=True)
            return
        svc_name, country_name, range_val = parts[0], parts[1], parts[2]
        
        custom_svcs = load_custom_services()
        target_svc = next((s for s in custom_svcs if s.get("sid", "").upper() == svc_name.upper()), None)
        if target_svc:
            target_svc["ranges"] = [r for r in target_svc.get("ranges", []) if r.get("range", "").upper() != range_val.upper()]
            save_custom_services(custom_svcs)
            await query.answer(f"Deleted range {range_val}", show_alert=True)
            
            grouped = get_grouped_countries_for_service(target_svc)
            if country_name in grouped:
                kb = build_country_detail_keyboard(svc_name, country_name)
                flag = grouped[country_name]["flag"]
                await query.message.edit_text(
                    f"{flag} RANGES → {svc_name.upper()} → {country_name.upper()}\n"
                    f"───────────────────\n"
                    f"TAP TO DELETE / EDIT:",
                    reply_markup=kb
                )
            else:
                kb = build_service_detail_keyboard(svc_name)
                await query.message.edit_text(
                    f"📁 SERVICE: <b>{svc_name.upper()}</b>\n"
                    f"───────────────────\n"
                    f"SELECT A COUNTRY TO MANAGE RANGES:",
                    parse_mode="HTML",
                    reply_markup=kb
                )
        return

    # ১৬. সম্পূর্ণ দেশ ডিলিটের কনফার্মেশন স্ক্রিন
    if data.startswith("manage_svc_delete_country_confirm_"):
        parts = data.replace("manage_svc_delete_country_confirm_", "").split("_", 1)
        svc_name = parts[0]
        country_name = parts[1]
        
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(make_bold_unicode("✅ CONFIRM"), callback_data=f"manage_svc_delete_country_do_{svc_name}_{country_name}", style="danger"),
                InlineKeyboardButton(make_bold_unicode("❌ CANCEL"), callback_data=f"manage_svc_country_view_{svc_name}_{country_name}", style="primary")
            ]
        ])
        await query.message.edit_text(
            f"🗑️ <b>Are you sure you want to delete {country_name.upper()} and all of its ranges from {svc_name.upper()}?</b>",
            parse_mode="HTML",
            reply_markup=kb
        )
        return

    # XVII. চূড়ান্ত দেশ ডিলিট প্রসেস
    if data.startswith("manage_svc_delete_country_do_"):
        parts = data.replace("manage_svc_delete_country_do_", "").split("_", 1)
        svc_name = parts[0]
        country_name = parts[1]
        
        custom_svcs = load_custom_services()
        target_svc = next((s for s in custom_svcs if s.get("sid", "").upper() == svc_name.upper()), None)
        if target_svc:
            new_ranges = []
            for r in target_svc.get("ranges", []):
                country_display = r.get("country", "")
                match = re.match(r'^([^\w\s]*)\s*(.*)$', country_display)
                cname = match.group(2).strip() if match else "Unknown"
                if cname.upper() != country_name.upper():
                    new_ranges.append(r)
            target_svc["ranges"] = new_ranges
            save_custom_services(custom_svcs)
            
            await query.answer(f"Deleted {country_name}", show_alert=True)
            kb = build_service_detail_keyboard(svc_name)
            await query.message.edit_text(
                f"📁 SERVICE: <b>{svc_name.upper()}</b>\n"
                f"───────────────────\n"
                f"SELECT A COUNTRY TO MANAGE RANGES:",
                parse_mode="HTML",
                reply_markup=kb
            )
        return

    # ১৮. কান্ট্রি রেনেম ইনিশিয়েট
    if data.startswith("manage_svc_rename_country_init_"):
        parts = data.replace("manage_svc_rename_country_init_", "").split("_", 1)
        svc_name = parts[0]
        country_name = parts[1]
        
        context.user_data["admin_state"] = "waiting_for_rename_country_inline"
        context.user_data["temp_target_service"] = svc_name
        context.user_data["temp_target_country"] = country_name
        
        await query.message.edit_text(
            f"✏️ <b>RENAME COUNTRY: {country_name.upper()}</b>\n"
            f"───────────────────\n"
            f"Please send the new name for this country:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("❌ CANCEL"), callback_data=f"manage_svc_country_view_{svc_name}_{country_name}", style="danger")]])
        )
        return

    # ১৯. রেঞ্জ এডিট ইনিশিয়েট
    if data.startswith("manage_svc_edit_range_init_"):
        parts = data.replace("manage_svc_edit_range_init_", "").rsplit("_", 2)
        svc_name, country_name, range_val = parts[0], parts[1], parts[2]
        
        context.user_data["admin_state"] = "waiting_for_edit_range_inline"
        context.user_data["temp_target_service"] = svc_name
        context.user_data["temp_target_country"] = country_name
        context.user_data["temp_target_range"] = range_val
        
        await query.message.edit_text(
            f"✏️ <b>EDIT RANGE: {range_val}</b>\n"
            f"───────────────────\n"
            f"Please send the new range value (e.g. <code>23672XXX</code>):",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(make_bold_unicode("❌ CANCEL"), callback_data=f"manage_svc_country_view_{svc_name}_{country_name}", style="danger")]])
        )
        return

    # ==================== USER COHERENT BOT CALLBACKS ====================

    # SERVICE SELECT CALLBACK
    if data.startswith("svc_"):
        idx = int(data.replace("svc_", ""))
        services = context.user_data.get("la_services", [])
        if not services:
            services = load_custom_services()
            context.user_data["la_services"] = services
        if idx >= len(services):
            await query.answer("Service not found. Please try again.", show_alert=True)
            return

        svc = services[idx]
        sid = svc.get("sid", "Service")
        ranges = svc.get("ranges", [])

        if not ranges:
            await query.answer("No ranges available for this service.", show_alert=True)
            return

        context.user_data["la_svc_idx"] = idx
        context.user_data["la_sid"] = sid
        context.user_data["la_ranges"] = ranges

        keyboard = _build_countries_keyboard(ranges, idx)
        await query.message.edit_text(
            f"📞 <b>GET NUMBER</b>\n\n"
            f"<blockquote>📱 Service: <b>{html.escape(sid)}</b></blockquote>\n"
            f"<blockquote>🌍 আপনার পছন্দের <b>Country</b> সিলেক্ট করুন:</blockquote>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return

    # RANGE SELECT CALLBACK
    if data.startswith("rng_"):
        idx = int(data.replace("rng_", ""))
        ranges = context.user_data.get("la_ranges", [])
        if idx >= len(ranges):
            await query.answer("Range not found. Please try again.", show_alert=True)
            return

        range_item = ranges[idx]
        target_country = range_item.get("country", "")
        if not target_country:
            r_text = range_item.get("range", "")
            prefix = re.sub(r'[xX]+$', '', str(r_text)).strip()
            prefix_clean = re.sub(r'\D', '', prefix)
            flag, cname = get_country_info(prefix_clean)
            target_country = f"{flag} {cname}"

        all_country_ranges = []
        target_clean = clean_country_display(target_country)
        for r_item in ranges:
            c_disp = r_item.get("country", "")
            if not c_disp:
                pref = re.sub(r'[xX]+$', '', str(r_item.get("range", ""))).strip()
                pref_cl = re.sub(r'\D', '', pref)
                flg, cn = get_country_info(pref_cl)
                c_disp = f"{flg} {cn}"
            if clean_country_display(c_disp) == target_clean:
                all_country_ranges.append(r_item.get("range", ""))

        sid = context.user_data.get("la_sid", "")

        asyncio.create_task(fast_allocate_number_multi(query, context, all_country_ranges, sid))
        return

    # BACK TO SERVICES
    if data == "back_services":
        services = load_custom_services()
        if not services:
            await query.message.edit_text("❌ Services লোড করা যায়নি।")
            return
        context.user_data["la_services"] = services
        keyboard = _build_services_keyboard(services)
        await query.message.edit_text(
            "📞 <b>GET NUMBER</b>\n\n"
            "<blockquote>📱 নিচ থেকে একটি <b>Service</b> সিলেক্ট করুন:</blockquote>",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return

    # SAME RANGE
    if data == "same_range":
        r_text = last_range.get(uid)
        if r_text:
            try:
                await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📢 OTP GROUP", url="https://t.me/ZebraXSupport0", style="primary")
                ]]))
            except:
                pass
            await process_numbers(update, context, r_text, 1)
        return

    # WITHDRAW CALLBACKS
    if data == "withdraw_start":
        balance = get_user(uid)['balance']
        if balance < MIN_WITHDRAW:
            await query.message.reply_text(
                f"<blockquote>💵 BALANCE: {format_balance(balance)} BDT\n📉 MIN WITHDRAW: {MIN_WITHDRAW} BDT</blockquote>",
                parse_mode="HTML"
            )
            return
        context.user_data["withdraw_mode"] = "select_method"
        await query.message.reply_text("💳 SELECT YOUR PAYMENT METHOD!", reply_markup=withdraw_method_keyboard())
        return

    if data == "withdraw_confirm":
        await process_withdraw_confirm(update, context)
        return

    if data == "withdraw_cancel":
        await process_withdraw_cancel(update, context)
        return

    if data.startswith("admin_approve_"):
        await admin_approve_withdraw(update, context, data.replace("admin_approve_", ""))
        return

    if data.startswith("admin_reject_"):
        await admin_reject_withdraw(update, context, data.replace("admin_reject_", ""))
        return

    # REPORTS / LOGS CALLBACKS
    if data.startswith("my_ref_"):
        target_uid = data.replace("my_ref_", "")
        all_logs = load_data(ACTIVITY_LOGS_FILE)
        my_referrals = [log for log in all_logs if str(log.get('uid')) == str(target_uid) and log.get('action') == "REFERRAL_JOINED"]
        content = f"👥 REFERRAL REPORT — {target_uid}\n━━━━━━━━━━━━\nTOTAL: {len(my_referrals)}\n\n"
        for i, log in enumerate(my_referrals, 1):
            try:
                dt_obj = datetime.fromisoformat(log['timestamp'])
                ref_id = log.get('details', {}).get('referred_user', 'N/A')
                content += f"{i}. ID: {ref_id} | {dt_obj.strftime('%d/%m/%Y %I:%M %p')}\n"
            except:
                continue
        f = io.BytesIO(content.encode())
        f.name = f"REF_{target_uid}.txt"
        await context.bot.send_document(chat_id=uid, document=f, caption="✅ **REFERRAL DATA**", parse_mode="Markdown")
        return

    if data.startswith("full_logs_"):
        target_uid = data.replace("full_logs_", "")
        stats = get_user_stats(target_uid)
        all_logs = load_data(ACTIVITY_LOGS_FILE)
        user_db = load_data(USER_DATA_FILE)
        user_info = user_db.get(str(target_uid), {})
        user_otps = [log for log in all_logs if str(log.get('uid')) == str(target_uid) and log.get('action') == "OTP_RECEIVED"]
        content = (
            f"📊 USER DATA REPORT — {target_uid}\n"
            f"💰 BALANCE: {user_info.get('balance', 0):.2f} BDT\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"TODAY NUMBERS: {stats['today_numbers']}\n"
            f"TODAY OTPS: {stats['today_otps']}\n"
            f"7D NUMBERS: {stats['last7d_numbers']}\n"
            f"7D OTPS: {stats['last7d_otps']}\n"
            f"TOTAL NUMBERS: {stats['total_numbers']}\n"
            f"TOTAL OTPS: {stats['total_otps']}\n"
            f"━━━━━━━━━━━━━━━━━━\n\nOTP LOGS:\n"
        )
        for i, log in enumerate(user_otps, 1):
            try:
                dt_obj = datetime.fromisoformat(log['timestamp'])
                d = log.get('details', {})
                content += f"{i}. {dt_obj.strftime('%d/%m/%Y %I:%M %p')}\n   📞 {d.get('number', 'N/A')}\n   🔑 {d.get('otp', 'N/A')}\n\n"
            except:
                continue
        f = io.BytesIO(content.encode())
        f.name = f"USER_{target_uid}.txt"
        await context.bot.send_document(
            chat_id=uid, document=f,
            caption=f"✅ <b>DATA FOR USER: <code>{target_uid}</code></b>",
            parse_mode="HTML"
        )
        return

# ==================== MAIN & POST INIT SECTION ====================

async def post_init(application):
    for _ in range(20):
        asyncio.create_task(worker())
    asyncio.create_task(monitor_loop(application))

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("get1number", get1number_command))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("refer", refer_command_slash))
    app.add_handler(CommandHandler("leaderboard", leaderboard_command_slash))

    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🚀 BOT RUNNING...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
