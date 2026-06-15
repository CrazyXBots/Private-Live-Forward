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

# Mode labels & descriptions
MODE_LABELS = {
    "auto": "🔄 Auto",
    "bot":  "🤖 Bot Mode",
    "user": "👤 User Mode",
}
MODE_DESC = {
    "auto": "Bot checks automatically. Uses Bot if it's in source channel, otherwise falls back to Userbot.",
    "bot":  "Bot Mode only. Bot must be a member/admin of the source channel.",
    "user": "User Mode only. Uses your Userbot session. Bot does NOT need to be in the channel.",
}

# ══════════════════════════════════════════════════════════════
#   RUNTIME STATE
# ══════════════════════════════════════════════════════════════

_userbot_tasks:   dict[str, asyncio.Task] = {}
_userbot_clients: dict[str, Client]       = {}


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
    try:
        member = await bot.get_chat_member(chat_id, "me")
        return member is not None
    except Exception:
        return False


def _running_mode(user_id: int, idx: int) -> str:
    """Return the actual running mode label for display."""
    key = _task_key(user_id, idx)
    if key in _userbot_tasks:
        return "👤 User Mode (running)"
    return "🤖 Bot Mode (running)"


# ══════════════════════════════════════════════════════════════
#   PANEL TEXT — main list
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
            idx   = c["index"]
            src   = c.get("source_title") or "❌ Not Set"
            dst   = c.get("dest_title")   or "❌ Not Set"
            sts   = "🟢" if c.get("active") else "🔴"
            mode  = MODE_LABELS.get(c.get("mode", "auto"), "🔄 Auto")
            run   = f" → {_running_mode(user_id, idx)}" if c.get("active") else ""
            lines.append(
                f"\n<b>#{idx+1}</b> {sts}  <i>{mode}{run}</i>\n"
                f"  📤 <b>Source:</b> {src}\n"
                f"  📥 <b>Dest:</b>   {dst}"
            )
    else:
        lines.append("\n<i>No connections yet. Tap ➕ Add Connection to start.</i>")

    if not premium:
        lines.append("\n\n<i>💡 Upgrade to ⭐ Premium to add up to 10 connections!</i>")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#   BUTTONS — main panel
# ══════════════════════════════════════════════════════════════

async def live_panel_buttons(user_id: int) -> InlineKeyboardMarkup:
    conns   = await db.get_live_connections(user_id)
    max_c   = await _max_connections(user_id)
    premium = await _is_premium(user_id)
    btns    = []

    for c in conns:
        idx = c["index"]
        src = (c.get("source_title") or "No Source")[:16]
        dst = (c.get("dest_title")   or "No Dest")[:16]
        sts = "🟢" if c.get("active") else "🔴"
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


# ══════════════════════════════════════════════════════════════
#   BUTTONS — connection detail panel
# ══════════════════════════════════════════════════════════════

def conn_detail_buttons(idx: int, active: bool, mode: str = "auto") -> InlineKeyboardMarkup:
    toggle_label = "⏹ STOP LIVE" if active else "▶️ START LIVE"
    toggle_cb    = f"lf#stop_{idx}" if active else f"lf#start_{idx}"
    mode_label   = MODE_LABELS.get(mode, "🔄 Auto")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 SET SOURCE CHANNEL",       callback_data=f"lf#set_src_{idx}")],
        [InlineKeyboardButton("📥 SET DESTINATION CHANNEL",  callback_data=f"lf#set_dst_{idx}")],
        [InlineKeyboardButton(f"⚙️ MODE: {mode_label}",     callback_data=f"lf#mode_{idx}")],
        [
            InlineKeyboardButton(toggle_label, callback_data=toggle_cb),
            InlineKeyboardButton("🗑 DELETE", callback_data=f"lf#del_conn_{idx}"),
        ],
        [InlineKeyboardButton("⫷ BACK", callback_data="lf#panel")],
    ])


