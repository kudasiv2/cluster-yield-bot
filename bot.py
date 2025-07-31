import os
import time
import asyncio
import requests
from threading import Thread, Lock
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes
)
import logging

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
BSC_ADDRESS = "0xa3512bd47d64fda7ad9160a259f1cf95e35d0f61"
API_URL = f"https://api.bscscan.com/api?module=account&action=tokentx&address={BSC_ADDRESS}&sort=desc&apikey={os.getenv('BSCSCAN_API_KEY')}"
CHECK_INTERVAL = 5  # 5 seconds to avoid rate limits
ADMIN_USERNAME = "choexo_ze"

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TransactionTracker:
    def __init__(self, application):
        self.last_tx = None
        self.active_chats = set()
        self.lock = Lock()
        self.application = application

    def start_monitoring(self):
        Thread(target=self._monitor_loop, daemon=True).start()

    def _monitor_loop(self):
        while True:
            try:
                txns = self._fetch_transactions()
                if txns and txns[0]['hash'] != self.last_tx:
                    self._process_new_transaction(txns[0])
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
            finally:
                time.sleep(CHECK_INTERVAL)

    def _fetch_transactions(self):
        try:
            response = requests.get(API_URL, timeout=10)
            return response.json().get('result', [])
        except Exception as e:
            logger.error(f"API Error: {e}")
            return []

    def _process_new_transaction(self, tx):
        with self.lock:
            self.last_tx = tx['hash']

        tx_type = self._detect_tx_type(tx)
        amount = int(tx['value']) / 10**18
        time_str = datetime.fromtimestamp(int(tx['timeStamp'])).strftime('%Y-%m-%d %H:%M:%S')

        message = (
            "✅ Transaction Detected!\n"
            f"📊 Type: {tx_type}\n"
            f"📌 From: {tx['from'][:6]}...{tx['from'][-4:]}\n"
            f"💰 Amount: {amount:.2f} USDT\n"
            f"⏰ Time: {time_str}"
        )

        keyboard = [
            [InlineKeyboardButton("🔍 View TX", url=f"https://bscscan.com/tx/{tx['hash']}")],
            [
                InlineKeyboardButton("📲 Register", url="https://t.me/ClusterYieldBot?start=welcome"),
                InlineKeyboardButton("📢 Channel", url="https://t.me/ClusterYieldOfficial")
            ]
        ]

        for chat_id in list(self.active_chats):
            asyncio.run_coroutine_threadsafe(
                self._send_notification(chat_id, message, keyboard),
                self.application.bot.loop
            )

    async def _send_notification(self, chat_id, message, keyboard):
        try:
            await self.application.bot.send_animation(
                chat_id=chat_id,
                animation="https://files.catbox.moe/alapau.mp4",
                caption=message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Failed to send to {chat_id}: {e}")

    def _detect_tx_type(self, tx):
        if tx['to'].lower() == BSC_ADDRESS.lower():
            return "Investment"
        elif tx['from'].lower() == BSC_ADDRESS.lower():
            if int(tx['value']) / 10**18 >= 100:
                return "Capital Withdrawal"
            elif "referral" in tx.get('input', '').lower():
                return "Referral Reward"
            return "Staking Reward"
        return "Other"

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        await update.message.reply_text("⛔ Command restricted to admin only.")
        return
    
    chat_id = update.effective_chat.id
    tracker.active_chats.add(chat_id)
    await update.message.reply_text("✅ Bot activated! Monitoring transactions.")

async def handle_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        await update.message.reply_text("⛔ Command restricted to admin only.")
        return
    
    chat_id = update.effective_chat.id
    tracker.active_chats.discard(chat_id)
    await update.message.reply_text("❌ Monitoring stopped in this group.")

async def post_init(application: Application):
    global tracker
    tracker = TransactionTracker(application)
    tracker.start_monitoring()

def main():
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("pro", handle_start))
    application.add_handler(CommandHandler("pro_transaksi", handle_start))
    application.add_handler(CommandHandler("stop", handle_stop))
    
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == '__main__':
    main()
