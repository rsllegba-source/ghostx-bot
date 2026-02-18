import os
import re
import time
import threading
from datetime import datetime, timedelta

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not TOKEN or ":" not in TOKEN:
    raise ValueError("BOT_TOKEN manquant/invalide. Fais: export BOT_TOKEN='123:ABC...'")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

VIDEO_PATH = "metacrash.mp4"     # optionnel (si présent, envoyé 1 fois)
COOLDOWN_SECONDS = 120           # anti-spam
LOADING_SECONDS = 2              # 2 ou 3
PROMO_CODE = "SXM229"
SIGNUP_LINK = "https://1w.run/?p=gByP"

import os
import time
import threading
from datetime import datetime, timedelta

import telebot
from telebot.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not TOKEN or ":" not in TOKEN:
    raise ValueError("BOT_TOKEN manquant/invalide. Fais: export BOT_TOKEN='123:ABC...'")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

VIDEO_PATH = "metacrash.mp4"   # optionnel: animation vidéo (mets-la dans le même dossier que bot.py)
COOLDOWN_SECONDS = 120         # anti-spam
LOADING_SECONDS = 2            # 2 ou 3 secondes

PROMO_CODE = "SXM229"
SIGNUP_LINK = "https://1w.run/?p=gByP"

# =========================
# STATE (RAM)
# =========================
user_state = {}           # user_id -> "WAIT_DATA" / None
user_data = {}            # user_id -> {"odds":[...], "game_time":"HH:MM:SS", "computed": {...}}
user_last_signal = {}     # user_id -> datetime
user_pending_timer = {}   # user_id -> bool (évite multi timers)

# =========================
# UI
# =========================
def kb_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📝 ENTRER CÔTES"))
    kb.row(KeyboardButton("📡 SIGNAL"), KeyboardButton("ℹ️ COMMENT ÇA MARCHE"))
    return kb

def kb_signal_only():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📡 SIGNAL"))
    kb.row(KeyboardButton("ℹ️ COMMENT ÇA MARCHE"))
    return kb

def signup_button():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ S’INSCRIRE (1win)", url=SIGNUP_LINK))
    return kb

# =========================
# STRATEGY HELPERS
# =========================
def parse_odds_line(line: str):
    """
    Ligne 1: 10 cotes séparées par espace ou virgule.
    Exemple:
    1.12 2.45 1.05 ... 2.75
    ou
    1.12,2.45,1.05,...,2.75
    """
    s = line.replace(",", " ").strip()
    parts = [p for p in s.split() if p]
    if len(parts) != 10:
        return None
    odds = []
    try:
        for p in parts:
            odds.append(float(p))
    except:
        return None
    return odds

def is_time_hhmmss(s: str):
    try:
        datetime.strptime(s.strip(), "%H:%M:%S")
        return True
    except:
        return False

def last_digit_of_cents(x: float) -> int:
    """
    Dernier chiffre (centièmes) comme tes exemples :
    4.43 -> 3
    5.32 -> 2
    1.16 -> 6
    4.37 -> 7
    """
    txt = f"{x:.2f}"
    return int(txt[-1])

def digits_are_consecutive(a: int, b: int) -> bool:
    # suit montant ou descendant (3->2 OK ; 6->7 OK)
    # seulement 1..9 (évite 0)
    if not (1 <= a <= 9 and 1 <= b <= 9):
        return False
    return abs(a - b) == 1

