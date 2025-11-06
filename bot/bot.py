import os, asyncio, logging
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Item, Ad, ServiceOffer
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.helpers import escape_markdown

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED = {u.strip() for u in os.getenv("TELEGRAM_ALLOWED_USER_IDS","").split(",") if u.strip()}
LOG_PATH = os.getenv("BOT_LOG_PATH", "/tmp/localbrain_bot_app.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("localbrain.bot")
SERVICE_CATEGORY_LABELS = {
    'pulizie': 'Pulizie domestiche',
    'babysitter': 'Babysitter',
    'dogsitter': 'Dog sitter',
    'assistenza': 'Assistenza anziani',
    'ripetizioni': 'Ripetizioni',
    'manutenzione': 'Manutenzioni',
    'eventi': 'Supporto eventi',
}


def _escape(text: str) -> str:
    return escape_markdown(text or "", version=2)

def _get_active_ads(db: Session):
    return (
        db.query(Ad)
        .filter(Ad.active == True, Ad.show_in_feed == True)
        .order_by(Ad.created_at.desc())
        .all()
    )

def _interleave_ads(text_items: list[str], ads: list[Ad], every: int = 3) -> list[str]:
    if not ads:
        return text_items
    out: list[str] = []
    ad_idx = 0
    for i, chunk in enumerate(text_items, start=1):
        out.append(chunk)
        if i % every == 0:
            ad = ads[ad_idx % len(ads)]
            out.append(
                f"🔸 *Sponsorizzato*: [{_escape(ad.title)}]({ad.url})\n_{_escape(ad.message)}_\n\n"
            )
            ad_idx += 1
    return out

def check_auth(user_id: int) -> bool:
    if not ALLOWED or str(user_id) in ALLOWED:
        return True
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        logger.warning("Unauthorized start from %s", update.effective_user.id)
        return
    logger.info("Start requested by %s", update.effective_user.id)
    await update.message.reply_text("Benvenuto su LocalBrain — usa /latest per le novità e /cat <categoria>.")

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        logger.warning("Unauthorized latest from %s", update.effective_user.id)
        return
    db: Session = SessionLocal()
    try:
        logger.info("Fetching latest for %s", update.effective_user.id)
        items = db.query(Item).order_by(Item.score.desc(), Item.created_at.desc()).limit(10).all()
        if not items:
            logger.info("No items found for latest request")
            await update.message.reply_text("Nessun elemento al momento. Esegui ingest e riprova.")
            return
        chunks = [
            f"• [{_escape(i.title)}]({i.url})\n_{_escape(i.category)} · {_escape(i.city)}_\n\n"
            for i in items
        ]
        ads = _get_active_ads(db)
        merged = _interleave_ads(chunks, ads, every=3)
        output = "".join(merged)[:3800]
        if not output:
            output = "Nessun elemento al momento."
        logger.info("Sending latest payload (%d chars, ads=%d)", len(output), len(ads))
        await update.message.reply_markdown_v2(output, disable_web_page_preview=True)
    finally:
        db.close()

async def cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        logger.warning("Unauthorized cat from %s", update.effective_user.id)
        return
    if not context.args:
        await update.message.reply_text("Uso: /cat <lavoro|bandi|eventi|annunci|casa>")
        return
    sel = context.args[0]
    db: Session = SessionLocal()
    try:
        logger.info("Fetching cat=%s for %s", sel, update.effective_user.id)
        items = (
            db.query(Item)
            .filter(Item.category == sel)
            .order_by(Item.score.desc(), Item.created_at.desc())
            .limit(10)
            .all()
        )
        if not items:
            logger.info("No items found for category %s", sel)
            await update.message.reply_text(f"Nessun elemento per categoria '{sel}'.")
            return
        chunks = [
            f"• [{_escape(i.title)}]({i.url})\n_{_escape(i.category)} · {_escape(i.city)}_\n\n"
            for i in items
        ]
        ads = _get_active_ads(db)
        merged = _interleave_ads(chunks, ads, every=3)
        output = "".join(merged)[:3800]
        if not output:
            output = f"Nessun elemento per categoria '{_escape(sel)}'."
        logger.info("Sending cat payload (%d chars, ads=%d)", len(output), len(ads))
        await update.message.reply_markdown_v2(output, disable_web_page_preview=True)
    finally:
        db.close()


_format_range = lambda start, end: (f"{start.isoformat()} -> {end.isoformat()}" if start and end else (f"dal {start.isoformat()}" if start else (f"fino al {end.isoformat()}" if end else "")))

async def offers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_auth(update.effective_user.id):
        logger.warning("Unauthorized offers from %s", update.effective_user.id)
        return
    db: Session = SessionLocal()
    try:
        offers = (
            db.query(ServiceOffer)
            .filter(ServiceOffer.status == "published")
            .order_by(ServiceOffer.created_at.desc())
            .limit(5)
            .all()
        )
        if not offers:
            await update.message.reply_text("Al momento non ci sono offerte pubblicate.")
            return
        lines = []
        for off in offers:
            category_label = SERVICE_CATEGORY_LABELS.get(off.category, off.category.title())
            location_parts = [_escape(off.city)]
            if off.zone:
                location_parts.append(_escape(off.zone))
            location_text = " · ".join(location_parts)
            lines.append(
                f"\u2022 *{_escape(off.title)}*\n_{category_label} · {location_text}_\nReferente: {_escape(off.contact_name)}\nContatto: {_escape(off.contact_method)}{f\'\nDisponibilità: {_escape(_format_range(off.available_from, off.available_to))}\' if off.available_from or off.available_to else ''}{f\'\nTariffa: {_escape(off.rate)}\' if off.rate else ''}\n\n"
            )
        payload = ''.join(lines)[:3800]
        await update.message.reply_markdown_v2(payload, disable_web_page_preview=True)
    finally:
        db.close()

def main():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN non impostato in .env")
    logger.info("Starting LocalBrain bot")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("latest", latest))
    app.add_handler(CommandHandler("cat", cat))
    app.add_handler(CommandHandler("offers", offers))
    app.run_polling()

if __name__ == "__main__":
    main()
