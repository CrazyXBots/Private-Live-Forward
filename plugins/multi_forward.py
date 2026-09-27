# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import re
import math
import time
import asyncio
import logging

from database import db
from config import Config, temp
from script import Script
from plugins.utils import STS
from plugins.test import get_client, parse_buttons, iter_messages
from plugins.regix import (
    copy, forward, msg_edit, custom_caption, media,
    keyword_filter, extension_filter, size_filter,
    get_size, TimeFormatter, get_bot_uptime, complete_time
)

from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Message
)
from pyrogram.errors import (
    FloodWait, MessageNotModified,
    ChannelInvalid, ChannelPrivate, ChatAdminRequired,
    UsernameInvalid, UsernameNotModified
)
from pyrogram.errors.exceptions.not_acceptable_406 import ChannelPrivate as PrivateChat

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ══════════════════════════════════════════════════════════════
#   CONSTANTS
# ══════════════════════════════════════════════════════════════

FREE_MAX_TASKS    = 1
PREMIUM_MAX_TASKS = 10

# ══════════════════════════════════════════════════════════════
#   HELPERS
# ══════════════════════════════════════════════════════════════

async def _max_tasks(user_id: int) -> int:
    return PREMIUM_MAX_TASKS if await db.is_premium_user(user_id) else FREE_MAX_TASKS


def _make_task_id(user_id: int, msg_id: int) -> str:
    return f"{user_id}-T{msg_id}"


# ══════════════════════════════════════════════════════════════
#   TASK PANEL — /tasks command
# ══════════════════════════════════════════════════════════════

async def tasks_panel_text(user_id: int) -> str:
    tasks   = await db.get_all_tasks(user_id)
    premium = await db.is_premium_user(user_id)
    max_t   = PREMIUM_MAX_TASKS if premium else FREE_MAX_TASKS
    plan    = "⭐ PREMIUM" if premium else "🆓 FREE"
    active  = [t for t in tasks if t.get("active")]

    lines = [
        f"📋 <b>FORWARD TASKS</b>  |  {plan}\n",
        f"<b>Running:</b> {len(active)} / {max_t}\n",
    ]
    if tasks:
        lines.append("─────────────────────────")
        for t in tasks:
            tid   = t["task_id"]
            sts   = "🟢" if t.get("active") else "🔴"
            src   = t.get("from_title", str(t.get("chat_id", "?")))[:18]
            dst   = t.get("to_title",   str(t.get("toid", "?")))[:18]
            pct   = 0
            if t.get("limit") and t.get("limit") > 0:
                pct = int(float(t.get("fetched", 0)) * 100 / float(t.get("limit", 1)))
            lines.append(
                f"\n{sts} <b>{tid}</b>\n"
                f"  📤 {src} ➜ {dst}\n"
                f"  📊 {pct}% done"
            )
    else:
        lines.append("\n<i>No tasks. Use /forward to start one.</i>")

    if not premium and len(active) >= FREE_MAX_TASKS:
        lines.append("\n\n<i>⭐ Upgrade to Premium to run up to 10 tasks at once!</i>")
    return "\n".join(lines)


async def tasks_panel_buttons(user_id: int) -> InlineKeyboardMarkup:
    tasks = await db.get_all_tasks(user_id)
    btns  = []
    for t in tasks:
        tid  = t["task_id"]
        sts  = "🟢" if t.get("active") else "🔴"
        src  = t.get("from_title", "?")[:14]
        dst  = t.get("to_title", "?")[:14]
        btns.append([InlineKeyboardButton(
            f"{sts} {src} ➜ {dst}",
            callback_data=f"mft#detail_{tid}"
        )])
    btns.append([InlineKeyboardButton("🔄 REFRESH", callback_data="mft#refresh")])
    return InlineKeyboardMarkup(btns)


@Client.on_message(filters.private & filters.command(["tasks"]))
async def tasks_command(bot, message):
    user_id = message.from_user.id
    await message.reply_text(
        await tasks_panel_text(user_id),
        reply_markup=await tasks_panel_buttons(user_id)
    )


# ══════════════════════════════════════════════════════════════
#   TASK DETAIL + CONTROL BUTTONS
# ══════════════════════════════════════════════════════════════

