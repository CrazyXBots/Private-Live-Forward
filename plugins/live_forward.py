# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import asyncio
import logging
from database import db
from config import Config, temp
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.errors import FloodWait, ChatAdminRequired, ChannelPrivate, ChatWriteForbidden

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ═══════════════════════════════════════════════════════
#   LIVE FORWARD — BUTTON LAYOUT
# ═══════════════════════════════════════════════════════

def live_forward_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 DESTINATION CHANNEL",  callback_data="lf#set_destination")],
        [InlineKeyboardButton("📤 SOURCE CHANNELS",      callback_data="lf#manage_sources")],
        [InlineKeyboardButton("⚙️ FILTERS",              callback_data="lf#filters")],
        [InlineKeyboardButton("🤖 MANAGE BOT / USERBOT", callback_data="lf#manage_bot")],
        [
            InlineKeyboardButton("▶️ START LIVE", callback_data="lf#start"),
            InlineKeyboardButton("⏹ STOP LIVE",  callback_data="lf#stop"),
        ],
        [InlineKeyboardButton("🔄 BACK", callback_data="settings#main")],
    ])


async def live_status_text(user_id: int) -> str:
    cfg       = await db.get_live_forward_config(user_id)
    status    = "🟢 ACTIVE"  if cfg.get("active")           else "🔴 INACTIVE"
    dest      = cfg.get("destination_title") or "❌ NOT SET"
    src_count = len(cfg.get("source_channels", []))
    return (
        f"📡 <b>LIVE FORWARD SETTINGS</b>\n\n"
        f"<b>STATUS :</b> {status}\n"
        f"<b>DESTINATION :</b> {dest}\n"
        f"<b>SOURCE CHANNELS :</b> {src_count}\n\n"
        f"<i>NEW MESSAGES FROM ALL SOURCE CHANNELS WILL BE\n"
        f"FORWARDED TO DESTINATION IN REAL TIME.</i>"
    )


# ═══════════════════════════════════════════════════════
#   LIVE FORWARD — SETTINGS PANEL (callback handler)
# ═══════════════════════════════════════════════════════

