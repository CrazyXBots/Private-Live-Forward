# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import asyncio
import logging
from database import db
from config import Config, temp
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.errors import (
    FloodWait, ChatAdminRequired, ChannelPrivate,
    ChatWriteForbidden, UserNotParticipant, PeerIdInvalid
)
from plugins.test import get_client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ══════════════════════════════════════════════════════════════
#   CONSTANTS
# ══════════════════════════════════════════════════════════════

FREE_MAX_CONNECTIONS    = 1
PREMIUM_MAX_CONNECTIONS = 10

# ══════════════════════════════════════════════════════════════
#   RUNTIME STATE
#   _userbot_tasks  : { "uid:idx" -> asyncio.Task }
#   _userbot_clients: { "uid:idx" -> pyrogram.Client }
# ══════════════════════════════════════════════════════════════

_userbot_tasks:   dict[str, asyncio.Task]  = {}
_userbot_clients: dict[str, Client]        = {}


def _task_key(user_id: int, idx: int) -> str:
    return f"{user_id}:{idx}"


# ══════════════════════════════════════════════════════════════
#   HELPERS
# ══════════════════════════════════════════════════════════════

async def _is_premium(user_id: int) -> bool:
    return await db.is_premium_user(user_id)


async def _max_connections(user_id: int) -> int:
    return PREMIUM_MAX_CONNECTIONS if await _is_premium(user_id) else FREE_MAX_CONNECTIONS


async def _bot_in_channel(bot: Client, chat_id: int) -> bool:
    """Return True if the bot itself is a member/admin of the channel."""
    try:
        member = await bot.get_chat_member(chat_id, "me")
        return member is not None
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════
#   PANEL TEXT
# ══════════════════════════════════════════════════════════════

async def live_panel_text(user_id: int) -> str:
    conns   = await db.get_live_connections(user_id)
    premium = await _is_premium(user_id)
    max_c   = PREMIUM_MAX_CONNECTIONS if premium else FREE_MAX_CONNECTIONS
    plan    = "⭐ PREMIUM" if premium else "🆓 FREE"

    lines = [
        f"📡 <b>LIVE FORWARD</b>  |  {plan}\n",
        f"<b>Connections:</b> {len(conns)} / {max_c}\n",
    ]
    if conns:
        lines.append("─────────────────────────")
        for c in conns:
            idx  = c["index"]
            src  = c.get("source_title")  or "❌ Not Set"
            dst  = c.get("dest_title")    or "❌ Not Set"
            sts  = "🟢" if c.get("active") else "🔴"
            mode = "👤 Userbot" if _task_key(user_id, idx) in _userbot_tasks else "🤖 Bot"
            lines.append(
                f"\n<b>#{idx+1}</b> {sts} <i>({mode})</i>\n"
                f"  📤 <b>Source:</b> {src}\n"
                f"  📥 <b>Dest:</b>   {dst}"
            )
    else:
        lines.append("\n<i>No connections yet. Tap ➕ Add Connection to start.</i>")

    if not premium:
        lines.append("\n\n<i>💡 Upgrade to ⭐ Premium to add up to 10 connections!</i>")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#   BUTTONS
# ══════════════════════════════════════════════════════════════

async def live_panel_buttons(user_id: int) -> InlineKeyboardMarkup:
    conns   = await db.get_live_connections(user_id)
    max_c   = await _max_connections(user_id)
    premium = await _is_premium(user_id)
    btns    = []

    for c in conns:
        idx  = c["index"]
        src  = (c.get("source_title") or "No Source")[:18]
        dst  = (c.get("dest_title")   or "No Dest")[:18]
        sts  = "🟢" if c.get("active") else "🔴"
        btns.append([InlineKeyboardButton(
            f"{sts} #{idx+1}  {src} ➜ {dst}",
            callback_data=f"lf#conn_{idx}"
        )])

    if len(conns) < max_c:
        btns.append([InlineKeyboardButton("➕ ADD CONNECTION", callback_data="lf#add_conn")])
    elif not premium:
        btns.append([InlineKeyboardButton(
            "⭐ UPGRADE TO PREMIUM — Up to 10 Connections",
            callback_data="lf#buy_premium"
        )])
    else:
        btns.append([InlineKeyboardButton("✅ Maximum 10 Connections Reached", callback_data="lf#noop")])

    btns.append([InlineKeyboardButton("⫷ BACK", callback_data="settings#main")])
    return InlineKeyboardMarkup(btns)