def conn_detail_text(c: dict, idx: int) -> str:
    src    = c.get("source_title") or "❌ Not Set"
    dst    = c.get("dest_title")   or "❌ Not Set"
    status = "🟢 ACTIVE" if c.get("active") else "🔴 INACTIVE"
    mode   = c.get("mode", "auto")
    m_lbl  = MODE_LABELS.get(mode, "🔄 Auto")
    m_desc = MODE_DESC.get(mode, "")
    return (
        f"📡 <b>CONNECTION #{idx+1}</b>\n\n"
        f"<b>STATUS :</b> {status}\n"
        f"<b>📤 SOURCE :</b> {src}\n"
        f"<b>📥 DESTINATION :</b> {dst}\n"
        f"<b>⚙️ MODE :</b> {m_lbl}\n"
        f"<i>{m_desc}</i>"
    )


# ══════════════════════════════════════════════════════════════
#   BUTTONS — mode selection panel
# ══════════════════════════════════════════════════════════════

def mode_select_buttons(idx: int, current_mode: str) -> InlineKeyboardMarkup:
    def btn(mode_key, label):
        tick = " ✅" if mode_key == current_mode else ""
        return InlineKeyboardButton(f"{label}{tick}", callback_data=f"lf#setmode_{idx}_{mode_key}")

    return InlineKeyboardMarkup([
        [btn("auto", "🔄 Auto (Recommended)")],
        [btn("bot",  "🤖 Bot Mode")],
        [btn("user", "👤 User Mode")],
        [InlineKeyboardButton("⫷ BACK", callback_data=f"lf#conn_{idx}")],
    ])


def mode_select_text(idx: int, current_mode: str) -> str:
    return (
        f"📡 <b>CONNECTION #{idx+1} — SELECT MODE</b>\n\n"
        f"<b>🔄 Auto (Recommended)</b>\n"
        f"  {MODE_DESC['auto']}\n\n"
        f"<b>🤖 Bot Mode</b>\n"
        f"  {MODE_DESC['bot']}\n\n"
        f"<b>👤 User Mode</b>\n"
        f"  {MODE_DESC['user']}\n\n"
        f"<b>Current:</b> {MODE_LABELS.get(current_mode, '🔄 Auto')} ✅"
    )


# ══════════════════════════════════════════════════════════════
#   CORE — START / STOP A LIVE CONNECTION
# ══════════════════════════════════════════════════════════════

async def _start_live_connection(bot: Client, user_id: int, idx: int) -> str:
    """
    Start the connection using the mode saved in DB:
      auto → check if bot is in channel; use bot if yes, userbot if no
      bot  → force bot mode (on_message handler only, no task started)
      user → force userbot mode regardless of bot membership

    Returns running mode string for display.
    Raises ValueError with user-friendly message on failure.
    """
    conn = await db.get_live_connection(user_id, idx)
    if not conn:
        raise ValueError("Connection not found.")

    source_id = conn.get("source_id")
    dest_id   = conn.get("dest_id")
    if not source_id or not dest_id:
        raise ValueError("Source or Destination not set.")

    mode = conn.get("mode", "auto")
    key  = _task_key(user_id, idx)

    # Stop any existing task first
    await _stop_live_connection(user_id, idx)

    # ── BOT MODE ─────────────────────────────────────────────
    if mode == "bot":
        if not await _bot_in_channel(bot, source_id):
            raise ValueError(
                "🤖 <b>Bot Mode requires the bot to be a member/admin of the source channel.</b>\n\n"
                "Either add the bot to the source channel, or switch to 👤 User Mode or 🔄 Auto."
            )
        logger.info(f"[LiveForward] #{idx} user={user_id}: Bot Mode (forced)")
        return "🤖 Bot Mode"

    # ── USER MODE ─────────────────────────────────────────────
    if mode == "user":
        return await _launch_userbot(bot, user_id, idx, source_id, dest_id, forced=True)

    # ── AUTO MODE ─────────────────────────────────────────────
    if await _bot_in_channel(bot, source_id):
        logger.info(f"[LiveForward] #{idx} user={user_id}: Auto → Bot Mode")
        return "🤖 Bot Mode (auto)"
    return await _launch_userbot(bot, user_id, idx, source_id, dest_id, forced=False)


