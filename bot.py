import os
import logging
import requests
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
import uuid 

# --- Configuration ---
TELEGRAM_BOT_TOKEN = "8269911853:AAF4uOGA3wCj9rb9-Uh96jpjS3O_v6yZNxY"  # Get from @BotFather
API_BASE_URL = "https://bot-api-1.inbo.ir/api/v2"
EXTERNAL_API_KEY = "6065152197:nJ1Xb5nBn0C2hCZGSSnz6QsS6m3910xO5PjEilQl"

# Admin user ID (Your Telegram user ID - get it from @userinfobot)
ADMIN_USER_ID = 6065152197  # Replace with your Telegram user ID
ADMIN_CHAT_ID = 6065152197 # The ID where payment requests will be sent (usually the same as ADMIN_USER_ID)

# Support contact
SUPPORT_USERNAME = "@sessionerowner"  # Your support Telegram username

# Helecta Payment Gateway (Keeping placeholders but logic is changed to manual)
HELECTA_API_KEY = "YOUR_HELECTA_API_KEY"  # Your Helecta API key
HELECTA_MERCHANT_KEY = "YOUR_HELECTA_MERCHANT_KEY"  # Your Helecta Merchant key
HELECTA_API_URL = "https://api.helecta.com/v1"  # Helecta API endpoint

# Allowed countries (only these will be shown)
ALLOWED_COUNTRIES = ['CA', 'US', 'SL', 'VN', 'ET']  # Canada, United States, Sierra Leone, Vietnam, Ethiopia

# Country flags
COUNTRY_FLAGS = {
    'CA': '🇨🇦',
    'US': '🇺🇸',
    'SL': '🇸🇱',
    'VN': '🇻🇳',
    'ET': '🇪🇹',
    'BD': '🇧🇩',
    'IN': '🇮🇳',
    'PK': '🇵🇰',
    'GB': '🇬🇧',
    'DE': '🇩🇪',
    'FR': '🇫🇷',
    'IT': '🇮🇹',
    'ES': '🇪🇸',
    'RU': '🇷🇺',
    'CN': '🇨🇳',
    'JP': '🇯🇵',
    'KR': '🇰🇷',
    'AU': '🇦🇺',
    'BR': '🇧🇷',
    'MX': '🇲🇽',
}

def get_country_flag(country_code):
    """Get flag emoji for country code"""
    return COUNTRY_FLAGS.get(country_code, '🌍')

# Database file
DB_FILE = "reseller_bot.db"

# --- State Keys ---
# Used for storing conversation state
STATE_ADD_BALANCE = 1

# Language texts
TEXTS = {
    'en': {
        'welcome': '🤖 *Welcome {name}!*\n\nThis is a phone number reseller bot.\n\nUse the menu below to get started! 👇',
        'balance': '💰 *Your Balance*\n\nBalance: *${balance:.2f}* USD',
        'buy_button': '🛒 Buy Account',
        'wallet_button': '💰 Wallet',
        'profile_button': '👤 User Profile',
        'support_button': '🆘 Support',
        'language_button': '🌐 Language',
        'user_profile': '👤 *User Profile*\n\n🆔 User ID: `{user_id}`\n👤 Name: {name}\n📱 Username: {username}\n💰 Balance: ${balance:.2f}\n📦 Total Purchases: {purchases}',
        'support_msg': '🆘 *Need Help?*\n\nContact our support team:\n{support}\n\nWe are here to help you 24/7!',
        'language_changed': '✅ Language changed to English',
        'select_country': '🌍 *Select a country to purchase:*\n\n💰 Your balance: ${balance:.2f}',
        'insufficient': '❌ Insufficient balance!\n\nYour balance: ${balance:.2f}\nPlease contact admin to add balance.',
    },
    'ar': {
        'welcome': '🤖 *مرحباً {name}!*\n\nهذا بوت لبيع أرقام الهواتف.\n\nاستخدم القائمة أدناه للبدء! 👇',
        'balance': '💰 *رصيدك*\n\nالرصيد: *${balance:.2f}* دولار',
        'buy_button': '🛒 شراء حساب',
        'wallet_button': '💰 المحفظة',
        'profile_button': '👤 الملف الشخصي',
        'support_button': '🆘 الدعم',
        'language_button': '🌐 اللغة',
        'user_profile': '👤 *الملف الشخصي*\n\n🆔 معرف المستخدم: `{user_id}`\n👤 الاسم: {name}\n📱 اسم المستخدم: {username}\n💰 الرصيد: ${balance:.2f}\n📦 إجمالي المشتريات: {purchases}',
        'support_msg': '🆘 *هل تحتاج مساعدة؟*\n\nاتصل بفريق الدعم:\n{support}\n\nنحن هنا لمساعدتك على مدار الساعة!',
        'language_changed': '✅ تم تغيير اللغة إلى العربية',
        'select_country': '🌍 *اختر دولة للشراء:*\n\n💰 رصيدك: ${balance:.2f}',
        'insufficient': '❌ رصيد غير كافٍ!\n\nرصيدك: ${balance:.2f}\nيرجى الاتصال بالمسؤول لإضافة رصيد.',
    }
}

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Database Functions ---
def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0.0,
            total_spent REAL DEFAULT 0.0,
            total_purchases INTEGER DEFAULT 0,
            language TEXT DEFAULT 'en',
            active_reservation TEXT,
            reservation_message_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check and add columns if missing (migration)
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'language' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN language TEXT DEFAULT "en"')
        logger.info("Added language column to users table")
    if 'active_reservation' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN active_reservation TEXT')
        logger.info("Added active_reservation column to users table")
    if 'reservation_message_id' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN reservation_message_id INTEGER')
        logger.info("Added reservation_message_id column to users table")
    
    # Transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            description TEXT,
            phone TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Manual Payments table (for admin approval)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS manual_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending', -- pending, completed, cancelled
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Payments table (for Helecta - kept for completeness but not used in manual flow)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            transaction_id TEXT,
            amount REAL,
            status TEXT,
            payment_url TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Initialize markup if not exists
    cursor.execute('SELECT value FROM settings WHERE key = ?', ('markup',))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO settings (key, value) VALUES (?, ?)', ('markup', '0.05'))
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

