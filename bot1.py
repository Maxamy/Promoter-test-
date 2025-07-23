import sqlite3
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from cryptography.fernet import Fernet  # For encryption
import requests  # For crypto rates

# ===== CONFIGURATION =====
BOT_TOKEN = "7429115282:AAHOc7UESTfl648pUr6_tavWqlhCYtVHLsw"  # From @BotFather
ADMIN_ID = 8142148294         # Your Telegram ID
CHANNEL_ID = "@testnetprof"   # Your channel username
SUPPORT_USERNAME = "@Maxamy1" # Support contact
ANALYTICS_URL = "https://your-analytics.com"  # For tracking

# Crypto Configuration
PAYMENT_ADDRESSES = {
    "usdt_trx": "TTZnPBeSoX95NhB7xQ4gfac5HF4qqAJ5xW",
    "ton": "UQAmPfO35H-q2sXMsi4kVQ5AhsVnG1TbFBeRxIxnZBRR4Em-"
}

# Security Configuration
ENCRYPTION_KEY = Fernet.generate_key()  # Store this securely in production
cipher_suite = Fernet(ENCRYPTION_KEY)

# ===== DATABASE SETUP =====
def init_db():
    conn = sqlite3.connect('promotion_bot.db')
    cursor = conn.cursor()
    
    # User accounts
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        ad_credits INTEGER DEFAULT 0,
        premium_expiry TEXT,
        invite_count INTEGER DEFAULT 0,
        last_active TEXT,
        encrypted_data TEXT  # For sensitive info
    )''')
    
    # Financial records
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        encrypted_amount TEXT,
        currency TEXT,
        encrypted_tx TEXT,
        status TEXT DEFAULT 'pending',
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Ad content
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ads (
        ad_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        encrypted_content TEXT,
        status TEXT DEFAULT 'pending',
        views INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()

# ===== SECURITY UTILITIES =====
def encrypt_data(data: str) -> str:
    """Encrypt sensitive data before storage"""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Decrypt stored data"""
    return cipher_suite.decrypt(encrypted_data.encode()).decode()

# ===== CORE COMMANDS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced start command with TOS"""
    keyboard = [
        [InlineKeyboardButton("📢 Submit Ad", callback_data='submit_help')],
        [InlineKeyboardButton("💎 Pricing", callback_data='pricing')],
        [InlineKeyboardButton("📜 Terms", callback_data='tos')]
    ]
    
    await update.message.reply_text(
        "🌟 <b>Ad Promotion Bot</b>\n\n"
        "✅ Submit ads for channels\n"
        "💰 Earn from referrals\n"
        "🛡️ Admin-approved content only\n\n"
        "By using this bot you agree to our /tos",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def tos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Terms of Service"""
    await update.message.reply_text(
        "📜 <b>Terms of Service</b>\n\n"
        "1. No spam/scams/illegal content\n"
        "2. Payments are non-refundable\n"
        "3. Max 3 ads/day per user\n"
        "4. Violations result in bans\n\n"
        "Full terms: https://your-bot.com/terms",
        parse_mode='HTML'
    )

# ===== PAYMENT SERVICES =====
async def pricing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Complete payment menu"""
    keyboard = [
        [InlineKeyboardButton("💎 1 Ad (100 Stars)", callback_data='pay_single_stars'),
         InlineKeyboardButton("🚀 Monthly (2000 Stars)", callback_data='pay_monthly_stars')],
        [InlineKeyboardButton("💰 Crypto Options", callback_data='crypto_options')],
        [InlineKeyboardButton("📊 My Credits", callback_data='check_credits')],
        [InlineKeyboardButton("📜 Payment Terms", callback_data='payment_tos')]
    ]
    
    crypto_options = "\n".join([f"• {n.upper()}: <code>{a}</code>" for n,a in PAYMENT_ADDRESSES.items()])
    
    await update.message.reply_text(
        f"💳 <b>Payment Plans</b>\n\n"
        f"<u>Telegram Stars</u>\n"
        f"• 1 Ad = 100 Stars\n"
        f"• Unlimited Monthly = 2000 Stars\n\n"
        f"<u>Crypto Payments</u>\n{crypto_options}\n\n"
        f"📌 All payments require verification",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Payment processor"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'pay_single_stars':
        await stars_payment_flow(query, 100, "Single Ad")
    elif query.data == 'pay_monthly_stars':
        await stars_payment_flow(query, 2000, "Monthly Plan")
    elif query.data == 'crypto_options':
        await show_crypto_menu(query)

async def stars_payment_flow(query, amount, plan_name):
    """Stars payment instructions"""
    await query.edit_message_text(
        f"⭐ <b>{plan_name} - {amount} Stars</b>\n\n"
        f"1. Send <b>{amount} Stars</b> to @{SUPPORT_USERNAME[1:]}\n"
        f"2. Forward receipt here with:\n"
        f"<code>/payment {amount} stars [TX_HASH]</code>\n\n"
        f"📌 Include memo: <code>user:{query.from_user.id}</code>",
        parse_mode='HTML'
    )

async def show_crypto_menu(query):
    """Crypto currency selection"""
    keyboard = [
        [InlineKeyboardButton("USDT (TRC20)", callback_data='crypto_usdt_trx'),
         InlineKeyboardButton("TON", callback_data='crypto_ton')],
        [InlineKeyboardButton("« Back", callback_data='back_to_pricing')]
    ]
    
    await query.edit_message_text(
        "💎 <b>Select Cryptocurrency</b>\n\n"
        "All payments require memo with your User ID",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def handle_crypto_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Crypto payment processor"""
    query = update.callback_query
    await query.answer()
    
    currency = query.data.replace('crypto_', '').upper()
    address = PAYMENT_ADDRESSES.get(query.data.replace('crypto_', ''), "N/A")
    
    await query.edit_message_text(
        f"💳 <b>Pay with {currency}</b>\n\n"
        f"<b>Address</b>:\n<code>{address}</code>\n\n"
        f"<b>Required Memo</b>:\n<code>user:{query.from_user.id}</code>\n\n"
        f"After payment, send:\n"
        f"1. Screenshot\n2. TX Hash\n"
        f"to @{SUPPORT_USERNAME}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("« Back", callback_data='crypto_options')
        ]]),
        parse_mode='HTML'
    )

# ===== PAYMENT VERIFICATION =====
async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Secure payment verification"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🔒 Admin only!")
        return
    
    try:
        user_id = int(context.args[0])
        amount = float(context.args[1])
        currency = context.args[2].lower()
        tx_hash = context.args[3] if len(context.args) > 3 else "MANUAL"
        
        conn = sqlite3.connect('promotion_bot.db')
        cursor = conn.cursor()
        
        # Encrypt sensitive data
        encrypted_amount = encrypt_data(str(amount))
        encrypted_tx = encrypt_data(tx_hash)
        
        # Process payment
        if currency == "stars":
            if amount == 100:
                cursor.execute('''
                    UPDATE users SET ad_credits = ad_credits + 1 
                    WHERE user_id = ?
                ''', (user_id,))
                msg = "➕ 1 ad credit added"
            elif amount >= 2000:
                expiry = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                cursor.execute('''
                    INSERT OR REPLACE INTO users 
                    (user_id, premium_expiry) VALUES (?, ?)
                ''', (user_id, expiry))
                msg = "🎉 Monthly subscription activated!"
        else:  # Crypto
            rate = get_crypto_rate(currency)  # Implement your rate API
            credits = int(amount * rate)
            cursor.execute('''
                UPDATE users SET ad_credits = ad_credits + ?
                WHERE user_id = ?
            ''', (credits, user_id))
            msg = f"➕ {credits} ad credits added"
        
        # Record payment (with encrypted data)
        cursor.execute('''
            INSERT INTO payments 
            (user_id, encrypted_amount, currency, encrypted_tx, status)
            VALUES (?, ?, ?, ?, 'verified')
        ''', (user_id, encrypted_amount, currency, encrypted_tx))
        
        conn.commit()
        conn.close()
        
        # Notify user
        await context.bot.send_message(
            chat_id=user_id,
            text=f"💳 <b>Payment Verified</b>\n\n"
                 f"• Amount: {amount} {currency.upper()}\n"
                 f"• Status: {msg}\n"
                 f"• TX: {tx_hash[:10]}...",
            parse_mode='HTML'
        )
        
        await update.message.reply_text(
            f"✅ Payment processed\n{msg}\nUser: {user_id}",
            reply_to_message_id=update.message.reply_to_message.message_id
        )
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: {str(e)}\n"
            f"Usage: /verify USER_ID AMOUNT CURRENCY [TX_HASH]"
        )

# ===== AD MANAGEMENT =====
async def submit_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Secure ad submission"""
    user_id = update.effective_user.id
    content = update.message.text
    
    conn = sqlite3.connect('promotion_bot.db')
    cursor = conn.cursor()
    
    # Check credentials
    cursor.execute('''
        SELECT ad_credits, premium_expiry FROM users 
        WHERE user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    
    if not result or (result[0] <= 0 and not (
        result[1] and datetime.strptime(result[1], '%Y-%m-%d') > datetime.now()
    )):
        await update.message.reply_text(
            "❌ No ad credits available!\n"
            "Get credits via /pricing",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Buy Now", callback_data='pricing')
            ]])
        )
        return
    
    # Deduct credit if not premium
    if not (result[1] and datetime.strptime(result[1], '%Y-%m-%d') > datetime.now()):
        cursor.execute('''
            UPDATE users SET ad_credits = ad_credits - 1 
            WHERE user_id = ?
        ''', (user_id,))
    
    # Store encrypted ad
    encrypted_content = encrypt_data(content)
    cursor.execute('''
        INSERT INTO ads (user_id, encrypted_content, status)
        VALUES (?, ?, 'pending')
    ''', (user_id, encrypted_content))
    
    conn.commit()
    conn.close()
    
    # Notify admin
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📨 New Ad from @{update.effective_user.username}:\n\n"
             f"{content}\n\n"
             f"Approve: /approve {cursor.lastrowid}\n"
             f"Reject: /reject {cursor.lastrowid}"
    )
    
    await update.message.reply_text("✅ Ad submitted for approval!")

