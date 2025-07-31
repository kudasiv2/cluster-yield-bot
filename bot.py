import os
import time
import requests
import logging
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext
from threading import Thread, Lock
from datetime import datetime

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
BSC_ADDRESS = "0xa3512bd47d64fda7ad9160a259f1cf95e35d0f61"
API_URL = f"https://api.bscscan.com/api?module=account&action=tokentx&address={BSC_ADDRESS}&sort=desc&apikey={os.getenv('BSCSCAN_API_KEY')}"
CHECK_INTERVAL = 1  # 1 second check
ADMIN_USERNAME = "choexo_ze"  # Case-sensitive

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TransactionTracker:
    def __init__(self):
        self.last_tx = None
        self.active_chats = set()
        self.lock = Lock()
        self.bot = Bot(token=BOT_TOKEN)

    def track_transactions(self):
        while True:
            try:
                txns = self._fetch_transactions()
                if txns and txns[0]['hash'] != self.last_tx:
                    self._process_new_transaction(txns[0])
                time.sleep(CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"Tracking error: {e}")
                time.sleep(5)

    def _fetch_transactions(self):
        try:
            res = requests.get(API_URL, timeout=10)
            return res.json().get('result', [])
        except Exception as e:
            logger.error(f"API Error: {e}")
            return []

    def _process_new_transaction(self, tx):
        with self.lock:
            self.last_tx = tx['hash']
            
        tx_type = self._determine_tx_type(tx)
        amount = int(tx['value']) / 10**18
        time_str = datetime.fromtimestamp(int(tx['timeStamp'])).strftime('%Y-%m-%d %H:%M:%S')
        
        message = (
            "✅ Transaction Detected!\n"
            f"📊 Type: {tx_type}\n"
            f"📌 From: {tx['from'][:6]}...{tx['from'][-4:]}\n"
            f"💰 Amount: {amount:.2f} USDT\n"
            f"⏰ Time: {time_str}"
        )
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 View Transaction", url=f"https://bscscan.com/tx/{tx['hash']}")],
            [
                InlineKeyboardButton("📲 Register Now", url="https://t.me/ClusterYieldBot?start=welcome"),
                InlineKeyboardButton("📢 Info Channel", url="https://t.me/ClusterYieldOfficial")
            ]
        ])
        
        for chat_id in list(self.active_chats):
            try:
                self.bot.send_animation(
                    chat_id=chat_id,
                    animation="https://files.catbox.moe/alapau.mp4",
                    caption=message,
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Failed to notify {chat_id}: {e}")

    def _determine_tx_type(self, tx):
        if tx['to'].lower() == BSC_ADDRESS.lower():
            return "Investment"
        elif tx['from'].lower() == BSC_ADDRESS.lower():
            if int(tx['value']) / 10**18 >= 100:
                return "Capital Withdrawal"
            elif "referral" in tx.get('input', '').lower():
                return "Referral Reward"
            return "Staking Reward"
        return "Other"

def handle_start(update: Update, context: CallbackContext):
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        update.message.reply_text("⛔ Command restricted to admin only.")
        return
    
    chat_id = update.effective_chat.id
    tracker.active_chats.add(chat_id)
    update.message.reply_text("✅ Bot activated! Monitoring transactions every second.")

def handle_stop(update: Update, context: CallbackContext):
    user = update.effective_user
    if user.username != ADMIN_USERNAME:
        update.message.reply_text("⛔ Command restricted to admin only.")
        return
    
    chat_id = update.effective_chat.id
    tracker.active_chats.discard(chat_id)
    update.message.reply_text("❌ Monitoring stopped in this group.")

if __name__ == '__main__':
    tracker = TransactionTracker()
    Thread(target=tracker.track_transactions, daemon=True).start()
    
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher
    
    dispatcher.add_handler(CommandHandler(["start", "pro", "pro_transaksi"], handle_start))
    dispatcher.add_handler(CommandHandler("stop", handle_stop))
    
    logger.info("Bot starting...")
    updater.start_polling()
    updater.idle()
