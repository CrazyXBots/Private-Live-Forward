# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import asyncio
import logging
from database import db
from config import Config, temp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.errors import FloodWait, ChatAdminRequired, ChannelPrivate
from .test import CLIENT, get_client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CLIENT = CLIENT()

# ─────────────────────────────────────────────
#  LIVE FORWARD SETTINGS PANEL
# ─────────────────────────────────────────────

def live_forward_main_buttons():
    buttons = [
        [InlineKeyboardButton("📥 DESTINATION CHANNEL", callback_data="lf#set_destination")],
        [InlineKeyboardButton("📤 SOURCE CHANNELS",     callback_data="lf#manage_sources")],
        [InlineKeyboardButton("⚙️ FILTERS",             callback_data="lf#filters")],
        [InlineKeyboardButton("🤖 MANAGE BOT / USERBOT", callback_data="lf#manage_bot")],
        [
            InlineKeyboardButton("▶️ START LIVE", callback_data="lf#start"),
            InlineKeyboardButton("⏹ STOP LIVE",  callback_data="lf#stop"),
        ],
        [InlineKeyboardButton("🔄 BACK", callback_data="settings#main")],
    ]
    return InlineKeyboardMarkup(buttons)


async def live_forward_status_text(user_id: int) -> str:
    cfg = await db.get_live_forward_config(user_id)
    status    = "🟢 ACTIVE"   if cfg.get("active")      else "🔴 INACTIVE"
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


# ─────────────────────────────────────────────
#  CALLBACK HANDLER
# ─────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^lf#"))
async def live_forward_cb(bot, query):
    user_id = query.from_user.id
    action  = query.data.split("#")[1]
    back_btn = [[InlineKeyboardButton("🔄 BACK", callback_data="lf#panel")]]

    # ── Show panel ──────────────────────────────
    if action == "panel":
        await query.message.edit_text(
            await live_forward_status_text(user_id),
            reply_markup=live_forward_main_buttons()
        )

    # ── Set destination ─────────────────────────
    elif action == "set_destination":
        await query.message.delete()
        msg = await bot.ask(
            user_id,
            "<b>📥 SET DESTINATION CHANNEL\n\n"
            "Forward any message from your <u>destination</u> channel here.\n"
            "/cancel – cancel</b>"
        )
        if msg.text == "/cancel":
            return await msg.reply_text("❌ Cancelled.", reply_markup=InlineKeyboardMarkup(back_btn))
        if not msg.forward_date or not msg.forward_from_chat:
            return await msg.reply_text("⚠️ That's not a forwarded message. Please forward a message from the channel.",
                                        reply_markup=InlineKeyboardMarkup(back_btn))
        chat    = msg.forward_from_chat
        chat_id = chat.id
        title   = chat.title
        await db.set_live_forward_destination(user_id, chat_id, title)
        await msg.reply_text(
            f"✅ <b>Destination set to:</b> <code>{title}</code>",
            reply_markup=InlineKeyboardMarkup(back_btn)
        )

    # ── Manage source channels ──────────────────
    elif action == "manage_sources":
        cfg      = await db.get_live_forward_config(user_id)
        sources  = cfg.get("source_channels", [])
        btns     = []
        for src in sources:
            btns.append([InlineKeyboardButton(
                f"❌ Remove: {src.get('title', src['chat_id'])}",
                callback_data=f"lf#remove_src_{src['chat_id']}"
            )])
        btns.append([InlineKeyboardButton("➕ Add Source Channel", callback_data="lf#add_source")])
        btns.append([InlineKeyboardButton("🔄 BACK", callback_data="lf#panel")])
        await query.message.edit_text(
            f"<b>📤 SOURCE CHANNELS</b>\n\n"
            f"Total: <code>{len(sources)}</code> channels\n\n"
            f"<i>Messages from these channels will be forwarded live.</i>",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif action == "add_source":
        await query.message.delete()
        msg = await bot.ask(
            user_id,
            "<b>📤 ADD SOURCE CHANNEL\n\n"
            "Forward any message from the <u>source</u> channel you want to monitor.\n"
            "/cancel – cancel</b>"
        )
        if msg.text == "/cancel":
            return await msg.reply_text("❌ Cancelled.", reply_markup=InlineKeyboardMarkup(back_btn))
        if not msg.forward_date or not msg.forward_from_chat:
            return await msg.reply_text("⚠️ That's not a forwarded message.",
                                        reply_markup=InlineKeyboardMarkup(back_btn))
        chat    = msg.forward_from_chat
        chat_id = chat.id
        title   = chat.title
        await db.add_live_source_channel(user_id, chat_id, title)
        await msg.reply_text(
            f"✅ <b>Source channel added:</b> <code>{title}</code>",
            reply_markup=InlineKeyboardMarkup(back_btn)
        )

    elif action.startswith("remove_src_"):
        chat_id = int(action.replace("remove_src_", ""))
        await db.remove_live_source_channel(user_id, chat_id)
        await query.answer("✅ Source channel removed.", show_alert=True)
        cfg     = await db.get_live_forward_config(user_id)
        sources = cfg.get("source_channels", [])
        btns    = []
        for src in sources:
            btns.append([InlineKeyboardButton(
                f"❌ Remove: {src.get('title', src['chat_id'])}",
                callback_data=f"lf#remove_src_{src['chat_id']}"
            )])
        btns.append([InlineKeyboardButton("➕ Add Source Channel", callback_data="lf#add_source")])
        btns.append([InlineKeyboardButton("🔄 BACK", callback_data="lf#panel")])
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btns))

    # ── Manage bot ──────────────────────────────
    elif action == "manage_bot":
        await query.answer("Use /settings → Bots to manage your bot/userbot.", show_alert=True)

    # ── Filters ─────────────────────────────────
    elif action == "filters":
        await query.answer("Live forward uses the same filters as your main settings.", show_alert=True)

    # ── Start live forward ──────────────────────
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
            await live_forward_status_text(user_id),
            reply_markup=live_forward_main_buttons()
        )

    # ── Stop live forward ───────────────────────
    elif action == "stop":
        await db.set_live_forward_active(user_id, False)
        await query.answer("⏹ Live Forward STOPPED.", show_alert=True)
        await query.message.edit_text(
            await live_forward_status_text(user_id),
            reply_markup=live_forward_main_buttons()
        )