# ===== PROMOTION FEATURES =====
async def invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Referral system with rewards"""
    user_id = update.effective_user.id
    ref_link = f"https://t.me/{(await context.bot.get_me()).username}?start=ref={user_id}"
    
    conn = sqlite3.connect('promotion_bot.db')
    cursor = conn.cursor()
    
    # Check if new user came via referral
    if context.args and context.args[0].startswith('ref='):
        referrer_id = int(context.args[0][4:])
        cursor.execute('''
            UPDATE users SET invite_count = invite_count + 1 
            WHERE user_id = ?
        ''', (referrer_id,))
        
        # Reward every 3 invites
        cursor.execute('SELECT invite_count FROM users WHERE user_id = ?', (referrer_id,))
        count = cursor.fetchone()[0]
        if count % 3 == 0:
            cursor.execute('''
                UPDATE users SET ad_credits = ad_credits + 1 
                WHERE user_id = ?
            ''', (referrer_id,))
            await context.bot.send_message(
                chat_id=referrer_id,
                text="🎉 You earned +1 ad credit from referrals!"
            )
        conn.commit()
    
    await update.message.reply_text(
        f"📢 <b>Earn Free Credits!</b>\n\n"
        f"Share your link:\n<code>{ref_link}</code>\n\n"
        f"• Get +1 credit every 3 friends\n"
        f"• Friends get 5% discount",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Share", switch_inline_query="Join for exclusive ads!")
        ]]),
        parse_mode='HTML'
    )
    conn.close()

# ===== AUTOMATION =====
async def auto_post_ads(context: ContextTypes.DEFAULT_TYPE):
    """Scheduled ad posting"""
    conn = sqlite3.connect('promotion_bot.db')
    cursor = conn.cursor()
    
    # Get approved ads
    cursor.execute('''
        SELECT ad_id, user_id, encrypted_content 
        FROM ads 
        WHERE status='approved' 
        AND timestamp > datetime('now','-1 day')
        ORDER BY RANDOM() 
        LIMIT 10
    ''')
    
    for ad in cursor.fetchall():
        try:
            content = decrypt_data(ad[2])
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=f"📢 Promoted Ad:\n\n{content}\n\n"
                     f"👤 User ID: {ad[1]}\n"
                     f"🔄 Views: {ad[3] if len(ad) > 3 else 0}"
            )
            # Update view count
            cursor.execute('''
                UPDATE ads SET views = views + 1 
                WHERE ad_id = ?
            ''', (ad[0],))
            time.sleep(5)  # Rate limit
        except Exception as e:
            print(f"Failed to post ad {ad[0]}: {e}")
    
    conn.commit()
    conn.close()

# ===== MAIN SETUP =====
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Core commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tos", tos))
    app.add_handler(CommandHandler("help", help))
    
    # Payment system
    app.add_handler(CommandHandler("pricing", pricing))
    app.add_handler(CommandHandler("verify", verify_payment))
    app.add_handler(CallbackQueryHandler(handle_payment, pattern='^pay_'))
    app.add_handler(CallbackQueryHandler(handle_crypto_payment, pattern='^crypto_'))
    app.add_handler(CallbackQueryHandler(pricing, pattern='^back_to_pricing'))
    
    # Ad management
    app.add_handler(CommandHandler("submit", submit_ad))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, submit_ad))
    
    # Promotion
    app.add_handler(CommandHandler("invite", invite))
    
    # Scheduling
    job_queue = app.job_queue
    job_queue.run_daily(
        callback=auto_post_ads,
        time=datetime.time(hour=12, minute=0),  # 12 PM UTC
        days=(0, 1, 2, 3, 4, 5, 6)  # Daily
    )
    
    print("🚀 Bot is running with all features...")
    app.run_polling()

if __name__ == "__main__":
    main()