def conn_detail_buttons(idx: int, active: bool) -> InlineKeyboardMarkup:
    toggle_label = "⏹ STOP LIVE" if active else "▶️ START LIVE"
    toggle_cb    = f"lf#stop_{idx}" if active else f"lf#start_{idx}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 SET SOURCE CHANNEL",      callback_data=f"lf#set_src_{idx}")],
        [InlineKeyboardButton("📥 SET DESTINATION CHANNEL", callback_data=f"lf#set_dst_{idx}")],
        [
            InlineKeyboardButton(toggle_label, callback_data=toggle_cb),
            InlineKeyboardButton("🗑 DELETE",  callback_data=f"lf#del_conn_{idx}"),
        ],
        [InlineKeyboardButton("⫷ BACK", callback_data="lf#panel")],
    ])


def conn_detail_text(c: dict, idx: int, mode: str = "") -> str:
    src    = c.get("source_title") or "❌ Not Set"
    dst    = c.get("dest_title")   or "❌ Not Set"
    status = "🟢 ACTIVE" if c.get("active") else "🔴 INACTIVE"
    mode_line = f"\n<b>Mode:</b> {mode}" if mode else ""
    return (
        f"📡 <b>CONNECTION #{idx+1}</b>\n\n"
        f"<b>STATUS :</b> {status}{mode_line}\n"
        f"<b>📤 SOURCE :</b> {src}\n"
        f"<b>📥 DESTINATION :</b> {dst}\n\n"
        f"<i>New messages from SOURCE will be copied to\n"
        f"DESTINATION in real time (copyright safe).\n"
        f"Works even if bot is NOT in the source channel.</i>"
    )


# ══════════════════════════════════════════════════════════════
#   CORE — START / STOP A LIVE CONNECTION
# ══════════════════════════════════════════════════════════════

async def _start_live_connection(bot: Client, user_id: int, idx: int) -> str:
    """
    Start listening on source channel and copying to dest.
    
    Priority:
      1. Bot is in source channel → use bot's on_message (already handled
         by live_forward_bot_listener below). Return mode "🤖 Bot".
      2. Bot NOT in source channel → spin up user's userbot session,
         attach an asyncio task that polls/listens. Return mode "👤 Userbot".
    
    Returns a mode string for display, or raises on failure.
    """
    conn = await db.get_live_connection(user_id, idx)
    if not conn:
        raise ValueError("Connection not found")

    source_id = conn.get("source_id")
    dest_id   = conn.get("dest_id")
    if not source_id or not dest_id:
        raise ValueError("Source or destination not set")

    key = _task_key(user_id, idx)

    # Stop any existing task for this connection first
    await _stop_live_connection(user_id, idx)

    # ── Check if bot is already in source channel ──────────────
    if await _bot_in_channel(bot, source_id):
        # Bot can see messages via on_message handler — no task needed
        logger.info(f"[LiveForward] #{idx} user={user_id}: Bot mode (bot is in source)")
        return "🤖 Bot (already in channel)"

    # ── Bot NOT in channel — use userbot ───────────────────────
    userbot_data = await db.get_userbot(user_id)
    if not userbot_data or not userbot_data.get("session"):
        raise ValueError(
            "Bot is not in the source channel and no userbot session found.\n"
            "Please add a userbot via Settings → Bots → Add Userbot."
        )

    session_string = userbot_data["session"]

    # Build and start the userbot client
    userbot = await get_client(session_string, is_bot=False)
    try:
        await userbot.start()
    except Exception as e:
        raise ValueError(f"Failed to start userbot: {e}")

    _userbot_clients[key] = userbot
    logger.info(f"[LiveForward] #{idx} user={user_id}: Userbot mode started")

    # Spin up the listener task
    task = asyncio.create_task(
        _userbot_listener_task(bot, userbot, user_id, idx, source_id, dest_id)
    )
    _userbot_tasks[key] = task
    logger.info(f"[LiveForward] #{idx} user={user_id}: Listener task created")
    return "👤 Userbot (bot not in channel)"


