import os
import time
import requests
import platform
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler
from threading import Thread, Lock
from datetime import datetime
import logging

# Configuration
BOT_TOKEN = "8207995879:AAG1aTPtDViqtsA5VCex9B8gKrgrvigvo3s"
BSC_ADDRESS = "0xa3512bd47d64fda7ad9160a259f1cf95e35d0f61"
API_URL = f"https://api.bscscan.com/api?module=account&action=tokentx&address={BSC_ADDRESS}&sort=desc&apikey=5MY25WCXQD2YKDNJCJD1GYXH6C7EC63MBV"
CHECK_INTERVAL = 1  # 1 second interval
ADMIN_USERNAME = "choexo_ze"  # Only this admin can activate monitoring

# Global variables with thread safety
last_tx_hash = None
active_chats = set()
data_lock = Lock()

# Enhanced logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize bot
bot = Bot(token=BOT_TOKEN)

def clear_console():
    """Clear console based on the operating system"""
    if platform.system() == "Windows":
        os.system('cls')
    else:
        os.system('clear')

def is_admin(update: Update):
    """Check if the user is the authorized admin"""
    user = update.effective_user
    return user.username and user.username.lower() == ADMIN_USERNAME.lower()

def get_transactions():
    """Fetch recent transactions from BSCScan API"""
    try:
        response = requests.get(API_URL, timeout=5)
        data = response.json()
        if data['status'] == '1' and data['message'] == 'OK':
            return data['result']
        return []
    except requests.exceptions.RequestException as e:
        logger.warning(f"Failed to fetch transactions: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching transactions: {e}")
        return []

def detect_transaction_type(tx):
    """Determine transaction type with improved logic"""
    value = int(tx['value'])
    amount = value / 10**18  # Assuming 18 decimal places
    
    if tx['to'].lower() == BSC_ADDRESS.lower():
        return "Investment"
    elif tx['from'].lower() == BSC_ADDRESS.lower():
        if amount >= 100:  # Large amount considered as withdrawal
            return "Capital Withdrawal"
        elif "referral" in tx.get('input', '').lower():
            return "Referral Reward"
        else:
            return "Staking Reward"
    return "Other Transaction"

def format_message(tx):
    """Format notification message in English"""
    tx_type = detect_transaction_type(tx)
    amount = int(tx['value']) / 10**18
    timestamp = datetime.fromtimestamp(int(tx['timeStamp'])).strftime('%Y-%m-%d %H:%M:%S')
    
    message = (
        "✅ Transaction Detected!\n"
        f"📊 Type: {tx_type}\n"
        f"📌 From: {tx['from'][:6]}...{tx['from'][-4:]}\n"
        f"💰 Amount: {amount:.2f} USDT\n"
        f"⏰ Time: {timestamp}"
    )
    
    return message

def create_keyboard(tx_hash):
    """Create inline keyboard with English buttons"""
    keyboard = [
        [
            InlineKeyboardButton("🔍 View Transaction", url=f"https://bscscan.com/tx/{tx_hash}"),
        ],
        [
            InlineKeyboardButton("📲 Register Now", url="https://t.me/ClusterYieldBot?start=welcome"),
            InlineKeyboardButton("📢 Info Channel", url="https://t.me/ClusterYieldOfficial"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def send_transaction_notification(chat_id, tx):
    """Send notification to Telegram group and clear console"""
    global last_tx_hash
    
    tx_hash = tx['hash']
    
    with data_lock:
        if tx_hash == last_tx_hash:
            return False
        last_tx_hash = tx_hash
    
    message = format_message(tx)
    keyboard = create_keyboard(tx_hash)
    gif_url = "https://files.catbox.moe/alapau.mp4"
    
    try:
        bot.send_animation(
            chat_id=chat_id,
            animation=gif_url,
            caption=message,
            reply_markup=keyboard
        )
        clear_console()  # Clear console after successful notification
        logger.info(f"Notification sent to chat {chat_id} for tx {tx_hash[:10]}...")
        return True
    except Exception as e:
        logger.error(f"Failed to send notification to {chat_id}: {e}")
        return False

def monitor_transactions(context: CallbackContext):
    """Main monitoring loop with error handling"""
    logger.info("Starting transaction monitor...")
    error_count = 0
    
    while True:
        try:
            transactions = get_transactions()
            if transactions:
                latest_tx = transactions[0]
                
                with data_lock:
                    current_chats = active_chats.copy()
                
                for chat_id in current_chats:
                    try:
                        send_transaction_notification(chat_id, latest_tx)
                    except Exception as e:
                        logger.error(f"Error processing chat {chat_id}: {e}")
            
            error_count = 0  # Reset error counter on success
            time.sleep(CHECK_INTERVAL)
            
        except Exception as e:
            error_count += 1
            logger.error(f"Monitoring error (attempt {error_count}): {e}")
            
            # Exponential backoff for repeated errors
            sleep_time = min(2 ** error_count, 60)  # Max 60 seconds
            time.sleep(sleep_time)

def start_monitoring(update: Update, context: CallbackContext):
    """Handler for /start and /pro commands - Admin only"""
    if not is_admin(update):
        update.message.reply_text("⛔ Command restricted to admin only.")
        logger.warning(f"Unauthorized access attempt by {update.effective_user.username}")
        return
    
    chat_id = update.effective_chat.id
    with data_lock:
        if chat_id not in active_chats:
            active_chats.add(chat_id)
            update.message.reply_text("✅ Bot activated! Now monitoring transactions in real-time (1 second interval).")
            logger.info(f"Added chat {chat_id} to monitoring by admin")
        else:
            update.message.reply_text("⚠️ Bot is already monitoring transactions in this group.")

def stop_monitoring(update: Update, context: CallbackContext):
    """Handler for /stop command - Admin only"""
    if not is_admin(update):
        update.message.reply_text("⛔ Command restricted to admin only.")
        logger.warning(f"Unauthorized access attempt by {update.effective_user.username}")
        return
    
    chat_id = update.effective_chat.id
    with data_lock:
        if chat_id in active_chats:
            active_chats.remove(chat_id)
            update.message.reply_text("❌ Monitoring stopped in this group.")
            logger.info(f"Removed chat {chat_id} from monitoring by admin")
        else:
            update.message.reply_text("⚠️ Bot isn't currently monitoring this group.")

def error_handler(update: Update, context: CallbackContext):
    """Global error handler"""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Main application setup"""
    # Configure logging levels
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    # Start monitoring thread
    monitor_thread = Thread(target=monitor_transactions, args=(None,), daemon=True)
    monitor_thread.start()
    
    # Set up Telegram bot
    updater = Updater(token=BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    # Add command handlers
    dispatcher.add_handler(CommandHandler(["start", "pro", "pro_transaksi"], start_monitoring))
    dispatcher.add_handler(CommandHandler("stop", stop_monitoring))
    
    # Add error handler
    dispatcher.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Bot is running...")
    print("Bot is running. Press Ctrl+C to stop.")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()