def task_detail_text(t: dict) -> str:
    tid    = t["task_id"]
    sts    = "🟢 RUNNING" if t.get("active") else "🔴 STOPPED"
    src    = t.get("from_title", str(t.get("chat_id", "?")))
    dst    = t.get("to_title",   str(t.get("toid", "?")))
    fetch  = t.get("fetched", 0)
    total  = t.get("limit", 0)
    fwd    = t.get("total_files", 0)
    dup    = t.get("duplicate", 0)
    deld   = t.get("deleted", 0)
    skip   = t.get("skip", 0)
    filt   = t.get("filtered", 0)
    pct    = int(float(fetch) * 100 / float(total)) if total > 0 else 0

    # Live speed/ETA only exist while the task's coroutine is running in this
    # process (STS is in-memory). After a restart, before the task resumes,
    # there's nothing live to show yet.
    live = STS(tid)
    if t.get("active") and live.verify():
        speed = live.speed_per_min()
        speed_line = f"<b>🚀 Speed :</b> <code>{speed:.1f} msg/min</code>\n" if speed > 0 else "<b>🚀 Speed :</b> <code>calculating…</code>\n"
        eta_line = f"<b>⏳ ETA :</b> <code>{live.eta_string()}</code>\n"
    else:
        speed_line = ""
        eta_line = ""

    return (
        f"📋 <b>TASK: {tid}</b>\n\n"
        f"<b>STATUS :</b> {sts}\n"
        f"<b>📤 SOURCE :</b> {src}\n"
        f"<b>📥 DEST :</b> {dst}\n\n"
        f"<b>🕵 Fetched :</b> <code>{fetch}</code>\n"
        f"<b>✅ Forwarded :</b> <code>{fwd}</code>\n"
        f"<b>👥 Duplicate :</b> <code>{dup}</code>\n"
        f"<b>🗑 Deleted :</b> <code>{deld}</code>\n"
        f"<b>🪆 Skipped :</b> <code>{skip}</code>\n"
        f"<b>🔁 Filtered :</b> <code>{filt}</code>\n"
        f"{speed_line}{eta_line}"
        f"<b>📊 Progress :</b> <code>{pct}%</code>"
    )


def task_detail_buttons(task_id: str, active: bool, paused: bool = False) -> InlineKeyboardMarkup:
    btns = []
    if active:
        pause_label = "▶️ RESUME" if paused else "⏸ PAUSE"
        pause_cb    = f"mft#resume_{task_id}" if paused else f"mft#pause_{task_id}"
        btns.append([
            InlineKeyboardButton(pause_label, callback_data=pause_cb),
            InlineKeyboardButton("⏹ CANCEL",  callback_data=f"mft#cancel_{task_id}"),
        ])
    btns.append([
        InlineKeyboardButton("🗑 DELETE",   callback_data=f"mft#delete_{task_id}"),
        InlineKeyboardButton("🔄 REFRESH",  callback_data=f"mft#detail_{task_id}"),
    ])
    btns.append([InlineKeyboardButton("⫷ BACK", callback_data="mft#refresh")])
    return InlineKeyboardMarkup(btns)


# ══════════════════════════════════════════════════════════════
#   CALLBACK HANDLER
# ══════════════════════════════════════════════════════════════