async def _stop_live_connection(user_id: int, idx: int):
    """Cancel any running userbot task for this connection."""
    key = _task_key(user_id, idx)

    task = _userbot_tasks.pop(key, None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    client = _userbot_clients.pop(key, None)
    if client:
        try:
            await client.stop()
        except Exception:
            pass

    logger.info(f"[LiveForward] #{idx} user={user_id}: Stopped")


# ══════════════════════════════════════════════════════════════
#   USERBOT LISTENER TASK
#   Runs as a long-lived asyncio task.
#   Uses get_chat_history in a loop to catch new messages.
# ══════════════════════════════════════════════════════════════

async def _userbot_listener_task(
    bot: Client,
    userbot: Client,
    user_id: int,
    idx: int,
    source_id: int,
    dest_id: int
):
    """
    Long-running task that watches a source channel via userbot
    and copies new messages to dest using the main bot.

    Uses offset_id tracking so it never re-sends old messages.
    Polls every 5 seconds for new messages.
    """
    logger.info(f"[UBListener] Starting for user={user_id} idx={idx} src={source_id}")

    # Get current latest message ID as starting offset
    try:
        history = [m async for m in userbot.get_chat_history(source_id, limit=1)]
        last_id = history[0].id if history else 0
    except Exception as e:
        logger.error(f"[UBListener] Failed to get initial offset: {e}")
        last_id = 0

    while True:
        try:
            # Check if still active in DB (user may have stopped it)
            conn = await db.get_live_connection(user_id, idx)
            if not conn or not conn.get("active"):
                logger.info(f"[UBListener] Connection {idx} deactivated, stopping task")
                break

            # Fetch messages newer than last_id
            new_messages = []
            async for msg in userbot.get_chat_history(source_id, limit=50):
                if msg.id <= last_id:
                    break
                new_messages.append(msg)

            # Process oldest-first
            for msg in reversed(new_messages):
                if msg.id > last_id:
                    last_id = msg.id
                    try:
                        await _safe_copy(bot, msg, dest_id, user_id, via_userbot=True)
                    except Exception as e:
                        logger.error(f"[UBListener] copy error: {e}")

            await asyncio.sleep(5)   # poll interval

        except asyncio.CancelledError:
            logger.info(f"[UBListener] Task cancelled for user={user_id} idx={idx}")
            break
        except FloodWait as fw:
            logger.warning(f"[UBListener] FloodWait {fw.value}s")
            await asyncio.sleep(fw.value)
        except Exception as e:
            logger.error(f"[UBListener] Unexpected error: {e}")
            await asyncio.sleep(10)

    logger.info(f"[UBListener] Exited for user={user_id} idx={idx}")


# ══════════════════════════════════════════════════════════════
#   BOT ON_MESSAGE LISTENER
#   Only fires when the bot IS already a member of source channel.
# ══════════════════════════════════════════════════════════════

@Client.on_message(filters.channel & ~filters.private)
async def live_forward_bot_listener(bot: Client, message: Message):
    """
    Fires when bot itself receives a channel post (bot is member of source).
    Handles all active connections whose source matches this chat.
    """
    source_chat_id = message.chat.id

    active_users = await db.get_all_active_live_users()
    if not active_users:
        return

    for user_id in active_users:
        conns = await db.get_live_connections(user_id)
        for conn in conns:
            if not conn.get("active"):
                continue
            if conn.get("source_id") != source_chat_id:
                continue
            dest = conn.get("dest_id")
            if not dest:
                continue
            # Skip if this connection is handled by a userbot task
            if _task_key(user_id, conn["index"]) in _userbot_tasks:
                continue
            try:
                await _safe_copy(bot, message, dest, user_id)
            except Exception as e:
                logger.error(
                    f"[BotListener] user={user_id} conn={conn['index']} error: {e}"
                )


# ══════════════════════════════════════════════════════════════
#   SAFE COPY — copyright protected, works for both modes
# ══════════════════════════════════════════════════════════════

async def _safe_copy(
    bot: Client,
    message: Message,
    dest: int,
    user_id: int,
    via_userbot: bool = False
):
    """
    Copy a message to destination.
    - Uses bot.copy_message() for clean re-post (no forward tag).
    - Handles all errors gracefully.
    """
    if getattr(message, "has_protected_content", False):
        logger.info(f"[LiveForward] Skipping protected msg {message.id}")
        return

    caption = message.caption

    try:
        await bot.copy_message(
            chat_id=dest,
            from_chat_id=message.chat.id,
            message_id=message.id,
            caption=caption,
            parse_mode=enums.ParseMode.HTML if caption else enums.ParseMode.DISABLED
        )

    except FloodWait as fw:
        logger.warning(f"[LiveForward] FloodWait {fw.value}s")
        await asyncio.sleep(fw.value)
        await bot.copy_message(
            chat_id=dest,
            from_chat_id=message.chat.id,
            message_id=message.id,
            caption=caption,
            parse_mode=enums.ParseMode.HTML if caption else enums.ParseMode.DISABLED
        )

    except (ChatAdminRequired, ChatWriteForbidden):
        logger.warning(f"[LiveForward] Bot lacks permission in dest {dest}")

    except (ChannelPrivate, PeerIdInvalid):
        logger.warning(f"[LiveForward] Cannot access channel for user {user_id}")

    except Exception as e:
        err = str(e).lower()
        if any(k in err for k in ("copyright", "restricted", "protected", "forward")):
            logger.info(f"[LiveForward] Copyright skip: {e}")
        else:
            raise


# ══════════════════════════════════════════════════════════════
#   RESTART — resume all active connections after bot restart
# ══════════════════════════════════════════════════════════════

async def restart_live_forward_tasks(bot: Client):
    """
    Call this from main.py on bot startup.
    Resumes all active live connections that need userbot tasks.
    """
    logger.info("[LiveForward] Restarting active live connections...")
    active_users = await db.get_all_active_live_users()
    count = 0
    for user_id in active_users:
        conns = await db.get_live_connections(user_id)
        for conn in conns:
            if not conn.get("active"):
                continue
            idx = conn["index"]
            try:
                mode = await _start_live_connection(bot, user_id, idx)
                logger.info(f"[LiveForward] Resumed user={user_id} idx={idx} mode={mode}")
                count += 1
            except Exception as e:
                logger.warning(f"[LiveForward] Could not resume user={user_id} idx={idx}: {e}")
    logger.info(f"[LiveForward] {count} connection(s) resumed.")


# ══════════════════════════════════════════════════════════════
#   CALLBACK HANDLER — settings UI
# ══════════════════════════════════════════════════════════════

@Client.on_callback_query(filters.regex(r"^lf#"))
async def live_forward_cb(bot, query):
    user_id = query.from_user.id
    action  = query.data.split("#", 1)[1]

    # ── No-op ──────────────────────────────────────────────
    if action == "noop":
        return await query.answer()

    # ── Main panel ─────────────────────────────────────────
    if action == "panel":
        await query.message.edit_text(
            await live_panel_text(user_id),
            reply_markup=await live_panel_buttons(user_id)
        )

    # ── Add connection ──────────────────────────────────────
    elif action == "add_conn":
        conns   = await db.get_live_connections(user_id)
        max_c   = await _max_connections(user_id)
        premium = await _is_premium(user_id)
        if len(conns) >= max_c:
            if not premium:
                return await query.answer(
                    "⭐ Upgrade to Premium to add more than 1 connection!",
                    show_alert=True
                )
            return await query.answer("Maximum 10 connections reached.", show_alert=True)
        idx = await db.add_live_connection(user_id)
        conn = await db.get_live_connection(user_id, idx)
        await query.message.edit_text(
            conn_detail_text(conn, idx),
            reply_markup=conn_detail_buttons(idx, False)
        )

    # ── Open detail ─────────────────────────────────────────
    elif action.startswith("conn_"):
        idx  = int(action.split("_", 1)[1])
        conn = await db.get_live_connection(user_id, idx)
        if not conn:
            return await query.answer("Connection not found.", show_alert=True)
        key  = _task_key(user_id, idx)
        mode = "👤 Userbot" if key in _userbot_tasks else ("🤖 Bot" if conn.get("active") else "")
        await query.message.edit_text(
            conn_detail_text(conn, idx, mode),
            reply_markup=conn_detail_buttons(idx, conn.get("active", False))
        )

    # ── Set source ──────────────────────────────────────────
    elif action.startswith("set_src_"):
        idx = int(action.split("_")[-1])
        await query.message.delete()
        msg = await bot.ask(
            user_id,
            f"<b>📤 SET SOURCE CHANNEL — Connection #{idx+1}\n\n"
            "Forward any message from the <u>source</u> channel.\n"
            "<i>Bot does NOT need to be in the channel.</i>\n\n"
            "/cancel – cancel</b>"
        )
        if msg.text == "/cancel":
            conn = await db.get_live_connection(user_id, idx)
            return await msg.reply_text(
                conn_detail_text(conn, idx),
                reply_markup=conn_detail_buttons(idx, conn.get("active", False))
            )
        origin   = getattr(msg, "forward_origin", None)
        fwd_chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
        if not origin or not fwd_chat:
            conn = await db.get_live_connection(user_id, idx)
            return await msg.reply_text(
                "⚠️ Please forward a message from the channel.\n\n" +
                conn_detail_text(conn, idx),
                reply_markup=conn_detail_buttons(idx, conn.get("active", False))
            )
        await db.set_live_connection_source(user_id, idx, fwd_chat.id, fwd_chat.title)
        conn = await db.get_live_connection(user_id, idx)
        await msg.reply_text(
            f"✅ <b>Source set to:</b> <code>{fwd_chat.title}</code>\n\n" +
            conn_detail_text(conn, idx),
            reply_markup=conn_detail_buttons(idx, conn.get("active", False))
        )

    # ── Set destination ─────────────────────────────────────
    elif action.startswith("set_dst_"):
        idx = int(action.split("_")[-1])
        await query.message.delete()
        msg = await bot.ask(
            user_id,
            f"<b>📥 SET DESTINATION CHANNEL — Connection #{idx+1}\n\n"
            "Forward any message from the <u>destination</u> channel.\n"
            "/cancel – cancel</b>"
        )
        if msg.text == "/cancel":
            conn = await db.get_live_connection(user_id, idx)
            return await msg.reply_text(
                conn_detail_text(conn, idx),
                reply_markup=conn_detail_buttons(idx, conn.get("active", False))
            )
        origin   = getattr(msg, "forward_origin", None)
        fwd_chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
        if not origin or not fwd_chat:
            conn = await db.get_live_connection(user_id, idx)
            return await msg.reply_text(
                "⚠️ Please forward a message from the channel.\n\n" +
                conn_detail_text(conn, idx),
                reply_markup=conn_detail_buttons(idx, conn.get("active", False))
            )
        await db.set_live_connection_dest(user_id, idx, fwd_chat.id, fwd_chat.title)
        conn = await db.get_live_connection(user_id, idx)
        await msg.reply_text(
            f"✅ <b>Destination set to:</b> <code>{fwd_chat.title}</code>\n\n" +
            conn_detail_text(conn, idx),
            reply_markup=conn_detail_buttons(idx, conn.get("active", False))
        )

    # ── Start ───────────────────────────────────────────────
    elif action.startswith("start_"):
        idx  = int(action.split("_", 1)[1])
        conn = await db.get_live_connection(user_id, idx)
        if not conn:
            return await query.answer("Connection not found.", show_alert=True)
        if not conn.get("source_id"):
            return await query.answer("⚠️ Set a SOURCE channel first!", show_alert=True)
        if not conn.get("dest_id"):
            return await query.answer("⚠️ Set a DESTINATION channel first!", show_alert=True)

        await query.answer("⏳ Starting...", show_alert=False)
        try:
            mode = await _start_live_connection(bot, user_id, idx)
        except ValueError as e:
            return await query.message.edit_text(
                f"❌ <b>Could not start:</b>\n{e}\n\n" + conn_detail_text(conn, idx),
                reply_markup=conn_detail_buttons(idx, False)
            )

        await db.set_live_connection_active(user_id, idx, True)
        conn = await db.get_live_connection(user_id, idx)
        await query.answer(f"✅ STARTED — {mode}", show_alert=True)
        await query.message.edit_text(
            conn_detail_text(conn, idx, mode),
            reply_markup=conn_detail_buttons(idx, True)
        )

    # ── Stop ────────────────────────────────────────────────
    elif action.startswith("stop_"):
        idx = int(action.split("_", 1)[1])
        await _stop_live_connection(user_id, idx)
        await db.set_live_connection_active(user_id, idx, False)
        conn = await db.get_live_connection(user_id, idx)
        await query.answer("⏹ Live Forward STOPPED.", show_alert=True)
        await query.message.edit_text(
            conn_detail_text(conn, idx),
            reply_markup=conn_detail_buttons(idx, False)
        )

    # ── Delete ──────────────────────────────────────────────
    elif action.startswith("del_conn_"):
        idx = int(action.split("_")[-1])
        await _stop_live_connection(user_id, idx)
        await db.delete_live_connection(user_id, idx)
        await query.answer("🗑 Connection deleted.", show_alert=True)
        await query.message.edit_text(
            await live_panel_text(user_id),
            reply_markup=await live_panel_buttons(user_id)
        )

    # ── Premium upsell ──────────────────────────────────────
    elif action == "buy_premium":
        await query.message.edit_text(
            "⭐ <b>UPGRADE TO PREMIUM</b>\n\n"
            "With Premium you get:\n"
            "• Up to <b>10 live forward connections</b>\n"
            "• Each connection has its own Source ➜ Destination\n"
            "• Works with or without bot in channel\n\n"
            f"👤 <a href='tg://user?id={Config.BOT_OWNER}'>Contact owner to purchase</a>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 Contact Owner", url=f"tg://user?id={Config.BOT_OWNER}")],
                [InlineKeyboardButton("⫷ BACK", callback_data="lf#panel")]
            ]),
            disable_web_page_preview=True
        )


# ══════════════════════════════════════════════════════════════
#   ADMIN COMMANDS
# ══════════════════════════════════════════════════════════════

@Client.on_message(filters.command("grantpremium") & filters.user(Config.BOT_OWNER))
async def grant_premium(bot, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> /grantpremium &lt;user_id&gt;")
    try:
        target = int(message.command[1])
    except ValueError:
        return await message.reply_text("⚠️ Invalid user ID.")
    await db.set_premium(target, True)
    await message.reply_text(f"✅ Premium granted to <code>{target}</code>")
    try:
        await bot.send_message(
            target,
            "⭐ <b>You have been upgraded to Premium!</b>\n"
            "You can now create up to <b>10 live forward connections</b>.\n"
            "Open /settings → 📡 Live Forward to get started."
        )
    except Exception:
        pass


@Client.on_message(filters.command("revokepremium") & filters.user(Config.BOT_OWNER))
async def revoke_premium(bot, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> /revokepremium &lt;user_id&gt;")
    try:
        target = int(message.command[1])
    except ValueError:
        return await message.reply_text("⚠️ Invalid user ID.")
    await db.set_premium(target, False)
    await message.reply_text(f"✅ Premium revoked from <code>{target}</code>")

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