async def _launch_userbot(
    bot: Client, user_id: int, idx: int,
    source_id: int, dest_id: int, forced: bool
) -> str:
    """Start a userbot listener task for this connection."""
    userbot_data = await db.get_userbot(user_id)
    if not userbot_data or not userbot_data.get("session"):
        hint = "switch Mode to 🤖 Bot Mode (and add bot to channel)" if not forced else ""
        raise ValueError(
            "👤 <b>No Userbot session found.</b>\n\n"
            "Add a userbot via <b>Settings → Bots → Add Userbot</b>."
            + (f"\n\nOr {hint}." if hint else "")
        )

    key = _task_key(user_id, idx)
    userbot = await get_client(userbot_data["session"], is_bot=False)
    try:
        await userbot.start()
    except Exception as e:
        raise ValueError(f"Failed to start Userbot session: {e}")

    _userbot_clients[key] = userbot
    task = asyncio.create_task(
        _userbot_listener_task(bot, userbot, user_id, idx, source_id, dest_id)
    )
    _userbot_tasks[key] = task
    label = "👤 User Mode (forced)" if forced else "👤 User Mode (auto fallback)"
    logger.info(f"[LiveForward] #{idx} user={user_id}: {label}")
    return label


async def _stop_live_connection(user_id: int, idx: int):
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
# ══════════════════════════════════════════════════════════════

async def _userbot_listener_task(
    bot: Client, userbot: Client,
    user_id: int, idx: int,
    source_id: int, dest_id: int
):
    logger.info(f"[UBListener] Start user={user_id} idx={idx} src={source_id}")
    try:
        history = [m async for m in userbot.get_chat_history(source_id, limit=1)]
        last_id = history[0].id if history else 0
    except Exception as e:
        logger.error(f"[UBListener] Initial offset failed: {e}")
        last_id = 0

    # ✅ Pre-resolve destination peer in the userbot session so copy_message works.
    # Without this, Telegram returns CHANNEL_INVALID because the peer is unknown.
    try:
        await userbot.get_chat(dest_id)
        logger.info(f"[UBListener] Dest peer {dest_id} resolved OK")
    except Exception as e:
        logger.warning(f"[UBListener] Could not resolve dest peer {dest_id}: {e}")

    while True:
        try:
            conn = await db.get_live_connection(user_id, idx)
            if not conn or not conn.get("active"):
                logger.info(f"[UBListener] Deactivated — exiting idx={idx}")
                break

            # ✅ Collect ALL messages newer than last_id
            # Do NOT break early — fetch full batch and filter by ID.
            # This prevents missing messages when media groups have close/adjacent IDs.
            new_msgs = []
            async for msg in userbot.get_chat_history(source_id, limit=50):
                if msg.id <= last_id:
                    break   # history is newest-first; once we hit known ID, stop
                new_msgs.append(msg)

            if new_msgs:
                # Update last_id to the newest message seen
                last_id = max(m.id for m in new_msgs)

                # Process oldest-first so destination order is correct
                seen_media_groups = set()
                for msg in sorted(new_msgs, key=lambda m: m.id):
                    try:
                        # ✅ Skip duplicate media group messages —
                        # copy_message on any one message in a group copies
                        # the whole album. Sending each one individually
                        # would duplicate files in destination.
                        if msg.media_group_id:
                            if msg.media_group_id in seen_media_groups:
                                continue
                            seen_media_groups.add(msg.media_group_id)

                        await _safe_copy(userbot, msg, dest_id, user_id)
                        await asyncio.sleep(0.5)  # small delay between messages

                    except Exception as e:
                        logger.error(f"[UBListener] copy error msg={msg.id}: {e}")

            await asyncio.sleep(5)   # poll interval

        except asyncio.CancelledError:
            logger.info(f"[UBListener] Cancelled idx={idx}")
            break
        except FloodWait as fw:
            logger.warning(f"[UBListener] FloodWait {fw.value}s")
            await asyncio.sleep(fw.value)
        except Exception as e:
            logger.error(f"[UBListener] Error: {e}")
            await asyncio.sleep(10)

    logger.info(f"[UBListener] Exited idx={idx}")


# ══════════════════════════════════════════════════════════════
#   BOT on_message LISTENER (Bot Mode)
# ══════════════════════════════════════════════════════════════