def get_markup():
    """Get current markup value"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT value FROM settings WHERE key = ?', ('markup',))
    result = cursor.fetchone()
    
    conn.close()
    return float(result[0]) if result else 0.05

def set_markup(value):
    """Set markup value"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('markup', str(value)))
    conn.commit()
    conn.close()
    logger.info(f"Markup updated to ${value}")

def get_or_create_user(user_id, username=None, first_name=None):
    """Get user or create if doesn't exist"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, balance)
            VALUES (?, ?, ?, 0.0)
        ''', (user_id, username, first_name))
        conn.commit()
        logger.info(f"New user created: {user_id}")
    
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    
    conn.close()
    return balance

def update_user_balance(user_id, amount, transaction_type, description, phone=None):
    """Update user balance and log transaction"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Update balance
    cursor.execute('''
        UPDATE users 
        SET balance = balance + ? 
        WHERE user_id = ?
    ''', (amount, user_id))
    
    # Log transaction
    cursor.execute('''
        INSERT INTO transactions (user_id, type, amount, description, phone)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, transaction_type, amount, description, phone))
    
    # Update stats if purchase
    if transaction_type == 'purchase':
        cursor.execute('''
            UPDATE users 
            SET total_spent = total_spent + ?,
                total_purchases = total_purchases + 1
            WHERE user_id = ?
        ''', (abs(amount), user_id))
    
    conn.commit()
    conn.close()
    logger.info(f"Balance updated for user {user_id}: {amount}")

def get_user_balance(user_id):
    """Get user balance"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result else 0.0

def get_all_users():
    """Get all users (admin only)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, username, first_name, balance, total_purchases FROM users')
    users = cursor.fetchall()
    
    conn.close()
    return users

def get_user_transactions(user_id, limit=10):
    """Get user transaction history"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT type, amount, description, phone, timestamp
        FROM transactions
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (user_id, limit))
    
    transactions = cursor.fetchall()
    conn.close()
    return transactions

def get_user_language(user_id):
    """Get user's preferred language"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result else 'en'

def set_user_language(user_id, language):
    """Set user's preferred language"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET language = ? WHERE user_id = ?', (language, user_id))
    conn.commit()
    conn.close()

def get_text(user_id, key):
    """Get translated text for user"""
    lang = get_user_language(user_id)
    return TEXTS.get(lang, TEXTS['en']).get(key, TEXTS['en'].get(key, ''))

def get_user_stats(user_id):
    """Get user statistics"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT username, first_name, balance, total_purchases FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result if result else (None, None, 0.0, 0)

def get_active_reservation(user_id):
    """Get user's active reservation"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT active_reservation FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result and result[0] else None

def set_active_reservation(user_id, phone):
    """Set user's active reservation"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET active_reservation = ? WHERE user_id = ?', (phone, user_id))
    conn.commit()
    conn.close()

def set_reservation_message_id(user_id, message_id):
    """Set reservation message ID"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET reservation_message_id = ? WHERE user_id = ?', (message_id, user_id))
    conn.commit()
    conn.close()

def get_reservation_message_id(user_id):
    """Get reservation message ID"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT reservation_message_id FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result and result[0] else None

def clear_active_reservation(user_id):
    """Clear user's active reservation"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET active_reservation = NULL, reservation_message_id = NULL WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def create_manual_payment_request(user_id, amount):
    """Create a manual payment request entry in the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    request_id = str(uuid.uuid4())[:8].upper() # 8-character unique ID
    
    cursor.execute('''
        INSERT INTO manual_payments (request_id, user_id, amount, status)
        VALUES (?, ?, ?, 'pending')
    ''', (request_id, user_id, amount))
    
    conn.commit()
    conn.close()
    return request_id

def complete_manual_payment(request_id):
    """Complete a manual payment request, update user balance, and return user_id/amount."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, amount, status FROM manual_payments WHERE request_id = ?', (request_id,))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return None, None, "not_found"
        
    user_id, amount, status = result
    
    if status == 'completed':
        conn.close()
        return user_id, amount, "already_completed"

    # Update payment status
    cursor.execute('''
        UPDATE manual_payments 
        SET status = 'completed'
        WHERE request_id = ?
    ''', (request_id,))
    
    conn.commit()
    conn.close()
    
    return user_id, amount, "success"

# The original create_helecta_payment is kept here but not used in the manual flow
def create_helecta_payment(user_id, amount):
    """Create payment request with Helecta"""
    try:
        import uuid
        transaction_id = str(uuid.uuid4())
        
        # Helecta API request
        headers = {
            'Authorization': f'Bearer {HELECTA_API_KEY}',
            'Merchant-Key': HELECTA_MERCHANT_KEY,
            'Content-Type': 'application/json'
        }
        
        payload = {
            'amount': amount,
            'currency': 'USD',
            'transaction_id': transaction_id,
            'callback_url': f'https://your-bot-webhook.com/payment/{transaction_id}',
            'return_url': f'https://t.me/YourBotUsername'
        }
        
        response = requests.post(
            f'{HELECTA_API_URL}/payment/create',
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            payment_url = data.get('payment_url')
            
            # Save to database
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO payments (user_id, transaction_id, amount, status, payment_url)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, transaction_id, amount, 'pending', payment_url))
            conn.commit()
            conn.close()
            
            return {'success': True, 'payment_url': payment_url, 'transaction_id': transaction_id}
        else:
            return {'success': False, 'error': 'Payment creation failed'}
            
    except Exception as e:
        logger.error(f"Helecta payment error: {e}")
        return {'success': False, 'error': str(e)}

def get_main_menu_keyboard(user_id):
    """Get main menu keyboard"""
    lang = get_user_language(user_id)
    texts = TEXTS[lang]
    
    keyboard = [
        [
            InlineKeyboardButton(texts['buy_button'], callback_data='menu_buy'),
            InlineKeyboardButton(texts['wallet_button'], callback_data='menu_wallet')
        ],
        [
            InlineKeyboardButton(texts['profile_button'], callback_data='menu_profile'),
            InlineKeyboardButton('💳 Add Balance', callback_data='menu_payment')
        ],
        [
            InlineKeyboardButton(texts['support_button'], callback_data='menu_support'),
            InlineKeyboardButton(texts['language_button'], callback_data='menu_language')
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def get_persistent_menu_keyboard(user_id):
    """Get persistent menu keyboard (always visible)"""
    lang = get_user_language(user_id)
    texts = TEXTS[lang]
    
    keyboard = [
        [
            KeyboardButton(texts['buy_button']),
            KeyboardButton(texts['wallet_button'])
        ],
        [
            KeyboardButton(texts['profile_button']),
            KeyboardButton('💳 Add Balance')
        ]
    ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- Helper Functions ---
def apply_markup(api_price):
    """Apply fixed markup to API price"""
    markup = get_markup()
    return api_price + markup

def calculate_profit(api_price):
    """Calculate profit from markup"""
    return get_markup()

def is_admin(user_id):
    """Check if user is admin"""
    return user_id == ADMIN_USER_ID

# --- API Helper Functions ---
def make_api_request(endpoint, method="GET", data=None):
    """Make API request with authentication"""
    headers = {
        "Authorization": f"Bearer {EXTERNAL_API_KEY}",
        "Content-Type": "application/json"
    }
    
    url = f"{API_BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                raise Exception(error_data.get('error', str(e)))
            except:
                raise Exception(f"API Error: {e.response.status_code}")
        raise Exception(f"Connection error: {str(e)}")

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)
    
    welcome_text = get_text(user.id, 'welcome').format(name=user.first_name)
    
    keyboard = get_persistent_menu_keyboard(user.id)
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=keyboard
    )

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user balance"""
    user_id = update.effective_user.id
    user_balance = get_user_balance(user_id)
    
    message = get_text(user_id, 'balance').format(balance=user_balance)
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def countries(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available countries"""
    try:
        user_id = update.effective_user.id
        user_balance = get_user_balance(user_id)
        
        await update.message.reply_text('⏳ Loading countries...')
        
        result = make_api_request('/accounts')
        all_countries = result['data']['countries']
        
        # Filter only allowed countries
        countries_list = [c for c in all_countries if c['code'] in ALLOWED_COUNTRIES]
        
        if not countries_list:
            await update.message.reply_text('❌ No countries available at the moment.')
            return
        
        # Sort by price
        countries_list.sort(key=lambda x: x['price'])
        
        message = f'🌍 *Available Countries*\n\n💰 Your Balance: ${user_balance:.2f}\n\n'
        
        for idx, country in enumerate(countries_list, 1):
            api_price = country['price']
            user_price = apply_markup(api_price)
            
            # Remove the afforability emoji (✅/❌) as requested
            
            message += f"{idx}. {get_country_flag(country['code'])} *{country['name']}*\n"
            message += f"   💵 ${user_price:.2f} | 📱 {country['available']} available\n\n"
        
        message += '━━━━━━━━━━━━━━━━\n'
        message += '💡 Use /buy to purchase!'
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buy phone number with interactive buttons"""
    try:
        user_id = update.effective_user.id
        user_balance = get_user_balance(user_id)
        
        result = make_api_request('/accounts')
        all_countries = result['data']['countries']
        
        # Filter only allowed countries
        countries_list = [c for c in all_countries if c['code'] in ALLOWED_COUNTRIES]
        
        if not countries_list:
            await update.message.reply_text('❌ No countries available at the moment.')
            return
        
        # Sort by price
        countries_list.sort(key=lambda x: x['price'])
        
        # Show ALL countries regardless of balance (even if $0)
        keyboard = []
        for country in countries_list:
            if country['available'] <= 0:
                continue
                
            api_price = country['price']
            user_price = apply_markup(api_price)
            flag = get_country_flag(country['code'])
            
            # --- REMOVED EMOJIS (✅/❌) FROM BUTTON TEXT ---
            button_text = f"{flag} {country['name']} - ${user_price:.2f}"
            
            # Keep the callback logic for affordability check in the next step
            if user_balance > 0 and user_price <= user_balance:
                callback_data = f"buy_{country['code']}"
            else:
                callback_data = f"insufficient_{country['code']}_{user_price:.2f}"
            # -----------------------------------------------
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
        if not keyboard:
            await update.message.reply_text('❌ No countries available at the moment.')
            return
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f'🌍 *Available Countries*\n\n💰 Your Balance: ${user_balance:.2f}'
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')

async def my_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user's purchase history from transactions"""
    try:
        user_id = update.effective_user.id
        transactions = get_user_transactions(user_id, limit=20)
        
        purchase_trans = [t for t in transactions if t[0] == 'purchase']
        
        if not purchase_trans:
            await update.message.reply_text('📭 You have no purchase history.')
            return
        
        message = "📚 *Your Purchase History*\n\n"
        
        for idx, trans in enumerate(purchase_trans[:10], 1):
            trans_type, amount, description, phone, timestamp = trans
            message += f"{idx}. 📱 `{phone}`\n"
            message += f"   💰 ${abs(amount):.2f}\n"
            message += f"   📅 {timestamp}\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')

async def transactions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View transaction history"""
    try:
        user_id = update.effective_user.id
        transactions = get_user_transactions(user_id, limit=15)
        
        if not transactions:
            await update.message.reply_text('📭 No transaction history.')
            return
        
        message = "📊 *Transaction History*\n\n"
        
        for trans in transactions:
            trans_type, amount, description, phone, timestamp = trans
            emoji = "💰" if amount > 0 else "💸"
            message += f"{emoji} *{trans_type.title()}*\n"
            message += f"   Amount: ${amount:.2f}\n"
            message += f"   {description}\n"
            message += f"   📅 {timestamp}\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')

# --- Admin Commands ---
async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all users (admin only)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text('❌ This command is only for admins.')
        return
    
    try:
        users = get_all_users()
        
        if not users:
            await update.message.reply_text('📭 No users found.')
            return
        
        message = "👥 *All Users*\n\n"
        
        for user in users:
            user_id, username, first_name, balance, purchases = user
            username_text = f"@{username}" if username else "No username"
            message += f"👤 {first_name} ({username_text})\n"
            message += f"   ID: `{user_id}`\n"
            message += f"   💰 ${balance:.2f} | 📦 {purchases} purchases\n\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')

async def addbalance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add balance to user (admin only)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text('❌ This command is only for admins.')
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            '❌ Usage: /addbalance <user_id> <amount>\n\n'
            'Example: /addbalance 123456789 10.50'
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        amount = float(context.args[1])
        
        if amount <= 0:
            await update.message.reply_text('❌ Amount must be positive.')
            return
        
        # Update balance
        update_user_balance(
            target_user_id,
            amount,
            'deposit',
            f'Balance added by admin',
            None
        )
        
        new_balance = get_user_balance(target_user_id)
        
        await update.message.reply_text(
            f'✅ Balance added successfully!\n\n'
            f'User ID: `{target_user_id}`\n'
            f'Amount: ${amount:.2f}\n'
            f'New Balance: ${new_balance:.2f}',
            parse_mode='Markdown'
        )
        
    except ValueError:
        await update.message.reply_text('❌ Invalid user ID or amount.')
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """System statistics (admin only)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text('❌ This command is only for admins.')
        return
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get stats
        cursor.execute('SELECT COUNT(*), SUM(balance), SUM(total_spent), SUM(total_purchases) FROM users')
        total_users, total_balance, total_spent, total_purchases = cursor.fetchone()
        
        conn.close()
        
        # Get API balance
        try:
            api_result = make_api_request('/user/balance')
            api_balance = api_result['data']['balance']
        except:
            api_balance = 0.0
        
        # Get current markup
        markup = get_markup()
        estimated_profit = (total_purchases or 0) * markup
        
        message = f"""
📊 *System Statistics*

👥 Total Users: {total_users or 0}
💰 Total User Balance: ${total_balance or 0:.2f}
💸 Total Spent: ${total_spent or 0:.2f}
📦 Total Purchases: {total_purchases or 0}

🏦 *API Account*
Balance: ${api_balance:.2f}

💵 *Markup Settings*
Current Markup: ${markup:.2f} per purchase
Estimated Total Profit: ${estimated_profit:.2f}

Use /setmarkup to change markup amount.
        """
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')

async def setmarkup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set markup value (admin only)"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text('❌ This command is only for admins.')
        return
    
    if len(context.args) < 1:
        current_markup = get_markup()
        await update.message.reply_text(
            f'💵 *Current Markup*\n\n'
            f'Markup: ${current_markup:.2f}\n\n'
            f'Usage: /setmarkup <amount>\n\n'
            f'Example: /setmarkup 0.10\n'
            f'This will add $0.10 to each purchase.',
            parse_mode='Markdown'
        )
        return
    
    try:
        new_markup = float(context.args[0])
        
        if new_markup < 0:
            await update.message.reply_text('❌ Markup must be positive or zero.')
            return
        
        if new_markup > 10:
            await update.message.reply_text('❌ Markup seems too high. Maximum is $10.')
            return
        
        set_markup(new_markup)
        
        await update.message.reply_text(
            f'✅ Markup updated successfully!\n\n'
            f'Old Markup: ${get_markup():.2f}\n'
            f'New Markup: ${new_markup:.2f}\n\n'
            f'All new purchases will use this markup.',
            parse_mode='Markdown'
        )
        
    except ValueError:
        await update.message.reply_text('❌ Invalid amount. Use a number like 0.05 or 0.10')
    except Exception as e:
        await update.message.reply_text(f'❌ Error: {str(e)}')

# --- Callback Query Handler ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    try:
        # Handle main menu buttons
        if data == 'menu_buy':
            # Directly show countries, no balance check
            await buy_menu(query, user_id)
        
        elif data == 'menu_wallet':
            user_balance = get_user_balance(user_id)
            message = get_text(user_id, 'balance').format(balance=user_balance)
            keyboard = get_main_menu_keyboard(user_id)
            await query.message.edit_text(message, parse_mode='Markdown', reply_markup=keyboard)
        
        elif data == 'menu_profile':
            username, first_name, balance, purchases = get_user_stats(user_id)
            username_text = f"@{username}" if username else "No username"
            
            # Escape special characters for Markdown
            first_name_safe = (first_name or "Unknown").replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            username_safe = username_text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            
            message = f"""👤 *User Profile*

🆔 User ID: `{user_id}`
👤 Name: {first_name_safe}
📱 Username: {username_safe}
💰 Balance: ${balance:.2f}
📦 Total Purchases: {purchases}"""
            
            keyboard = [[InlineKeyboardButton('« Back', callback_data='menu_back')]]
            await query.message.edit_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif data == 'menu_support':
            message = get_text(user_id, 'support_msg').format(support=SUPPORT_USERNAME)
            keyboard = [[InlineKeyboardButton('« Back', callback_data='menu_back')]]
            await query.message.edit_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif data == 'menu_payment':
            # Manual Payment Request Menu
            keyboard = [
                [InlineKeyboardButton('💵 $5', callback_data='req_5'), InlineKeyboardButton('💵 $10', callback_data='req_10')],
                [InlineKeyboardButton('💵 $20', callback_data='req_20'), InlineKeyboardButton('💵 $50', callback_data='req_50')],
                [InlineKeyboardButton('💰 Custom Amount', callback_data='req_custom')], # ADDED CUSTOM BUTTON
                [InlineKeyboardButton('« Back', callback_data='menu_back')]
            ]
            
            # --- MESSAGE WITH PAYMENT ID ---
            payment_id = "851008371"
            
            message = f"""
💳 *Add Balance (Manual Payment)*

**1. Pay the amount:**
Please pay your desired amount to this Binance ID: 
👉 `{payment_id}`

**2. Select Amount Below:**
Select the amount you wish to add below. You will receive a unique ID.
*(Click 'Custom Amount' to enter your own value, minimum $0.50)*

**3. Submit Proof:**
Send your payment proof along with the unique ID to our support: **{SUPPORT_USERNAME}**.

Once the payment is verified, the admin will approve your request.
            """
            
            await query.message.edit_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

        # Handle Custom Amount Request Activation
        elif data == 'req_custom':
            # Set state to await custom amount input
            context.user_data['state'] = STATE_ADD_BALANCE 
            keyboard = [[InlineKeyboardButton('❌ Cancel', callback_data='menu_back')]]
            
            await query.message.edit_text(
                "✍️ *Enter Custom Amount*\n\nPlease type the amount you wish to add (minimum $0.50).",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return # IMPORTANT: Do not run the rest of the button_callback
        
        # Manual Payment Request Handling (req_X)
        elif data.startswith('req_'):
            amount_str = data.replace('req_', '')
            
            try:
                amount = float(amount_str)
                
                # 1. Create manual payment request and get unique ID
                request_id = create_manual_payment_request(user_id, amount)
                
                # 2. Inform the user
                user_message = f"""
✅ *Payment Request Created*

Amount: *${amount:.2f}*
Unique ID: `{request_id}`

⚠️ *Next Steps:*
1. Send the payment to the admin/support account.
2. Send this *Unique ID* and the *Payment Proof (Screenshot)* to our support: **{SUPPORT_USERNAME}**.

Your balance will be added immediately after admin confirmation.
"""
                keyboard = [[InlineKeyboardButton('« Back to Menu', callback_data='menu_back')]]
                await query.message.edit_text(user_message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
                
                # 3. Inform the Admin
                user_info = update.effective_user.mention_markdown()
                admin_message = f"""
🔔 *NEW MANUAL PAYMENT REQUEST*

👤 User: {user_info}
🆔 User ID: `{user_id}`
💰 Amount: *${amount:.2f}*
🔐 Unique ID: `{request_id}`

_Awaiting payment proof from user to {SUPPORT_USERNAME}._
"""
                admin_keyboard = [[
                    InlineKeyboardButton(f'✅ Add ${amount:.2f} to {user_id}', callback_data=f'manual_complete_{request_id}')
                ]]
                
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=admin_message,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(admin_keyboard)
                )

            except Exception as e:
                await query.answer(f'Error processing request: {str(e)}', show_alert=True)
        
        # Admin action to complete payment (manual_complete_)
        elif data.startswith('manual_complete_'):
            if not is_admin(user_id):
                await query.answer('❌ You are not authorized to complete payments.', show_alert=True)
                return
            
            request_id = data.replace('manual_complete_', '')
            
            # Try to complete the payment in DB
            target_user_id, amount, status = complete_manual_payment(request_id)
            
            if status == "not_found":
                await query.message.edit_text(f'❌ Error: Payment request with ID `{request_id}` not found.', parse_mode='Markdown')
            elif status == "already_completed":
                await query.message.edit_text(f'❌ Error: Payment request with ID `{request_id}` was already completed.', parse_mode='Markdown')
            elif status == "success":
                # 1. Update user balance
                update_user_balance(
                    target_user_id,
                    amount,
                    'deposit',
                    f'Manual deposit approved by Admin for request ID: {request_id}',
                    None
                )
                new_balance = get_user_balance(target_user_id)
                
                # 2. Inform the Admin (Edit their message)
                admin_confirmation = f"""
✅ *PAYMENT APPROVED*

User ID: `{target_user_id}`
Amount: ${amount:.2f}
Unique ID: `{request_id}`

Balance added successfully!
New Balance: ${new_balance:.2f}
"""
                await query.message.edit_text(admin_confirmation, parse_mode='Markdown')
                
                # 3. Inform the User (Send a new message to the user)
                user_confirmation = f"""
🎉 *Balance Added!*

✅ Your manual payment of *${amount:.2f}* has been verified and approved by the admin!
💰 Your new balance is: *${new_balance:.2f}*
"""
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=user_confirmation,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to send confirmation to user {target_user_id}: {e}")
        
        elif data == 'menu_back':
            user = update.effective_user
            # If canceling custom amount input, clear state
            if context.user_data.get('state') == STATE_ADD_BALANCE:
                context.user_data['state'] = None
                
            welcome_text = get_text(user_id, 'welcome').format(name=user.first_name)
            keyboard = get_main_menu_keyboard(user_id)
            await query.message.edit_text(welcome_text, parse_mode='Markdown', reply_markup=keyboard)
        
        # Handle insufficient balance notification
        elif data.startswith('insufficient_'):
            parts = data.split('_')
            country_code = parts[1]
            price = parts[2]
            
            user_balance = get_user_balance(user_id)
            needed = float(price) - user_balance
            
            flag = get_country_flag(country_code)
            
            # Show in reply message, not popup
            message = f"""
❌ *Insufficient Balance*

{flag} Price: ${price}
💰 Your balance: ${user_balance:.2f}
📉 You need: ${needed:.2f} more

Please contact admin to add balance.
            """
            
            await query.answer()  # Just acknowledge the click
            await query.message.reply_text(message, parse_mode='Markdown')
            return
        
        # Handle country selection for purchase
        elif data.startswith('buy_'):
            country_code = data.replace('buy_', '')
            
            # Check if country is allowed
            if country_code not in ALLOWED_COUNTRIES:
                await query.message.reply_text('❌ This country is not available for purchase.')
                return
            
            # Get country price
            result = make_api_request('/accounts')
            country = next((c for c in result['data']['countries'] if c['code'] == country_code), None)
            
            if not country:
                await query.message.reply_text('❌ Country not found.')
                return
            
            api_price = country['price']
            user_price = apply_markup(api_price)
            
            # Check user balance
            user_balance = get_user_balance(user_id)
            
            if user_balance < user_price:
                needed = user_price - user_balance
                
                flag = get_country_flag(country['code']) # Use country code for flag
                
                message = f"""
❌ *Insufficient Balance*

{flag} *{country['name']}*
💰 Price: ${user_price:.2f}
💵 Your balance: ${user_balance:.2f}
📉 You need: ${needed:.2f} more

Use 💳 Add Balance to add funds.
                """
                
                keyboard = [[InlineKeyboardButton('💳 Add Balance', callback_data='menu_payment')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.answer()
                await query.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
                return
            
            # Check if user already has an active reservation
            existing_reservation = get_active_reservation(user_id)
            if existing_reservation:
                try:
                    # Cancel the old reservation
                    make_api_request('/account/cancel-reserve', 'POST', {'phone': existing_reservation})
                    logger.info(f"Auto-cancelled old reservation: {existing_reservation}")
                except Exception as e:
                    logger.error(f"Failed to cancel old reservation: {e}")
            
            # Delete the country selection message
            try:
                await query.message.delete()
            except:
                pass
            
            loading_msg = await query.message.reply_text('⏳ Reserving phone number...')
            
            # Reserve number from API (DON'T deduct balance yet)
            api_result = make_api_request('/account/reserve-number', 'POST', {
                'country_code': country_code
            })
            
            reservation = api_result['data']
            expires_minutes = reservation['expires_in'] // 60
            
            # Store reservation info (price) for later
            # We'll deduct balance only when code is received
            context.user_data[f'pending_price_{reservation["phone"]}'] = user_price
            
            # Set as active reservation
            set_active_reservation(user_id, reservation['phone'])
            
            new_balance = get_user_balance(user_id)
            profit = calculate_profit(api_price)
            flag = get_country_flag(country['code']) # Use country code for flag
            
            message = f"""
✅ *Phone Number Reserved!*

{flag} *{reservation['country']}*
📱 Number: `{reservation['phone']}`
💰 Price: ${user_price:.2f}
⏰ Expires in: {expires_minutes} minutes

💵 Your balance: ${new_balance:.2f}

⚠️ *Balance will be deducted when you receive the login code.*

Use buttons below to get codes.
            """
            
            keyboard = [[
                InlineKeyboardButton('🔑 Get Codes', callback_data=f"codes_{reservation['phone']}"),
                InlineKeyboardButton('❌ Cancel', callback_data=f"cancel_{reservation['phone']}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Delete loading message
            try:
                await loading_msg.delete()
            except:
                pass
            
            # Send and store message ID for later deletion
            sent_msg = await query.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            set_reservation_message_id(user_id, sent_msg.message_id)
        
        # Handle cancel reservation
        elif data.startswith('cancel_'):
            phone = data.replace('cancel_', '')
            
            # Delete previous message
            try:
                await query.message.delete()
            except:
                pass
            
            loading_msg = await query.message.reply_text('⏳ Cancelling reservation...')
            
            try:
                make_api_request('/account/cancel-reserve', 'POST', {'phone': phone})
                
                # Remove from pending (no refund needed since balance wasn't deducted)
                pending_price_key = f'pending_price_{phone}'
                if pending_price_key in context.user_data:
                    del context.user_data[pending_price_key]
                
                # Clear active reservation
                clear_active_reservation(user_id)
                
                # Delete loading message
                try:
                    await loading_msg.delete()
                except:
                    pass
                
                success_msg = await query.message.reply_text(
                    f'✅ Reservation cancelled!\n\n'
                    f'📱 {phone}\n'
                    f'💰 No charges applied.'
                )
                
                # Delete success message after 5 seconds
                import asyncio
                await asyncio.sleep(5)
                try:
                    await success_msg.delete()
                except:
                    pass
                    
            except Exception as e:
                # Delete loading message
                try:
                    await loading_msg.delete()
                except:
                    pass
                
                await query.message.reply_text(f'❌ Error cancelling: {str(e)}')
        
        # Handle get codes
        elif data.startswith('codes_'):
            phone = data.replace('codes_', '')
            
            # Delete previous message
            try:
                await query.message.delete()
            except:
                pass
            
            loading_msg = await query.message.reply_text('⏳ Getting codes...')
            
            try:
                result = make_api_request('/account/get-code', 'POST', {'phone': phone})
                codes = result['data']['codes']
                otp = codes['otp']
                password = codes['password']
                
                # Check if this is a Telegram login code (5-6 digits)
                is_telegram_code = otp and len(str(otp)) >= 5 and str(otp).isdigit()
                
                # If telegram code received, deduct balance NOW
                if is_telegram_code:
                    # Get pending price
                    pending_price_key = f'pending_price_{phone}'
                    if pending_price_key in context.user_data:
                        price = context.user_data[pending_price_key]
                        
                        # Deduct balance
                        update_user_balance(
                            user_id,
                            -price,
                            'purchase',
                            f'Phone number purchased with code: {phone}',
                            phone
                        )
                        
                        # Remove from pending
                        del context.user_data[pending_price_key]
                        
                        new_balance = get_user_balance(user_id)
                        balance_info = f'\n💰 *Balance deducted: ${price:.2f}*\n💵 New balance: ${new_balance:.2f}\n'
                    else:
                        balance_info = ''
                else:
                    balance_info = '\n⚠️ Waiting for Telegram login code...\n'
                
                message = f"""
🔑 *Verification Codes*

📱 Phone: `{result['data']['phone']}`
🔢 OTP: `{otp}`
🔐 Password: `{password or 'N/A'}`
{balance_info}
*Tap to copy the codes above.*
                """
                
                keyboard = [[
                    InlineKeyboardButton('🚪 Logout', callback_data=f"logout_{result['data']['phone']}"),
                    InlineKeyboardButton('🔄 Refresh', callback_data=f"codes_{result['data']['phone']}")
                ]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Delete loading message
                try:
                    await loading_msg.delete()
                except:
                    pass
                
                await query.message.edit_text(message, parse_mode='Markdown', reply_markup=reply_markup)
                
            except Exception as e:
                # Delete loading message
                try:
                    await loading_msg.delete()
                except:
                    pass
                
                await query.message.edit_text(f'❌ Error getting codes: {str(e)}')
        
        # Handle logout
        elif data.startswith('logout_'):
            phone = data.replace('logout_', '')
            
            # Delete previous message
            try:
                await query.message.delete()
            except:
                pass
            
            loading_msg = await query.message.reply_text('⏳ Logging out...')
            
            make_api_request('/account/logout', 'POST', {'phone': phone})
            
            # Delete loading message
            try:
                await loading_msg.delete()
            except:
                pass
            
            success_msg = await query.message.reply_text(f'✅ Successfully logged out from {phone}')
            
            # Delete success message after 5 seconds
            import asyncio
            await asyncio.sleep(5)
            try:
                await success_msg.delete()
            except:
                pass
    
    except Exception as e:
        # Don't delete error messages
        await query.message.reply_text(f'❌ Error: {str(e)}')

async def buy_menu(query, user_id):
    """Show buy menu"""
    try:
        user_balance = get_user_balance(user_id)
        
        result = make_api_request('/accounts')
        all_countries = result['data']['countries']
        
        # Filter only allowed countries
        countries_list = [c for c in all_countries if c['code'] in ALLOWED_COUNTRIES]
        
        if not countries_list:
            await query.message.edit_text('❌ No countries available at the moment.')
            return
        
        # Sort by price
        countries_list.sort(key=lambda x: x['price'])
        
        # Show ALL countries regardless of balance
        keyboard = []
        for country in countries_list:
            if country['available'] <= 0:
                continue
                
            api_price = country['price']
            user_price = apply_markup(api_price)
            flag = get_country_flag(country['code'])
            
            # --- REMOVED EMOJIS (✅/❌) FROM BUTTON TEXT ---
            button_text = f"{flag} {country['name']} - ${user_price:.2f}"
            
            # Keep the callback logic for affordability check in the next step
            if user_balance > 0 and user_price <= user_balance:
                callback_data = f"buy_{country['code']}"
            else:
                callback_data = f"insufficient_{country['code']}_{user_price:.2f}"
            # -----------------------------------------------
            
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        if not keyboard:
            await query.message.edit_text('❌ No countries available at the moment.')
            return
            
        keyboard.append([InlineKeyboardButton('« Back', callback_data='menu_back')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f'🌍 *Available Countries*\n\n💰 Your Balance: ${user_balance:.2f}'
        
        await query.message.edit_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    except Exception as e:
        await query.message.edit_text(f'❌ Error: {str(e)}')

# --- Main Function ---
def main():
    """Start the bot"""
    # Initialize database
    init_database()
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("countries", countries))
    application.add_handler(CommandHandler("buy", buy))
    application.add_handler(CommandHandler("myhistory", my_history))
    application.add_handler(CommandHandler("transactions", transactions_command))
    
    # Handle text messages for persistent menu
    async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        user_id = update.effective_user.id
        
        # --- NEW: Handle Custom Amount Input State ---
        if context.user_data.get('state') == STATE_ADD_BALANCE:
            try:
                custom_amount = float(text)
                
                if custom_amount < 0.50:
                    # Clear chat by sending a new reply keyboard (main menu)
                    await update.message.reply_text(
                        "❌ Minimum amount accepted is $0.50. Please enter a higher value or click 'Cancel'.",
                        parse_mode='Markdown',
                        reply_markup=get_persistent_menu_keyboard(user_id)
                    )
                    return
                
                # Clear state
                context.user_data['state'] = None
                
                # Directly proceed to create the request (same logic as 'req_X' button click)
                request_id = create_manual_payment_request(user_id, custom_amount)
                
                # 2. Inform the user (similar to req_ logic)
                user_message = f"""
✅ *Payment Request Created*

Amount: *${custom_amount:.2f}*
Unique ID: `{request_id}`

⚠️ *Next Steps:*
1. Send the payment to the admin/support account.
2. Send this *Unique ID* and the *Payment Proof (Screenshot)* to our support: **{SUPPORT_USERNAME}**.

Your balance will be added immediately after admin confirmation.
"""
                # Send with persistent menu keyboard
                await update.message.reply_text(user_message, parse_mode='Markdown', reply_markup=get_persistent_menu_keyboard(user_id))
                
                # 3. Inform the Admin
                user_info = update.effective_user.mention_markdown()
                admin_message = f"""
🔔 *NEW MANUAL PAYMENT REQUEST (CUSTOM)*

👤 User: {user_info}
🆔 User ID: `{user_id}`
💰 Amount: *${custom_amount:.2f}*
🔐 Unique ID: `{request_id}`

_Awaiting payment proof from user to {SUPPORT_USERNAME}._
"""
                admin_keyboard = [[
                    InlineKeyboardButton(f'✅ Add ${custom_amount:.2f} to {user_id}', callback_data=f'manual_complete_{request_id}')
                ]]
                
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=admin_message,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(admin_keyboard)
                )

                return
                
            except ValueError:
                await update.message.reply_text("❌ Invalid input. Please enter a valid number for the amount (e.g., 5.50).")
                return
            except Exception as e:
                context.user_data['state'] = None
                await update.message.reply_text(f"❌ An error occurred: {str(e)}")
                return
        # --- END Custom Amount Input State ---
        
        # Delete reservation message if exists
        reservation_msg_id = get_reservation_message_id(user_id)
        if reservation_msg_id:
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=reservation_msg_id
                )
                set_reservation_message_id(user_id, None)  # Clear stored message ID
            except Exception as e:
                logger.error(f"Failed to delete reservation message: {e}")
        
        if '🛒' in text or 'Buy' in text:
            await buy(update, context)
        elif '💰' in text or 'Wallet' in text:
            await balance(update, context)
        elif '👤' in text or 'Profile' in text:
            username, first_name, balance_amt, purchases = get_user_stats(user_id)
            username_text = f"@{username}" if username else "No username"
            
            # Escape special characters for Markdown
            first_name_safe = (first_name or "Unknown").replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            username_safe = username_text.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
            
            message = f"""👤 *User Profile*

🆔 User ID: `{user_id}`
👤 Name: {first_name_safe}
📱 Username: {username_safe}
💰 Balance: ${balance_amt:.2f}
📦 Total Purchases: {purchases}"""
            
            await update.message.reply_text(message, parse_mode='Markdown')
        elif '🆘' in text or 'Support' in text:
            message = get_text(user_id, 'support_msg').format(support=SUPPORT_USERNAME)
            await update.message.reply_text(message, parse_mode='Markdown')
        elif '💳' in text or 'Add Balance' in text:
            # Manual Payment Request Menu (as handled by callback)
            keyboard = [
                [InlineKeyboardButton('💵 $5', callback_data='req_5'), InlineKeyboardButton('💵 $10', callback_data='req_10')],
                [InlineKeyboardButton('💵 $20', callback_data='req_20'), InlineKeyboardButton('💵 $50', callback_data='req_50')],
                [InlineKeyboardButton('💰 Custom Amount', callback_data='req_custom')],
            ]
            
            # --- MESSAGE WITH PAYMENT ID ---
            payment_id = "851008371"
            
            message = f"""
💳 *Add Balance (Manual Payment)*

**1. Pay the amount:**
Please pay your desired amount to this Binance ID: 
👉 `{payment_id}`

**2. Select Amount Below:**
Select the amount you wish to add below. You will receive a unique ID.
*(Click 'Custom Amount' to enter your own value, minimum $0.50)*

**3. Submit Proof:**
Send your payment proof along with the unique ID to our support: **{SUPPORT_USERNAME}**.

Once the payment is verified, the admin will approve your request.
            """
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Admin commands
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("addbalance", addbalance_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("setmarkup", setmarkup_command))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start the bot
    logger.info("🤖 Reseller Bot is starting...")
    logger.info("✅ Database initialized")
    logger.info(f"👑 Admin ID: {ADMIN_USER_ID}")
    logger.info(f"💰 Current Markup: ${get_markup():.2f}")
    logger.info("📡 Bot is now running!")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()