@Client.on_callback_query(filters.regex(r"^lf#"))
async def live_forward_cb(bot, query):
    user_id = query.from_user.id
    action  = query.data.split("#", 1)[1]
    back    = [[InlineKeyboardButton("🔄 BACK", callback_data="lf#panel")]]

    # ── Main panel ──────────────────────────────────────
    if action == "panel":
        await query.message.edit_text(
            await live_status_text(user_id),
            reply_markup=live_forward_buttons()
        )

    # ── Set destination ──────────────────────────────────
    elif action == "set_destination":
        await query.message.delete()
        msg = await bot.ask(
            user_id,
            "<b>📥 SET DESTINATION CHANNEL\n\n"
            "Forward any message from your <u>destination</u> channel here.\n"
            "/cancel – cancel</b>"
        )
        if msg.text == "/cancel":
            return await msg.reply_text("❌ Cancelled.", reply_markup=InlineKeyboardMarkup(back))
        origin   = getattr(msg, "forward_origin", None)
        fwd_chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
        if not origin or not fwd_chat:
            return await msg.reply_text(
                "⚠️ Please forward a message from the destination channel.",
                reply_markup=InlineKeyboardMarkup(back)
            )
        chat = fwd_chat
        await db.set_live_forward_destination(user_id, chat.id, chat.title)
        await msg.reply_text(
            f"✅ <b>Destination set to:</b> <code>{chat.title}</code>",
            reply_markup=InlineKeyboardMarkup(back)
        )

    # ── Manage sources ───────────────────────────────────
    elif action == "manage_sources":
        cfg     = await db.get_live_forward_config(user_id)
        sources = cfg.get("source_channels", [])
        btns    = []
        for src in sources:
            title = src.get("title", str(src["chat_id"]))
            btns.append([InlineKeyboardButton(
                f"❌ Remove: {title}",
                callback_data=f"lf#remove_src_{src['chat_id']}"
            )])
        btns.append([InlineKeyboardButton("➕ Add Source Channel", callback_data="lf#add_source")])
        btns.append([InlineKeyboardButton("🔄 BACK", callback_data="lf#panel")])
        await query.message.edit_text(
            f"<b>📤 SOURCE CHANNELS</b>\n\nTotal: <code>{len(sources)}</code> channel(s)\n\n"
            f"<i>Messages from these channels are forwarded live.</i>",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif action == "add_source":
        await query.message.delete()
        msg = await bot.ask(
            user_id,
            "<b>📤 ADD SOURCE CHANNEL\n\n"
            "Forward any message from the source channel you want to monitor.\n"
            "/cancel – cancel</b>"
        )
        if msg.text == "/cancel":
            return await msg.reply_text("❌ Cancelled.", reply_markup=InlineKeyboardMarkup(back))
        origin   = getattr(msg, "forward_origin", None)
        fwd_chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
        if not origin or not fwd_chat:
            return await msg.reply_text(
                "⚠️ Please forward a message from the source channel.",
                reply_markup=InlineKeyboardMarkup(back)
            )
        chat = fwd_chat
        await db.add_live_source_channel(user_id, chat.id, chat.title)
        await msg.reply_text(
            f"✅ <b>Source channel added:</b> <code>{chat.title}</code>",
            reply_markup=InlineKeyboardMarkup(back)
        )

    elif action.startswith("remove_src_"):
        chat_id = int(action.replace("remove_src_", ""))
        await db.remove_live_source_channel(user_id, chat_id)
        await query.answer("✅ Source channel removed.", show_alert=True)
        # Refresh source list
        cfg     = await db.get_live_forward_config(user_id)
        sources = cfg.get("source_channels", [])
        btns    = []
        for src in sources:
            title = src.get("title", str(src["chat_id"]))
            btns.append([InlineKeyboardButton(
                f"❌ Remove: {title}",
                callback_data=f"lf#remove_src_{src['chat_id']}"
            )])
        btns.append([InlineKeyboardButton("➕ Add Source Channel", callback_data="lf#add_source")])
        btns.append([InlineKeyboardButton("🔄 BACK", callback_data="lf#panel")])
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btns))

    # ── Bot management (redirect) ────────────────────────
    elif action == "manage_bot":
        await query.answer(
            "Use /settings → 🤖 Bots to manage your bot/userbot.",
            show_alert=True
        )

    # ── Filters (redirect) ───────────────────────────────
    elif action == "filters":
        await query.answer(
            "Live forward uses the same filters as your main settings → Filters.",
            show_alert=True
        )

    # ── Start live ───────────────────────────────────────
    elif action == "start":
        cfg  = await db.get_live_forward_config(user_id)
        dest = cfg.get("destination_id")
        srcs = cfg.get("source_channels", [])
        if not dest:
            return await query.answer("⚠️ Set a destination channel first!", show_alert=True)
        if not srcs:
            return await query.answer("⚠️ Add at least one source channel first!", show_alert=True)
        await db.set_live_forward_active(user_id, True)
        await query.answer("✅ Live Forward STARTED!", show_alert=True)
        await query.message.edit_text(
            await live_status_text(user_id),
            reply_markup=live_forward_buttons()
        )

    # ── Stop live ────────────────────────────────────────
    elif action == "stop":
        await db.set_live_forward_active(user_id, False)
        await query.answer("⏹ Live Forward STOPPED.", show_alert=True)
        await query.message.edit_text(
            await live_status_text(user_id),
            reply_markup=live_forward_buttons()
        )


# ═══════════════════════════════════════════════════════
#   LIVE FORWARD — REAL-TIME MESSAGE LISTENER
#   Fires on every channel post the bot can see.
#   Uses copy_message() for copyright protection.
# ═══════════════════════════════════════════════════════