@Client.on_message(filters.channel & ~filters.private)
async def live_forward_bot_listener(bot: Client, message: Message):
    """Fires when bot receives a channel post. Skips connections handled by userbot tasks."""
    source_chat_id = message.chat.id
    active_users   = await db.get_all_active_live_users()
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
            # Skip — this connection is running in user mode via task
            if _task_key(user_id, conn["index"]) in _userbot_tasks:
                continue
            try:
                # ✅ Skip non-first messages in a media group —
                # copy_message handles the whole album from the first message.
                if message.media_group_id:
                    # Only process the first message of a group
                    # (Pyrogram fires on_message once per item in the group)
                    # We use a simple temp set on temp to deduplicate.
                    mg_key = f"mg_{user_id}_{message.media_group_id}"
                    if mg_key in getattr(temp, "_mg_seen", set()):
                        continue
                    if not hasattr(temp, "_mg_seen"):
                        temp._mg_seen = set()
                    temp._mg_seen.add(mg_key)
                    # Clean up old keys to avoid memory leak
                    if len(temp._mg_seen) > 500:
                        temp._mg_seen = set(list(temp._mg_seen)[-250:])

                await _safe_copy(bot, message, dest, user_id)
            except Exception as e:
                logger.error(f"[BotListener] user={user_id} idx={conn['index']} error: {e}")


# ══════════════════════════════════════════════════════════════
#   SAFE COPY
# ══════════════════════════════════════════════════════════════

async def _safe_copy(copier: Client, message: Message, dest: int, user_id: int):
    """
    Copy a message to destination using `copier` (may be bot OR userbot).
    When called from userbot listener, copier=userbot so peer is already known.

    Key fix: preserve caption_entities so hashtags/bold/links are not stripped.
    Do NOT override caption — pass None to keep original caption+entities intact.
    """
    if getattr(message, "has_protected_content", False):
        return

    async def _do_copy():
        await copier.copy_message(
            chat_id=dest,
            from_chat_id=message.chat.id,
            message_id=message.id,
            # ✅ Do NOT pass caption= or parse_mode= here.
            # copy_message preserves the original caption + all entities
            # (hashtags, bold, links) automatically when these are omitted.
        )

    try:
        await _do_copy()

    except FloodWait as fw:
        logger.warning(f"[SafeCopy] FloodWait {fw.value}s — sleeping")
        await asyncio.sleep(fw.value)
        await _do_copy()

    except (ChatAdminRequired, ChatWriteForbidden):
        logger.warning(f"[SafeCopy] No send permission in dest {dest}")

    except (ChannelPrivate, PeerIdInvalid) as e:
        # Peer not yet in session cache — resolve both peers then retry once
        logger.warning(f"[SafeCopy] Peer unknown ({e}), resolving and retrying...")
        try:
            await copier.get_chat(dest)
            await copier.get_chat(message.chat.id)
            await _do_copy()
        except Exception as retry_err:
            logger.error(f"[SafeCopy] Retry failed for user={user_id}: {retry_err}")

    except Exception as e:
        err = str(e).lower()
        if any(k in err for k in ("copyright", "restricted", "protected", "forward")):
            logger.info(f"[SafeCopy] Copyright/restricted skip: {e}")
        else:
            logger.error(f"[SafeCopy] Unexpected error user={user_id}: {e}")


# ══════════════════════════════════════════════════════════════
#   RESTART on bot startup
# ══════════════════════════════════════════════════════════════

async def restart_live_forward_tasks(bot: Client):
    logger.info("[LiveForward] Restarting active connections...")
    active_users = await db.get_all_active_live_users()
    count = 0
    for user_id in active_users:
        conns = await db.get_live_connections(user_id)
        for conn in conns:
            if not conn.get("active"):
                continue
            idx = conn["index"]
            try:
                mode_run = await _start_live_connection(bot, user_id, idx)
                logger.info(f"[LiveForward] Resumed user={user_id} idx={idx} → {mode_run}")
                count += 1
            except Exception as e:
                logger.warning(f"[LiveForward] Could not resume user={user_id} idx={idx}: {e}")
    logger.info(f"[LiveForward] {count} connection(s) resumed.")


# ══════════════════════════════════════════════════════════════
#   CALLBACK HANDLER
# ══════════════════════════════════════════════════════════════