def compute_strategy(odds):
    """
    Applique EXACTEMENT TES 3 règles. Aucun hasard.
    Retour: dict {has_signal, reason, objective, safety}
    """
    # 🩵 R2: deux cotes (3+) se suivent -> objectif 1.50
    if odds[-2] >= 3.0 and odds[-1] >= 3.0:
        return {
            "has_signal": True,
            "reason": "Deux cotes (3+) consécutives → objectif 1.50X",
            "objective": 1.50,
            "safety": 1.20
        }

    # 🩵 R3: trois cotes < 1.50 se suivent -> objectif 2.00
    if odds[-3] < 1.50 and odds[-2] < 1.50 and odds[-1] < 1.50:
        return {
            "has_signal": True,
            "reason": "Trois cotes < 1.50 consécutives → objectif 2.00X",
            "objective": 2.00,
            "safety": 1.30
        }

    # 💙 R1: dernier chiffre des 2 dernières cotes se suivent -> 2+
    d1 = last_digit_of_cents(odds[-2])
    d2 = last_digit_of_cents(odds[-1])
    if digits_are_consecutive(d1, d2):
        return {
            "has_signal": True,
            "reason": f"Derniers chiffres consécutifs ({d1}→{d2}) → objectif 2.00X (2+)",
            "objective": 2.00,
            "safety": 1.30
        }

    return {
        "has_signal": False,
        "reason": "Aucune de tes 3 conditions n’est validée sur ces 10 dernières côtes."
    }

def build_slot_from_game_time(game_time_str: str):
    """
    Créneau synchronisé sur l'heure du jeu fournie:
    play_at = time du jeu + 7 secondes
    end_at  = play_at + 60 secondes
    """
    t = datetime.strptime(game_time_str.strip(), "%H:%M:%S")
    play_at = t + timedelta(seconds=7)
    end_at = play_at + timedelta(seconds=60)
    return play_at.strftime("%H:%M:%S"), end_at.strftime("%H:%M:%S")

# =========================
# OUTPUT
# =========================
def send_animation(user_id):
    if os.path.exists(VIDEO_PATH):
        try:
            with open(VIDEO_PATH, "rb") as f:
                bot.send_video(user_id, f, caption="⏳ <b>ATTENTE DU PROCHAIN TOUR...</b>")
                return
        except:
            pass
    bot.send_message(user_id, "⏳ <b>ATTENTE DU PROCHAIN TOUR...</b>")

def format_prediction_message(pred, slot_start, slot_end):
    return (
        "🚀 <b>PRÉDICTION META CRASH</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>CRÉNEAU</b> : {slot_start} - {slot_end}\n"
        f"📈 <b>OBJECTIF</b> : {pred['objective']:.2f}X\n"
        f"🛡 <b>SÉCURITÉ</b> : {pred['safety']:.2f}X\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🎁 <b>CODE</b> : {PROMO_CODE}\n"
        f"🔗 {SIGNUP_LINK}"
    )

# =========================
# CORE FLOW
# =========================
def really_send_prediction(user_id):
    data = user_data.get(user_id)
    if not data:
        bot.send_message(user_id, "❌ Données manquantes. Clique sur 📝 ENTRER CÔTES.", reply_markup=kb_menu())
        return

    pred = data["computed"]
    if not pred.get("has_signal"):
        bot.send_message(user_id, "❌ <b>AUCUN SIGNAL</b>\n" + pred.get("reason", ""), reply_markup=kb_menu())
        return

    bot.send_message(user_id, "🔍 Analyse avancée en cours...")
    send_animation(user_id)
    time.sleep(LOADING_SECONDS)

    slot_start, slot_end = build_slot_from_game_time(data["game_time"])

    bot.send_message(user_id, f"✅ Règle détectée : <b>{pred['reason']}</b>")
    bot.send_message(
        user_id,
        format_prediction_message(pred, slot_start, slot_end),
        reply_markup=signup_button()  # ✅ bouton cliquable
    )
    # On renvoie le menu juste après (car inline + reply ne se mixent pas sur le même message)
    bot.send_message(user_id, "📌 Menu :", reply_markup=kb_menu())

    user_last_signal[user_id] = datetime.now()
    user_pending_timer[user_id] = False

def schedule_after(wait_seconds, user_id):
    def run():
        time.sleep(wait_seconds)
        really_send_prediction(user_id)
    threading.Thread(target=run, daemon=True).start()

# =========================
# HANDLERS
# =========================
@bot.message_handler(commands=["start"])
def start_cmd(message):
    user_id = message.chat.id
    user_state[user_id] = "WAIT_DATA"
    bot.send_message(
        user_id,
        "👻 <b>METAPHANTOM • META CRASH</b>\n\n"
        "1) Clique sur <b>📝 ENTRER CÔTES</b>\n"
        "2) Envoie 10 dernières côtes + time du jeu\n"
        "3) Clique sur <b>📡 SIGNAL</b> pour voir la prédiction",
        reply_markup=kb_menu()
    )