@Client.on_callback_query(filters.regex(r"^mft#"))
async def multi_task_cb(bot, query):
    user_id = query.from_user.id
    action  = query.data.split("#", 1)[1]

    if user_id != Config.BOT_OWNER and not await db.is_feature_enabled("multi_forward_enabled"):
        return await query.answer(
            "🚫 Multi Forward is currently disabled by the admin.",
            show_alert=True
        )

    # ── Refresh main panel ─────────────────────────────────────
    if action in ("refresh", "panel"):
        return await query.message.edit_text(
            await tasks_panel_text(user_id),
            reply_markup=await tasks_panel_buttons(user_id)
        )

    # ── Task detail ────────────────────────────────────────────
    if action.startswith("detail_"):
        task_id = action[7:]
        t = await db.get_task(user_id, task_id)
        if not t:
            return await query.answer("Task not found.", show_alert=True)
        paused = temp.is_paused(user_id, task_id)
        return await query.message.edit_text(
            task_detail_text(t),
            reply_markup=task_detail_buttons(task_id, t.get("active", False), paused)
        )

    # ── Pause ──────────────────────────────────────────────────
    if action.startswith("pause_"):
        task_id = action[6:]
        temp.pause_task(user_id, task_id)
        await query.answer("⏸ Task Paused!", show_alert=True)
        t = await db.get_task(user_id, task_id)
        if t:
            return await query.message.edit_reply_markup(
                task_detail_buttons(task_id, t.get("active", False), paused=True)
            )

    # ── Resume ─────────────────────────────────────────────────
    if action.startswith("resume_"):
        task_id = action[7:]
        temp.resume_task(user_id, task_id)
        await query.answer("▶️ Task Resumed!", show_alert=True)
        t = await db.get_task(user_id, task_id)
        if t:
            return await query.message.edit_reply_markup(
                task_detail_buttons(task_id, t.get("active", False), paused=False)
            )

    # ── Cancel ─────────────────────────────────────────────────
    if action.startswith("cancel_"):
        task_id = action[7:]
        temp.cancel_task(user_id, task_id)
        await query.answer("❌ Cancelling task...", show_alert=True)
        t = await db.get_task(user_id, task_id)
        if t:
            return await query.message.edit_text(
                task_detail_text(t),
                reply_markup=task_detail_buttons(task_id, False)
            )

    # ── Delete ─────────────────────────────────────────────────
    if action.startswith("delete_"):
        task_id = action[7:]
        temp.cancel_task(user_id, task_id)
        await db.remove_task(user_id, task_id)
        await query.answer("🗑 Task deleted.", show_alert=True)
        return await query.message.edit_text(
            await tasks_panel_text(user_id),
            reply_markup=await tasks_panel_buttons(user_id)
        )

    # ── Premium upsell ─────────────────────────────────────────
    if action == "buy_premium":
        return await query.message.edit_text(
            "⭐ <b>UPGRADE TO PREMIUM</b>\n\n"
            "Run up to <b>10 forward tasks simultaneously</b>!\n\n"
            f"👤 <a href='tg://user?id={Config.BOT_OWNER}'>Contact owner</a>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 Contact Owner", url=f"tg://user?id={Config.BOT_OWNER}")],
                [InlineKeyboardButton("⫷ BACK", callback_data="mft#refresh")]
            ]),
            disable_web_page_preview=True
        )


# ══════════════════════════════════════════════════════════════
#   /forward COMMAND — multi-task aware
# ══════════════════════════════════════════════════════════════

