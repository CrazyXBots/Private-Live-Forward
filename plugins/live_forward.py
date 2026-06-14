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

# ══════════════════════════════════════════════════════════════
#   CONSTANTS
# ══════════════════════════════════════════════════════════════

FREE_MAX_CONNECTIONS    = 1    # free users can have 1 source→destination pair
PREMIUM_MAX_CONNECTIONS = 10   # premium users can have up to 10 pairs


# ══════════════════════════════════════════════════════════════
#   HELPERS — premium check & connection limit
# ══════════════════════════════════════════════════════════════

async def _is_premium(user_id: int) -> bool:
    return await db.is_premium_user(user_id)


async def _max_connections(user_id: int) -> int:
    return PREMIUM_MAX_CONNECTIONS if await _is_premium(user_id) else FREE_MAX_CONNECTIONS


# ══════════════════════════════════════════════════════════════
#   PANEL TEXT — overview of all connections
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
        for i, c in enumerate(conns, 1):
            src  = c.get("source_title")  or "❌ Not Set"
            dst  = c.get("dest_title")    or "❌ Not Set"
            sts  = "🟢" if c.get("active") else "🔴"
            lines.append(
                f"\n<b>#{i}</b> {sts}\n"
                f"  📤 <b>Source:</b> {src}\n"
                f"  📥 <b>Dest:</b>   {dst}"
            )
    else:
        lines.append("\n<i>No connections yet. Tap ➕ Add Connection to start.</i>")

    if not premium:
        lines.append(
            "\n\n<i>💡 Upgrade to ⭐ Premium to add up to 10 connections!</i>"
        )
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
#   BUTTONS — main panel
# ══════════════════════════════════════════════════════════════

async def live_panel_buttons(user_id: int) -> InlineKeyboardMarkup:
    conns   = await db.get_live_connections(user_id)
    max_c   = await _max_connections(user_id)
    premium = await _is_premium(user_id)
    btns    = []

    # One row per existing connection
    for i, c in enumerate(conns):
        idx  = c["index"]
        src  = (c.get("source_title") or "No Source")[:20]
        dst  = (c.get("dest_title")   or "No Dest")[:20]
        sts  = "🟢" if c.get("active") else "🔴"
        btns.append([InlineKeyboardButton(
            f"{sts} #{idx+1}  {src} ➜ {dst}",
            callback_data=f"lf#conn_{idx}"
        )])

    # Add connection button (or premium upsell)
    if len(conns) < max_c:
        btns.append([InlineKeyboardButton("➕ ADD CONNECTION", callback_data="lf#add_conn")])
    elif not premium:
        btns.append([InlineKeyboardButton(
            "⭐ UPGRADE TO PREMIUM — Add up to 10 Connections",
            callback_data="lf#buy_premium"
        )])
    else:
        btns.append([InlineKeyboardButton("✅ Maximum 10 Connections Reached", callback_data="lf#noop")])

    btns.append([InlineKeyboardButton("⫷ BACK", callback_data="settings#main")])
    return InlineKeyboardMarkup(btns)


# ══════════════════════════════════════════════════════════════
#   BUTTONS — single connection detail panel
# ══════════════════════════════════════════════════════════════

def conn_detail_buttons(idx: int, active: bool) -> InlineKeyboardMarkup:
    toggle = "⏹ STOP LIVE" if active else "▶️ START LIVE"
    toggle_cb = f"lf#stop_{idx}" if active else f"lf#start_{idx}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 SET SOURCE CHANNEL",      callback_data=f"lf#set_src_{idx}")],
        [InlineKeyboardButton("📥 SET DESTINATION CHANNEL", callback_data=f"lf#set_dst_{idx}")],
        [
            InlineKeyboardButton(toggle, callback_data=toggle_cb),
            InlineKeyboardButton("🗑 DELETE",  callback_data=f"lf#del_conn_{idx}"),
        ],
        [InlineKeyboardButton("⫷ BACK", callback_data="lf#panel")],
    ])


def conn_detail_text(c: dict, idx: int) -> str:
    src    = c.get("source_title")  or "❌ Not Set"
    dst    = c.get("dest_title")    or "❌ Not Set"
    status = "🟢 ACTIVE" if c.get("active") else "🔴 INACTIVE"
    return (
        f"📡 <b>CONNECTION #{idx+1}</b>\n\n"
        f"<b>STATUS :</b> {status}\n"
        f"<b>📤 SOURCE :</b> {src}\n"
        f"<b>📥 DESTINATION :</b> {dst}\n\n"
        f"<i>New messages from SOURCE will be copied to\n"
        f"DESTINATION in real time (copyright safe).</i>"
    )


# ══════════════════════════════════════════════════════════════
#   MAIN CALLBACK HANDLER
# ══════════════════════════════════════════════════════════════