@bot.message_handler(func=lambda m: m.text == "ℹ️ COMMENT ÇA MARCHE")
def how_it_works(message):
    bot.send_message(
        message.chat.id,
        "📊 <b>COMMENT ÇA MARCHE / SYNCHRONISATION</b>\n\n"
        "✅ Le bot n’a pas accès au serveur Meta Crash.\n"
        "✅ La synchronisation se fait à partir des données que TU envoies.\n\n"
        "1️⃣ Tu envoies <b>10 dernières côtes</b>\n"
        "2️⃣ Tu envoies <b>l’heure du jeu</b> (HH:MM:SS) au même moment\n"
        "3️⃣ Le bot applique tes 3 règles (sans hasard)\n"
        "4️⃣ Si une règle est validée → bouton <b>📡 SIGNAL</b>\n"
        "5️⃣ Quand tu cliques SIGNAL → animation + prédiction\n\n"
        "⛔ Anti-spam : 1 signal / 2 minutes.\n"
        "Si tu cliques trop tôt → le bot attend et envoie automatiquement."
    )

@bot.message_handler(func=lambda m: m.text == "📝 ENTRER CÔTES")
def enter_odds(message):
    user_id = message.chat.id
    user_state[user_id] = "WAIT_DATA"
    bot.send_message(
        user_id,
        "📝 Envoie en 2 lignes :\n"
        "1) 10 dernières côtes\n"
        "2) Time du jeu (HH:MM:SS)\n\n"
        "Ex:\n"
        "<code>1.12 2.45 1.05 3.20 1.90 2.10 1.15 4.30 1.01 2.75</code>\n"
        "<code>09:02:23</code>",
        reply_markup=kb_menu()
    )

@bot.message_handler(func=lambda m: m.text == "📡 SIGNAL")
def signal_btn(message):
    user_id = message.chat.id
    now = datetime.now()

    last = user_last_signal.get(user_id)
    if last:
        diff = int((now - last).total_seconds())
        if diff < COOLDOWN_SECONDS:
            wait_time = COOLDOWN_SECONDS - diff
            bot.send_message(
                user_id,
                f"⛔ Attends {wait_time} secondes.\n✅ Je t’envoie le signal automatiquement.",
                reply_markup=kb_menu()
            )
            if not user_pending_timer.get(user_id, False):
                user_pending_timer[user_id] = True
                schedule_after(wait_time, user_id)
            return

    really_send_prediction(user_id)

@bot.message_handler(func=lambda m: True)
def handle_text(message):
    user_id = message.chat.id
    if user_state.get(user_id) != "WAIT_DATA":
        return

    text = (message.text or "").strip()
    lines = text.splitlines()
    if len(lines) < 2:
        bot.send_message(user_id, "❌ Envoie 2 lignes :\n10 cotes\nHH:MM:SS", reply_markup=kb_menu())
        return

    odds = parse_odds_line(lines[0].strip())
    if not odds:
        bot.send_message(user_id, "❌ Ligne 1 : envoie exactement 10 cotes.", reply_markup=kb_menu())
        return

    game_time = lines[1].strip()
    if not is_time_hhmmss(game_time):
        bot.send_message(user_id, "❌ Ligne 2 : format invalide. Exemple: <code>09:02:23</code>", reply_markup=kb_menu())
        return

    computed = compute_strategy(odds)
    user_data[user_id] = {"odds": odds, "game_time": game_time, "computed": computed}
    user_state[user_id] = None

    if not computed.get("has_signal"):
        bot.send_message(user_id, "❌ <b>AUCUN SIGNAL</b>\n" + computed.get("reason", ""), reply_markup=kb_menu())
        return

    bot.send_message(
        user_id,
        "✅ Analyse terminée.\n👉 Clique sur <b>📡 SIGNAL</b> pour voir la prédiction.",
        reply_markup=kb_signal_only()
    )

# =========================
# RUN
# =========================
print("✅ Bot en ligne...")
while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print("Erreur:", e)
        time.sleep(5)