@Client.on_message(filters.private & filters.command(["forward"]))
async def run_multi(bot, message):
    user_id  = message.from_user.id
    max_t    = await _max_tasks(user_id)
    active_n = temp.active_task_count(user_id)

    if active_n >= max_t:
        premium = await db.is_premium_user(user_id)
        if not premium:
            return await message.reply_text(
                f"⚠️ You can only run <b>{FREE_MAX_TASKS} task</b> at a time on the free plan.\n\n"
                "⭐ Upgrade to <b>Premium</b> to run up to 10 tasks simultaneously!\n\n"
                f"👤 <a href='tg://user?id={Config.BOT_OWNER}'>Contact owner to upgrade</a>",
                disable_web_page_preview=True
            )
        return await message.reply_text(
            f"⚠️ You already have <b>{active_n} tasks</b> running (max {max_t}).\n"
            "Cancel one with /tasks before starting a new one."
        )

    _bot = await db.get_bot(user_id)
    if not _bot:
        _bot = await db.get_userbot(user_id)
        if not _bot:
            return await message.reply("<code>You didn't added any bot. Please add a bot using /settings!</code>")

    channels = await db.get_user_channels(user_id)
    if not channels:
        return await message.reply_text("Please set a destination channel in /settings before forwarding.")

    # ── Choose destination ─────────────────────────────────────
    if len(channels) > 1:
        buttons  = [[KeyboardButton(c["title"])] for c in channels]
        btn_data = {c["title"]: c["chat_id"] for c in channels}
        buttons.append([KeyboardButton("cancel")])
        _toid = await bot.ask(
            message.chat.id,
            Script.TO_MSG.format(_bot["name"], _bot["username"]),
            reply_markup=ReplyKeyboardMarkup(buttons, one_time_keyboard=True, resize_keyboard=True)
        )
        if _toid.text.startswith(("/", "cancel")):
            return await message.reply_text(Script.CANCEL, reply_markup=ReplyKeyboardRemove())
        toid      = btn_data.get(_toid.text)
        to_title  = _toid.text
        if not toid:
            return await message.reply_text("Wrong channel chosen!", reply_markup=ReplyKeyboardRemove())
    else:
        toid     = channels[0]["chat_id"]
        to_title = channels[0]["title"]

    # ── Choose source ──────────────────────────────────────────
    fromid = await bot.ask(message.chat.id, Script.FROM_MSG, reply_markup=ReplyKeyboardRemove())
    if fromid.text and fromid.text.startswith("/"):
        return await message.reply(Script.CANCEL)

    # Parse link or forwarded message
    chat_id, last_msg_id, from_title = await _parse_source(bot, fromid, message)
    if chat_id is None:
        return  # error already sent

    # ── Skip number ────────────────────────────────────────────
    skipno = await bot.ask(message.chat.id, Script.SKIP_MSG)
    if skipno.text.startswith("/"):
        return await message.reply(Script.CANCEL)

    task_id   = _make_task_id(user_id, skipno.id)
    buttons   = [[
        InlineKeyboardButton("Yes ✅", callback_data=f"mft_start#{task_id}"),
        InlineKeyboardButton("No ❌",  callback_data="close_btn")
    ]]
    await message.reply_text(
        text=Script.DOUBLE_CHECK.format(
            botname=_bot["name"], botuname=_bot["username"],
            from_chat=from_title, to_chat=to_title, skip=skipno.text
        ),
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    # Store STS for the forward engine
    STS(task_id).store(chat_id, toid, int(skipno.text), int(last_msg_id))

    # Save pending task to DB so it survives restart confirmation
    await db.add_task(user_id, {
        "task_id":    task_id,
        "active":     False,
        "chat_id":    chat_id if isinstance(chat_id, int) else str(chat_id),
        "toid":       toid,
        "from_title": from_title,
        "to_title":   to_title,
        "skip":       int(skipno.text),
        "limit":      int(last_msg_id),
        "fetched":    0,
        "offset":     int(skipno.text),
        "deleted":    0,
        "total_files":0,
        "duplicate":  0,
        "filtered":   0,
        "msg_id":     None,
        "start_time": None,
    })


async def _parse_source(bot, fromid, message):
    """Parse source from link or forwarded message. Returns (chat_id, last_msg_id, title)."""
    if fromid.text and not getattr(fromid, "forward_origin", None):
        link    = fromid.text.strip().replace("?single", "")
        private = re.search(r"(?:https?://)?t\.me/c/(\d+)/(\d+)", link)
        public  = re.search(r"(?:https?://)?t\.me/([A-Za-z0-9_]+)/(\d+)", link)
        if private:
            chat_id     = int("-100" + private.group(1))
            last_msg_id = int(private.group(2))
        elif public:
            chat_id     = public.group(1)
            last_msg_id = int(public.group(2))
        else:
            await message.reply("❌ Invalid Telegram link")
            return None, None, None
    else:
        origin   = getattr(fromid, "forward_origin", None)
        fwd_chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
        if not origin or not fwd_chat:
            await message.reply("❌ Invalid input — forward a message or send a link")
            return None, None, None
        last_msg_id = getattr(origin, "message_id", None)
        if not last_msg_id:
            await message.reply("❌ Anonymous admin message — send the post LINK instead.")
            return None, None, None
        chat_id = fwd_chat.username or fwd_chat.id

    try:
        title = (await bot.get_chat(chat_id)).title
    except (PrivateChat, ChannelPrivate, ChannelInvalid):
        title = "private"
    except (UsernameInvalid, UsernameNotModified):
        await message.reply("Invalid link specified.")
        return None, None, None
    except Exception as e:
        await message.reply(f"Error: {e}")
        return None, None, None

    return chat_id, last_msg_id, title


# ══════════════════════════════════════════════════════════════
#   START TASK CALLBACK — fires when user clicks Yes
# ══════════════════════════════════════════════════════════════

@Client.on_callback_query(filters.regex(r"^mft_start#"))
async def start_task_cb(bot, query):
    user_id = query.from_user.id
    task_id = query.data.split("#", 1)[1]

    max_t    = await _max_tasks(user_id)
    active_n = temp.active_task_count(user_id)
    if active_n >= max_t:
        return await query.answer(
            f"⚠️ Max {max_t} tasks running. Cancel one first.",
            show_alert=True
        )

    sts = STS(task_id)
    if not sts.verify():
        await query.answer("Session expired. Run /forward again.", show_alert=True)
        return await query.message.delete()

    t = await db.get_task(user_id, task_id)
    if not t:
        return await query.answer("Task data not found.", show_alert=True)

    toid = sts.get("TO")
    if toid in [x[2] for x in temp.IS_FRWD_CHAT]:
        return await query.answer(
            "A task is already running to that destination. Wait for it to finish.",
            show_alert=True
        )

    m = await query.message.edit_text("<code>Verifying your data, please wait…</code>")

    _bot, caption, forward_tag, datas, protect, button = await sts.get_data(user_id)
    if not _bot:
        return await msg_edit(m, "<code>No bot found. Please add a bot using /settings!</code>", wait=True)

    data  = _bot["token"] if _bot["is_bot"] else _bot["session"]
    is_b  = _bot["is_bot"]
    try:
        client = await get_client(data, is_bot=is_b)
        await client.start()
    except Exception as e:
        return await m.edit(str(e))

    try:
        await client.get_messages(sts.get("FROM"), sts.get("limit"))
    except Exception:
        await msg_edit(
            m,
            f"**Source is private. Make your [{_bot['username']}](t.me/{_bot['username']}) admin there or use userbot.**",
            InlineKeyboardMarkup([[InlineKeyboardButton("♻️ RETRY", f"mft_start#{task_id}")]]),
            True
        )
        return await _task_stop(client, user_id, task_id)

    try:
        k = await client.send_message(toid, "Testing")
        await k.delete()
    except Exception:
        await msg_edit(
            m,
            f"**Make your [{_bot['username']}](t.me/{_bot['username']}) admin in destination channel.**",
            InlineKeyboardMarkup([[InlineKeyboardButton("♻️ RETRY", f"mft_start#{task_id}")]]),
            True
        )
        return await _task_stop(client, user_id, task_id)

    # Mark active
    temp.set_task(user_id, task_id)
    temp.IS_FRWD_CHAT.append((user_id, task_id, toid))
    temp.forwardings += 1
    sts.add(time=True)

    await db.update_task(user_id, task_id, {"active": True, "msg_id": m.id, "start_time": time.time()})
    await query.answer(f"✅ Task {task_id} started!")

    # Launch as independent asyncio task
    asyncio.create_task(
        _run_forward_task(bot, client, user_id, task_id, m, sts, datas, caption, forward_tag, protect, button)
    )


# ══════════════════════════════════════════════════════════════
#   CORE FORWARD TASK — runs in background asyncio.Task
# ══════════════════════════════════════════════════════════════

async def _run_forward_task(
    bot, client, user_id, task_id, m, sts,
    datas, caption, forward_tag, protect, button
):
    filter    = datas["filters"]
    max_size  = datas["max_size"]
    min_size  = datas["min_size"]
    keywords  = _join_filter(datas["keywords"])
    exts      = _join_filter(datas["extensions"])
    dup_files = []

    user_have_db = False
    dburi = datas.get("db_uri")
    if dburi:
        try:
            from plugins.db import connect_user_db
            connected, user_db = await connect_user_db(user_id, dburi, sts.get("TO"))
            user_have_db = connected
        except Exception:
            pass

    try:
        MSG  = []
        pling = 0
        await _edit_task(user_id, task_id, m, "ᴘʀᴏɢʀᴇssɪɴɢ", 5, sts)
        async for message in iter_messages(
            client,
            chat_id=sts.get("FROM"),
            limit=sts.get("limit"),
            offset=sts.get("skip"),
            filters=filter,
            max_size=max_size
        ):
            # ── Pause loop ────────────────────────────────────
            while temp.is_paused(user_id, task_id):
                if temp.is_cancelled(user_id, task_id):
                    break
                await asyncio.sleep(2)

            # ── Cancel check ──────────────────────────────────
            if temp.is_cancelled(user_id, task_id):
                await _edit_task(user_id, task_id, m, "ᴄᴀɴᴄᴇʟʟᴇᴅ", "cancelled", sts)
                await bot.send_message(user_id, f"<b>❌ Task {task_id} cancelled.</b>")
                if user_have_db:
                    await user_db.drop_all(); await user_db.close()
                return await _task_stop(client, user_id, task_id)

            if pling % 20 == 0:
                await _edit_task(user_id, task_id, m, "ᴘʀᴏɢʀᴇssɪɴɢ", 5, sts)
            pling += 1
            sts.add("fetched")

            if message == "DUPLICATE":   sts.add("duplicate");  continue
            elif message == "FILTERED":  sts.add("filtered");   continue
            elif message.empty or message.service: sts.add("deleted"); continue
            elif message.document and await extension_filter(exts, message.document.file_name):
                sts.add("filtered"); continue
            elif message.document and await keyword_filter(keywords, message.document.file_name):
                sts.add("filtered"); continue
            elif message.document and await size_filter(max_size, min_size, message.document.file_size):
                sts.add("filtered"); continue
            elif message.document and message.document.file_id in dup_files:
                sts.add("duplicate"); continue

            if message.document and datas["skip_duplicate"]:
                dup_files.append(message.document.file_id)
                if user_have_db:
                    await user_db.add_file(message.document.file_id)

            if forward_tag:
                MSG.append(message.id)
                notcompleted = len(MSG)
                completed    = sts.get("total") - sts.get("fetched")
                if notcompleted >= 100 or completed <= 100:
                    await forward(user_id, client, MSG, m, sts, protect)
                    sts.add("total_files", notcompleted)
                    MSG = []
            else:
                new_caption = custom_caption(message, caption)
                details = {
                    "msg_id": message.id, "media": media(message),
                    "caption": new_caption, "button": button, "protect": protect
                }
                await copy(user_id, client, details, m, sts)
                sts.add("total_files")
                speed = await db.get_speed(user_id) or 20
                await asyncio.sleep(60 / speed)

            # ── Persist progress every 20 messages ────────────
            if pling % 20 == 0:
                i = sts.get(full=True)
                await db.update_task(user_id, task_id, {
                    "fetched":     i.fetched,
                    "offset":      i.fetched,
                    "total_files": i.total_files,
                    "duplicate":   i.duplicate,
                    "deleted":     i.deleted,
                    "filtered":    i.filtered,
                })

    except Exception as e:
        await msg_edit(m, f"<b>ERROR:</b>\n<code>{e}</code>", wait=True)
        logger.error(f"[MultiTask] task={task_id} user={user_id} error: {e}")
        if user_have_db:
            await user_db.drop_all(); await user_db.close()
        temp.IS_FRWD_CHAT[:] = [x for x in temp.IS_FRWD_CHAT if not (x[0]==user_id and x[1]==task_id)]
        return await _task_stop(client, user_id, task_id)

    temp.IS_FRWD_CHAT[:] = [x for x in temp.IS_FRWD_CHAT if not (x[0]==user_id and x[1]==task_id)]
    await bot.send_message(user_id, f"<b>🎉 Task {task_id} completed!</b>")
    await _edit_task(user_id, task_id, m, "ᴄᴏᴍᴘʟᴇᴛᴇᴅ", "completed", sts)
    if user_have_db:
        await user_db.drop_all(); await user_db.close()
    await _task_stop(client, user_id, task_id)


# ══════════════════════════════════════════════════════════════
#   EDIT PROGRESS MESSAGE
# ══════════════════════════════════════════════════════════════

async def _edit_task(user_id, task_id, msg, title, status, sts):
    i          = sts.get(full=True)
    status_str = "Forwarding" if status == 5 else (f"sleeping {status}s" if str(status).isnumeric() else status)
    total      = max(i.total, 1)
    percentage = "{:.0f}".format(float(i.fetched) * 100 / float(total))
    speed      = sts.speed_per_min()
    speed_str  = f"{speed:.1f}" if speed > 0 else "—"
    eta_str    = sts.eta_string()
    text       = Script.TEXT.format(
        i.fetched, i.total_files, i.duplicate,
        i.deleted, i.skip, i.filtered, status_str, percentage, speed_str, eta_str, title
    )
    progress    = "●{0}{1}".format(
        "".join(["●" for _ in range(math.floor(int(percentage) / 4))]),
        "".join(["○" for _ in range(24 - math.floor(int(percentage) / 4))])
    )
    paused = temp.is_paused(user_id, task_id)
    btns = [[InlineKeyboardButton(progress, f"mft#detail_{task_id}")]]
    if status in ("cancelled", "completed"):
        btns.append([InlineKeyboardButton("• ᴄᴏᴍᴘʟᴇᴛᴇᴅ ​•", url="https://t.me/Prime_SpoT")])
    else:
        pause_lbl = "▶️ ʀᴇsᴜᴍᴇ" if paused else "⏸ ᴘᴀᴜsᴇ"
        pause_cb  = f"mft#resume_{task_id}" if paused else f"mft#pause_{task_id}"
        btns.append([
            InlineKeyboardButton(pause_lbl,   callback_data=pause_cb),
            InlineKeyboardButton("⏹ ᴄᴀɴᴄᴇʟ", callback_data=f"mft#cancel_{task_id}"),
        ])
    await msg_edit(msg, text, InlineKeyboardMarkup(btns))


# ══════════════════════════════════════════════════════════════
#   STOP / CLEANUP
# ══════════════════════════════════════════════════════════════

async def _task_stop(client, user_id, task_id):
    try:
        await client.stop()
    except Exception:
        pass
    temp.clear_task(user_id, task_id)
    temp.forwardings -= 1
    await db.update_task(user_id, task_id, {"active": False})


# ══════════════════════════════════════════════════════════════
#   RESTART on bot startup
# ══════════════════════════════════════════════════════════════

async def restart_pending_multi_tasks(bot):
    logger.info("[MultiTask] Restarting pending tasks on startup...")
    try:
        user_ids = await db.get_all_active_task_users()
    except Exception as e:
        logger.error(f"[MultiTask] DB error fetching users: {e}")
        return

    count = 0
    for user_id in user_ids:
        tasks = await db.get_all_tasks(user_id)
        for t in tasks:
            if not t.get("active"):
                continue
            task_id = t["task_id"]
            try:
                sts = STS(task_id)
                sts.store(t["chat_id"], t["toid"], t.get("skip", 0), t.get("limit", 0))
                sts.add("fetched",    value=t.get("fetched", 0))
                sts.add("duplicate",  value=t.get("duplicate", 0))
                sts.add("filtered",   value=t.get("filtered", 0))
                sts.add("deleted",    value=t.get("deleted", 0))
                sts.add("total_files",value=t.get("total_files", 0))

                _bot, caption, forward_tag, datas, protect, button = await sts.get_data(user_id)
                if not _bot:
                    await db.update_task(user_id, task_id, {"active": False})
                    continue

                data   = _bot["token"] if _bot["is_bot"] else _bot["session"]
                client = await get_client(data, is_bot=_bot["is_bot"])
                await client.start()

                m = await bot.get_messages(user_id, t["msg_id"])
                temp.set_task(user_id, task_id)
                temp.IS_FRWD_CHAT.append((user_id, task_id, t["toid"]))
                temp.forwardings += 1
                sts.add(time=True, start_time=t.get("start_time"))

                asyncio.create_task(
                    _run_forward_task(
                        bot, client, user_id, task_id, m, sts,
                        datas, caption, forward_tag, protect, button
                    )
                )
                logger.info(f"[MultiTask] Resumed task={task_id} user={user_id}")
                count += 1
            except Exception as e:
                logger.warning(f"[MultiTask] Could not resume task={task_id} user={user_id}: {e}")
                await db.update_task(user_id, task_id, {"active": False})

    logger.info(f"[MultiTask] {count} task(s) resumed on startup.")


# ══════════════════════════════════════════════════════════════
#   UTIL
# ══════════════════════════════════════════════════════════════

def _join_filter(lst):
    if not lst:
        return None
    return "|".join(lst).rstrip("|")


# /tasks shortcut button on help
@Client.on_message(filters.private & filters.command(["stoptask"]))
async def stop_task_cmd(bot, message):
    user_id = message.from_user.id
    parts   = message.text.split()
    if len(parts) < 2:
        return await message.reply("<b>Usage:</b> /stoptask &lt;task_id&gt;")
    task_id = parts[1]
    t = await db.get_task(user_id, task_id)
    if not t:
        return await message.reply("Task not found.")
    temp.cancel_task(user_id, task_id)
    await message.reply(f"⏹ Task <code>{task_id}</code> is being cancelled…")

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