# ─────────────────────────────────────────────
#  LIVE MESSAGE LISTENER
#  Monitors ALL incoming channel posts and
#  forwards to destination of subscribed users.
# ─────────────────────────────────────────────

@Client.on_message(filters.channel & ~filters.private)
async def live_forward_listener(bot: Client, message: Message):
    """
    Fires for every channel post the bot can see.
    Checks all users with live forward active and
    forwards matching messages to their destination.

    COPYRIGHT PROTECTION:
    - Uses copy_message() instead of forward_message().
      copy_message re-sends content WITHOUT the
      "Forwarded from <channel>" tag, so the
      destination receives a clean original-looking
      post — avoiding Telegram's copyright/restriction
      notice that some channels attach to forwarded msgs.
    - Protect-content / no-forward messages are caught
      and skipped gracefully instead of crashing.
    """
    source_chat_id = message.chat.id

    # Fetch all users who have live forward active
    active_users = await db.get_all_active_live_forward_users()

    for user_id in active_users:
        cfg     = await db.get_live_forward_config(user_id)
        sources = cfg.get("source_channels", [])
        dest    = cfg.get("destination_id")

        # Is this message from one of this user's source channels?
        source_ids = [s["chat_id"] for s in sources]
        if source_chat_id not in source_ids:
            continue
        if not dest:
            continue

        try:
            await _copy_message_safe(bot, message, dest, user_id, cfg)
        except Exception as e:
            logger.error(f"[LiveForward] user {user_id}: {e}")


async def _copy_message_safe(bot: Client, message: Message, dest: int, user_id: int, cfg: dict):
    """
    Copy a message to destination using copy_message (no forward tag).
    Handles copyright-protected messages, FloodWait, and caption injection.
    """
    # ── Skip protect-content / forwarding-restricted messages ──
    if message.has_protected_content:
        logger.info(f"[LiveForward] Skipping protected content from {message.chat.id}")
        return

    # ── Respect user's filter settings ──────────────────────────
    user_filters = cfg.get("filters", {})
    msg_type = _get_msg_type(message)
    if msg_type and not user_filters.get(msg_type, True):
        return

    # ── Build caption ────────────────────────────────────────────
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
        # Strip "Forwarded from" attribution by using original caption as-is
        caption = message.caption

    # ── Forward tag toggle ───────────────────────────────────────
    # forward_tag=False means we use copy (no tag), True keeps attribution.
    forward_tag = cfg.get("forward_tag", False)

    try:
        if forward_tag:
            # Standard forward — preserves "Forwarded from X" tag
            await bot.forward_messages(
                chat_id=dest,
                from_chat_id=message.chat.id,
                message_ids=message.id
            )
        else:
            # COPYRIGHT SAFE: copy_message strips forwarding origin
            await bot.copy_message(
                chat_id=dest,
                from_chat_id=message.chat.id,
                message_id=message.id,
                caption=caption,
                parse_mode=None if caption is None else "html"
            )
    except FloodWait as fw:
        logger.warning(f"[LiveForward] FloodWait {fw.value}s for user {user_id}")
        await asyncio.sleep(fw.value)
        # Retry once after wait
        await bot.copy_message(
            chat_id=dest,
            from_chat_id=message.chat.id,
            message_id=message.id,
            caption=caption,
        )
    except ChatAdminRequired:
        logger.warning(f"[LiveForward] Bot not admin in dest {dest} for user {user_id}")
    except ChannelPrivate:
        logger.warning(f"[LiveForward] Cannot access channel for user {user_id}")
    except Exception as e:
        # Catch copyright/protected errors: log and skip silently
        err = str(e).lower()
        if "copyright" in err or "restricted" in err or "protected" in err or "forward" in err:
            logger.info(f"[LiveForward] Copyright/protected msg skipped: {e}")
        else:
            raise


def _get_msg_type(message: Message):
    """Return string type of message for filter matching."""
    if message.text:        return "text"
    if message.document:    return "document"
    if message.video:       return "video"
    if message.photo:       return "photo"
    if message.audio:       return "audio"
    if message.voice:       return "voice"
    if message.animation:   return "animation"
    if message.sticker:     return "sticker"
    if message.poll:        return "poll"
    return None