@Client.on_callback_query(filters.regex(r"^lf#"))
async def live_forward_cb(bot, query):
    user_id = query.from_user.id
    action  = query.data.split("#", 1)[1]
    back_to_panel = [[InlineKeyboardButton("⫷ BACK", callback_data="lf#panel")]]

    # ── No-op (disabled button) ─────────────────────────────
    if action == "noop":
        return await query.answer()

    # ── Main panel ──────────────────────────────────────────
    if action == "panel":
        await query.message.edit_text(
            await live_panel_text(user_id),
            reply_markup=await live_panel_buttons(user_id)
        )

    # ── Add new connection ───────────────────────────────────
    elif action == "add_conn":
        conns  = await db.get_live_connections(user_id)
        max_c  = await _max_connections(user_id)
        premium = await _is_premium(user_id)

        if len(conns) >= max_c:
            if not premium:
                return await query.answer(
                    "⭐ Upgrade to Premium to add more than 1 connection!",
                    show_alert=True
                )
            return await query.answer("Maximum 10 connections reached.", show_alert=True)

        idx = await db.add_live_connection(user_id)
        c   = (await db.get_live_connections(user_id))[idx]
        await query.message.edit_text(
            conn_detail_text(c, idx),
            reply_markup=conn_detail_buttons(idx, c.get("active", False))
        )

    # ── Open connection detail ───────────────────────────────
    elif action.startswith("conn_"):
        idx  = int(action.split("_", 1)[1])
        conn = await db.get_live_connection(user_id, idx)
        if conn is None:
            return await query.answer("Connection not found.", show_alert=True)
        await query.message.edit_text(
            conn_detail_text(conn, idx),
            reply_markup=conn_detail_buttons(idx, conn.get("active", False))
        )

    # ── Set source channel ───────────────────────────────────
    elif action.startswith("set_src_"):
        idx = int(action.split("_")[-1])
        await query.message.delete()
        msg = await bot.ask(
            user_id,
            f"<b>📤 SET SOURCE CHANNEL — Connection #{idx+1}\n\n"
            "Forward any message from the <u>source</u> channel.\n"
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

    # ── Set destination channel ──────────────────────────────
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

    # ── Start connection ─────────────────────────────────────
    elif action.startswith("start_"):
        idx  = int(action.split("_", 1)[1])
        conn = await db.get_live_connection(user_id, idx)
        if not conn:
            return await query.answer("Connection not found.", show_alert=True)
        if not conn.get("source_id"):
            return await query.answer("⚠️ Set a SOURCE channel first!", show_alert=True)
        if not conn.get("dest_id"):
            return await query.answer("⚠️ Set a DESTINATION channel first!", show_alert=True)
        await db.set_live_connection_active(user_id, idx, True)
        conn = await db.get_live_connection(user_id, idx)
        await query.answer("✅ Live Forward STARTED!", show_alert=True)
        await query.message.edit_text(
            conn_detail_text(conn, idx),
            reply_markup=conn_detail_buttons(idx, True)
        )

    # ── Stop connection ──────────────────────────────────────
    elif action.startswith("stop_"):
        idx  = int(action.split("_", 1)[1])
        await db.set_live_connection_active(user_id, idx, False)
        conn = await db.get_live_connection(user_id, idx)
        await query.answer("⏹ Live Forward STOPPED.", show_alert=True)
        await query.message.edit_text(
            conn_detail_text(conn, idx),
            reply_markup=conn_detail_buttons(idx, False)
        )

    # ── Delete connection ────────────────────────────────────
    elif action.startswith("del_conn_"):
        idx = int(action.split("_")[-1])
        await db.delete_live_connection(user_id, idx)
        await query.answer("🗑 Connection deleted.", show_alert=True)
        await query.message.edit_text(
            await live_panel_text(user_id),
            reply_markup=await live_panel_buttons(user_id)
        )

    # ── Buy premium upsell ───────────────────────────────────
    elif action == "buy_premium":
        await query.message.edit_text(
            "⭐ <b>UPGRADE TO PREMIUM</b>\n\n"
            "With Premium you get:\n"
            "• Up to <b>10 live forward connections</b>\n"
            "• Each connection has its own Source ➜ Destination\n"
            "• All connections run simultaneously\n\n"
            "Contact the bot owner to purchase premium:\n"
            f"👤 <a href='tg://user?id={Config.BOT_OWNER}'>Click here to contact</a>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 Contact Owner", url=f"tg://user?id={Config.BOT_OWNER}")],
                [InlineKeyboardButton("⫷ BACK", callback_data="lf#panel")]
            ]),
            disable_web_page_preview=True
        )


# ══════════════════════════════════════════════════════════════
#   ADMIN: Grant / Revoke premium  (/grantpremium /revokepremium)
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
            "⭐ <b>Congratulations!</b>\nYou have been upgraded to <b>Premium</b>!\n"
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


# ══════════════════════════════════════════════════════════════
#   LIVE MESSAGE LISTENER
#   Fires on every channel post the bot can see.
# ══════════════════════════════════════════════════════════════

@Client.on_message(filters.channel & ~filters.private)
async def live_forward_listener(bot: Client, message: Message):
    """
    COPYRIGHT PROTECTION STRATEGY
    ──────────────────────────────
    • copy_message() re-sends content as a FRESH post with NO
      "Forwarded from …" tag — breaks the Telegram copyright chain.
    • has_protected_content messages are silently skipped.
    • FloodWait is caught and retried automatically.
    • All copyright/restricted errors are logged and skipped.
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
            try:
                await _safe_copy(bot, message, dest, user_id)
            except Exception as e:
                logger.error(f"[LiveForward] user={user_id} conn={conn['index']} error: {e}")


async def _safe_copy(bot: Client, message: Message, dest: int, user_id: int):
    """Copy message to destination — copyright safe."""

    if getattr(message, "has_protected_content", False):
        logger.info(f"[LiveForward] Skipping protected msg from {message.chat.id}")
        return

    caption = message.caption  # original caption, no "Forwarded from" tag

    try:
        # ✅ COPYRIGHT SAFE — copy_message strips the forward origin
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
            parse_mode=enums.ParseMode.HTML if caption else enums.ParseMode.DISABLED
        )

    except (ChatAdminRequired, ChatWriteForbidden):
        logger.warning(f"[LiveForward] Bot lacks permission in dest {dest}")

    except ChannelPrivate:
        logger.warning(f"[LiveForward] Cannot access channel for user {user_id}")

    except Exception as e:
        err = str(e).lower()
        if any(k in err for k in ("copyright", "restricted", "protected", "forward")):
            logger.info(f"[LiveForward] Copyright/restricted skip: {e}")
        else:
            raise

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
