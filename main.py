
import os, json, random, logging, time as time_mod
from datetime import time
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# -------- Config --------
BOT_NAME = "Wch ntyb / وش نطيب🍲"
TOKEN = "8313158504:AAHVG1csPCvUto6Cn3rbzAHUO4oI0bpYUOk"
TZ = ZoneInfo("Africa/Algiers")
DATA_PATH = "recipes.json"
STATE_FILE = "state.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# Ensure randomness across sessions
random.seed(time_mod.time())

def load_json(path, fallback):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.warning("Failed to load %s: %s", path, e)
    return fallback

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

RECIPES = load_json(DATA_PATH, [])
STATE = load_json(STATE_FILE, {"lang": {}, "subs": []})
LAST_SENT = {}

def choose(lang: str, chat_id=None):
    pool = [r for r in RECIPES if r.get("lang") == lang] or RECIPES
    if not pool:
        return None
    last_title = LAST_SENT.get(chat_id)
    candidates = [r for r in pool if r.get("title") != last_title] or pool
    chosen = random.choice(candidates)
    if chat_id:
        LAST_SENT[chat_id] = chosen.get("title")
    return chosen

def fmt_recipe(r: dict):
    if not r:
        return "😕 Aucune recette disponible."
    lines = [f"🍽️ *{r.get('title','Recette')}*", f"⏱️ {r.get('time','--')} | 🍴 {r.get('serves','--')}"]
    if r.get("region"): lines.append(f"📍 {r['region']}")
    lines.append("\n🥕 Ingrédients:")
    for ing in r.get("ingredients", []): lines.append(f"- {ing}")
    lines.append("\n🔥 Étapes:")
    for i, s in enumerate(r.get("steps", []), 1): lines.append(f"{i}️⃣ {s}")
    if r.get("tip"): lines.append("\n💡 Astuce: " + r["tip"])
    return "\n".join(lines)

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🇩🇿 Darja", callback_data="lang:dz"),
        InlineKeyboardButton("🇫🇷 Français", callback_data="lang:fr")
    ]])
    txt = "Salam! Chkoune j3an? 😋 Voici ton idée de recette du jour!\nChoisis ta langue:"
    await u.message.reply_text(txt, reply_markup=kb, parse_mode="Markdown")

async def lang_button(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    l = q.data.split(":")[1]
    cid = str(q.message.chat.id)
    STATE["lang"][cid] = l
    save_json(STATE_FILE, STATE)
    await q.edit_message_text("Langue changée 🇫🇷" if l == "fr" else "Lougha tbadlet 🇩🇿")

async def today(u: Update, c: ContextTypes.DEFAULT_TYPE):
    cid = str(u.effective_chat.id)
    lang = STATE["lang"].get(cid, "fr")
    r = choose(lang, cid)
    msg = fmt_recipe(r)
    photo = r.get("photo") if r else None
    if photo and os.path.exists(photo):
        await u.message.reply_photo(InputFile(photo), caption=msg, parse_mode="Markdown")
    else:
        await u.message.reply_text(msg, parse_mode="Markdown")

async def categories(u: Update, c: ContextTypes.DEFAULT_TYPE):
    cats = sorted({x for r in RECIPES for x in r.get("tags", [])})
    if not cats:
        await u.message.reply_text("Aucune catégorie trouvée.")
        return
    buttons = [[InlineKeyboardButton(x, callback_data=f"cat:{x}")] for x in cats]
    await u.message.reply_text("📚 Choisis une catégorie :", reply_markup=InlineKeyboardMarkup(buttons))

async def cat_button(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    cat = q.data.split(":")[1]
    lang = STATE["lang"].get(str(q.message.chat.id), "fr")
    recipes = [r for r in RECIPES if cat in r.get("tags", []) and (r.get("lang")==lang or lang in ("fr","dz"))]
    if not recipes:
        await q.edit_message_text(f"Aucune recette trouvée pour « {cat} ».")
        return
    import random as _rnd
    r = _rnd.choice(recipes)
    await q.edit_message_text(f"🍲 Catégorie: *{cat}*\n\n{fmt_recipe(r)}", parse_mode="Markdown")

async def random_recipe(u: Update, c: ContextTypes.DEFAULT_TYPE):
    cid = str(u.effective_chat.id)
    lang = STATE["lang"].get(cid, "fr")
    r = choose(lang, cid)
    await u.message.reply_text(fmt_recipe(r), parse_mode="Markdown")

async def subscribe(u: Update, c: ContextTypes.DEFAULT_TYPE):
    cid = u.effective_chat.id
    if cid not in STATE["subs"]:
        STATE["subs"].append(cid)
        save_json(STATE_FILE, STATE)
    await u.message.reply_text("✅ Abonné aux recettes quotidiennes!")

async def unsubscribe(u: Update, c: ContextTypes.DEFAULT_TYPE):
    cid = u.effective_chat.id
    if cid in STATE["subs"]:
        STATE["subs"].remove(cid)
        save_json(STATE_FILE, STATE)
    await u.message.reply_text("❌ Désabonné.")

async def help_cmd(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("Commandes:\n/start\n/today\n/random\n/categories\n/subscribe\n/unsubscribe")

async def daily(ctx):
    for cid in list(STATE.get("subs", [])):
        try:
            lang = STATE["lang"].get(str(cid), "fr")
            r = choose(lang, cid)
            await ctx.bot.send_message(cid, fmt_recipe(r), parse_mode="Markdown")
        except Exception as e:
            logging.warning("Failed to send daily to %s: %s", cid, e)

async def post_init(application: Application) -> None:
    commands = [
        BotCommand("start", "Choose language 🇩🇿/🇫🇷"),
        BotCommand("today", "Get today's recipe"),
        BotCommand("random", "Random Algerian recipe"),
        BotCommand("categories", "Browse recipe tags"),
        BotCommand("subscribe", "Daily recipes at 9 AM"),
        BotCommand("unsubscribe", "Stop daily recipes"),
        BotCommand("help", "Help / Aide")
    ]
    await application.bot.set_my_commands(commands)

def main():
    if not TOKEN or TOKEN == "REPLACE_WITH_YOUR_TOKEN":
        print("⚠️ TOKEN missing.")
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(lang_button, pattern="^lang:"))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("categories", categories))
    app.add_handler(CallbackQueryHandler(cat_button, pattern="^cat:"))
    app.add_handler(CommandHandler("random", random_recipe))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("help", help_cmd))
    app.job_queue.run_daily(daily, time=time(hour=9, tzinfo=TZ))
    print(f"{BOT_NAME} running…")
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
