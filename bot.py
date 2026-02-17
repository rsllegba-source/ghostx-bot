import os
import re
from datetime import datetime, timedelta
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

PROMO_CODE = "SXM229"

user_data = {}

def get_user(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            "history": [],
            "last_signal": None
        }
    return user_data[user_id]

def parse_numbers(text):
    text = text.lower().replace("x", "").replace(",", ".")
    return [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)]

def check_strategies(history):
    signals = []
    if len(history) < 3:
        return signals

    last = history[-1]
    prev = history[-2]
    prev2 = history[-3]

    if prev >= 3 and last >= 3:
        signals.append("Deux cotes 3+ détectées")

    if prev2 < 1.5 and prev < 1.5 and last < 1.5:
        signals.append("Trois cotes <1.50 détectées")

    return signals

def generate_signal():
    now = datetime.now()
    start = now + timedelta(minutes=5)
    end = start + timedelta(seconds=60)
    entry = start + timedelta(seconds=30)

    return start, end, entry

markup = ReplyKeyboardMarkup(resize_keyboard=True)
markup.row("🚀 SIGNAL")

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "Bienvenue sur GHOSTX BOT 💀👿\n\n"
        "Envoie 10 à 20 dernières cotes pour commencer.",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "🚀 SIGNAL")
def manual_signal(message):
    start, end, entry = generate_signal()
    bot.send_message(
        message.chat.id,
        f"🚀 PRÉDICTION META CRASH\n\n"
        f"📅 Créneau: {start.strftime('%H:%M:%S')} - {end.strftime('%H:%M:%S')}\n"
        f"⏱️ Joue à: {entry.strftime('%H:%M:%S')}\n"
        f"🎯 Objectif: 3.00X\n"
        f"🛡️ Sécurité: 1.50X\n\n"
        f"🎁 Code promo: {PROMO_CODE}"
    )

@bot.message_handler(func=lambda message: True)
def receive_cotes(message):
    user = get_user(message.from_user.id)
    numbers = parse_numbers(message.text)

    if not numbers:
        return

    user["history"].extend(numbers)
    user["history"] = user["history"][-50:]

    signals = check_strategies(user["history"])

    if signals:
        start, end, entry = generate_signal()
        bot.send_message(
            message.chat.id,
            f"🚀 SIGNAL AUTOMATIQUE\n\n"
            f"📅 Créneau: {start.strftime('%H:%M:%S')} - {end.strftime('%H:%M:%S')}\n"
            f"⏱️ Joue à: {entry.strftime('%H:%M:%S')}\n"
            f"🎯 Objectif: 3.00X\n"
            f"🛡️ Sécurité: 1.50X\n\n"
            f"🎁 Code promo: {PROMO_CODE}"
        )

bot.infinity_polling()