@Client.on_message(filters.channel & ~filters.private)
async def live_forward_listener(bot: Client, message: Message):
    """
    COPYRIGHT PROTECTION STRATEGY
    ──────────────────────────────
    • copy_message()  →  re-sends content as a FRESH post with NO
      "Forwarded from …" tag.  This breaks the copyright chain that
      Telegram enforces on restricted channels.
    • has_protected_content messages are silently skipped so the bot
      never crashes on "forward restricted" content.
    • FloodWait is caught and retried automatically.
    • All other copyright/restricted errors are logged and skipped.
    """
    source_chat_id = message.chat.id

    # Fetch all users with live forward currently active
    active_users = await db.get_all_active_live_forward_users()
    if not active_users:
        return

    for user_id in active_users:
        cfg     = await db.get_live_forward_config(user_id)
        sources = cfg.get("source_channels", [])
        dest    = cfg.get("destination_id")

        # Only process if this message is from one of the user's sources
        if source_chat_id not in [s["chat_id"] for s in sources]:
            continue
        if not dest:
            continue

        try:
            await _safe_copy(bot, message, dest, user_id, cfg)
        except Exception as e:
            logger.error(f"[LiveForward] user={user_id} error: {e}")


async def _safe_copy(bot: Client, message: Message, dest: int,
                     user_id: int, cfg: dict):
    """Copy a message to destination with full copyright & error protection."""

    # ── Skip protected/restricted content ───────────────
    if getattr(message, "has_protected_content", False):
        logger.info(f"[LiveForward] Skipping protected msg from {message.chat.id}")
        return

    # ── Respect user's message type filters ─────────────
    user_filters = cfg.get("filters", {})
    msg_type = _msg_type(message)
    if msg_type and not user_filters.get(msg_type, True):
        return

    # ── Build caption ────────────────────────────────────
    custom_caption = cfg.get("caption")
    if custom_caption:
        try:
            caption = custom_caption.format(
                filename=getattr(getattr(message, "document", None), "file_name", ""),
                size="",
                caption=message.caption or ""
            )
        except Exception:
            caption = message.caption
    else:
        caption = message.caption   # keep original caption, no "Forwarded from" tag

    # ── Forward tag setting ──────────────────────────────
    # forward_tag=True  → standard forward (shows origin, may trigger copyright)
    # forward_tag=False → copy_message (no origin tag = copyright safe) [DEFAULT]
    forward_tag = cfg.get("forward_tag", False)

    try:
        if forward_tag:
            await bot.forward_messages(
                chat_id=dest,
                from_chat_id=message.chat.id,
                message_ids=message.id
            )
        else:
            # ✅ COPYRIGHT SAFE: no forwarding origin attached
            await bot.copy_message(
                chat_id=dest,
                from_chat_id=message.chat.id,
                message_id=message.id,
                caption=caption,
                parse_mode=enums.ParseMode.HTML if caption else enums.ParseMode.DISABLED
            )

    except FloodWait as fw:
        logger.warning(f"[LiveForward] FloodWait {fw.value}s — sleeping...")
        await asyncio.sleep(fw.value)
        await bot.copy_message(
            chat_id=dest,
            from_chat_id=message.chat.id,
            message_id=message.id,
            caption=caption,
        )

    except (ChatAdminRequired, ChatWriteForbidden):
        logger.warning(f"[LiveForward] Bot lacks permission in dest {dest}")

    except ChannelPrivate:
        logger.warning(f"[LiveForward] Cannot access source/dest for user {user_id}")

    except Exception as e:
        # Silently skip any copyright / forward-restricted Telegram errors
        err_lower = str(e).lower()
        if any(k in err_lower for k in ("copyright", "restricted", "protected", "forward")):
            logger.info(f"[LiveForward] Copyright/restricted skip: {e}")
        else:
            raise   # re-raise unexpected errors so they appear in logs


def _msg_type(message: Message):
    """Return the filter key string for a message's content type."""
    if message.text:      return "text"
    if message.document:  return "document"
    if message.video:     return "video"
    if message.photo:     return "photo"
    if message.audio:     return "audio"
    if message.voice:     return "voice"
    if message.animation: return "animation"
    if message.sticker:   return "sticker"
    if message.poll:      return "poll"
    return None

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