@Client.on_callback_query(filters.regex(r"^lf#"))
async def live_forward_cb(bot, query):
    user_id = query.from_user.id
    action  = query.data.split("#", 1)[1]

    # ── No-op ──────────────────────────────────────────────────
    if action == "noop":
        return await query.answer()

    # ── Main panel ─────────────────────────────────────────────
    if action == "panel":
        return await query.message.edit_text(
            await live_panel_text(user_id),
            reply_markup=await live_panel_buttons(user_id)
        )

    # ── Add connection ──────────────────────────────────────────
    if action == "add_conn":
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
        idx  = await db.add_live_connection(user_id)
        conn = await db.get_live_connection(user_id, idx)
        return await query.message.edit_text(
            conn_detail_text(conn, idx),
            reply_markup=conn_detail_buttons(idx, False, conn.get("mode", "auto"))
        )

    # ── Open connection detail ──────────────────────────────────
    if action.startswith("conn_"):
        idx  = int(action.split("_", 1)[1])
        conn = await db.get_live_connection(user_id, idx)
        if not conn:
            return await query.answer("Connection not found.", show_alert=True)
        return await query.message.edit_text(
            conn_detail_text(conn, idx),
            reply_markup=conn_detail_buttons(idx, conn.get("active", False), conn.get("mode", "auto"))
        )

    # ── Open mode selection panel ───────────────────────────────
    if action.startswith("mode_"):
        idx  = int(action.split("_", 1)[1])
        conn = await db.get_live_connection(user_id, idx)
        if not conn:
            return await query.answer("Connection not found.", show_alert=True)
        return await query.message.edit_text(
            mode_select_text(idx, conn.get("mode", "auto")),
            reply_markup=mode_select_buttons(idx, conn.get("mode", "auto"))
        )

    # ── Save selected mode ──────────────────────────────────────
    if action.startswith("setmode_"):
        # callback: lf#setmode_{idx}_{mode_key}
        parts    = action.split("_", 2)          # ["setmode", idx, mode_key]
        idx      = int(parts[1])
        mode_key = parts[2]                       # "auto" | "bot" | "user"
        if mode_key not in ("auto", "bot", "user"):
            return await query.answer("Invalid mode.", show_alert=True)

        await db.set_live_connection_mode(user_id, idx, mode_key)
        await query.answer(f"✅ Mode set to {MODE_LABELS[mode_key]}", show_alert=True)

        # If connection is currently active, restart it with new mode
        conn = await db.get_live_connection(user_id, idx)
        if conn and conn.get("active"):
            try:
                mode_run = await _start_live_connection(bot, user_id, idx)
                await query.answer(f"✅ Mode changed — Restarted as {mode_run}", show_alert=True)
            except ValueError as e:
                await db.set_live_connection_active(user_id, idx, False)
                await query.message.edit_text(
                    f"❌ <b>Mode change failed:</b>\n{e}\n\n"
                    f"Connection stopped. Please fix and restart.\n\n" +
                    conn_detail_text(conn, idx),
                    reply_markup=conn_detail_buttons(idx, False, mode_key)
                )
                return

        conn = await db.get_live_connection(user_id, idx)
        return await query.message.edit_text(
            mode_select_text(idx, mode_key),
            reply_markup=mode_select_buttons(idx, mode_key)
        )

    # ── Set source ──────────────────────────────────────────────
    if action.startswith("set_src_"):
        idx = int(action.split("_")[-1])
        await query.message.delete()
        msg = await bot.ask(
            user_id,
            f"<b>📤 SET SOURCE CHANNEL — Connection #{idx+1}\n\n"
            "Forward any message from the <u>source</u> channel.\n\n"
            "/cancel – cancel</b>"
        )
        conn = await db.get_live_connection(user_id, idx)
        if msg.text == "/cancel":
            return await msg.reply_text(
                conn_detail_text(conn, idx),
                reply_markup=conn_detail_buttons(idx, conn.get("active", False), conn.get("mode", "auto"))
            )
        origin   = getattr(msg, "forward_origin", None)
        fwd_chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
        if not origin or not fwd_chat:
            return await msg.reply_text(
                "⚠️ Please forward a message from the channel.\n\n" +
                conn_detail_text(conn, idx),
                reply_markup=conn_detail_buttons(idx, conn.get("active", False), conn.get("mode", "auto"))
            )
        await db.set_live_connection_source(user_id, idx, fwd_chat.id, fwd_chat.title)
        conn = await db.get_live_connection(user_id, idx)
        return await msg.reply_text(
            f"✅ <b>Source set to:</b> <code>{fwd_chat.title}</code>\n\n" +
            conn_detail_text(conn, idx),
            reply_markup=conn_detail_buttons(idx, conn.get("active", False), conn.get("mode", "auto"))
        )

    # ── Set destination ─────────────────────────────────────────
    if action.startswith("set_dst_"):
        idx = int(action.split("_")[-1])
        await query.message.delete()
        msg = await bot.ask(
            user_id,
            f"<b>📥 SET DESTINATION CHANNEL — Connection #{idx+1}\n\n"
            "Forward any message from the <u>destination</u> channel.\n\n"
            "/cancel – cancel</b>"
        )
        conn = await db.get_live_connection(user_id, idx)
        if msg.text == "/cancel":
            return await msg.reply_text(
                conn_detail_text(conn, idx),
                reply_markup=conn_detail_buttons(idx, conn.get("active", False), conn.get("mode", "auto"))
            )
        origin   = getattr(msg, "forward_origin", None)
        fwd_chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
        if not origin or not fwd_chat:
            return await msg.reply_text(
                "⚠️ Please forward a message from the channel.\n\n" +
                conn_detail_text(conn, idx),
                reply_markup=conn_detail_buttons(idx, conn.get("active", False), conn.get("mode", "auto"))
            )
        await db.set_live_connection_dest(user_id, idx, fwd_chat.id, fwd_chat.title)
        conn = await db.get_live_connection(user_id, idx)
        return await msg.reply_text(
            f"✅ <b>Destination set to:</b> <code>{fwd_chat.title}</code>\n\n" +
            conn_detail_text(conn, idx),
            reply_markup=conn_detail_buttons(idx, conn.get("active", False), conn.get("mode", "auto"))
        )

    # ── Start ───────────────────────────────────────────────────
    if action.startswith("start_"):
        idx  = int(action.split("_", 1)[1])
        conn = await db.get_live_connection(user_id, idx)
        if not conn:
            return await query.answer("Connection not found.", show_alert=True)
        if not conn.get("source_id"):
            return await query.answer("⚠️ Set a SOURCE channel first!", show_alert=True)
        if not conn.get("dest_id"):
            return await query.answer("⚠️ Set a DESTINATION channel first!", show_alert=True)

        try:
            mode_run = await _start_live_connection(bot, user_id, idx)
        except ValueError as e:
            return await query.message.edit_text(
                f"❌ <b>Could not start:</b>\n{e}\n\n" + conn_detail_text(conn, idx),
                reply_markup=conn_detail_buttons(idx, False, conn.get("mode", "auto"))
            )

        await db.set_live_connection_active(user_id, idx, True)
        conn = await db.get_live_connection(user_id, idx)
        await query.answer(f"✅ STARTED — {mode_run}", show_alert=True)
        return await query.message.edit_text(
            conn_detail_text(conn, idx),
            reply_markup=conn_detail_buttons(idx, True, conn.get("mode", "auto"))
        )

    # ── Stop ────────────────────────────────────────────────────
    if action.startswith("stop_"):
        idx = int(action.split("_", 1)[1])
        await _stop_live_connection(user_id, idx)
        await db.set_live_connection_active(user_id, idx, False)
        conn = await db.get_live_connection(user_id, idx)
        await query.answer("⏹ Live Forward STOPPED.", show_alert=True)
        return await query.message.edit_text(
            conn_detail_text(conn, idx),
            reply_markup=conn_detail_buttons(idx, False, conn.get("mode", "auto"))
        )

    # ── Delete ──────────────────────────────────────────────────
    if action.startswith("del_conn_"):
        idx = int(action.split("_")[-1])
        await _stop_live_connection(user_id, idx)
        await db.delete_live_connection(user_id, idx)
        await query.answer("🗑 Connection deleted.", show_alert=True)
        return await query.message.edit_text(
            await live_panel_text(user_id),
            reply_markup=await live_panel_buttons(user_id)
        )

    # ── Premium upsell ──────────────────────────────────────────
    if action == "buy_premium":
        return await query.message.edit_text(
            "⭐ <b>UPGRADE TO PREMIUM</b>\n\n"
            "With Premium you get:\n"
            "• Up to <b>10 live forward connections</b>\n"
            "• Each connection has its own Mode, Source & Destination\n"
            "• 🔄 Auto / 🤖 Bot / 👤 User per connection\n\n"
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
            "Each connection has its own 🔄 Auto / 🤖 Bot / 👤 User mode.\n"
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
