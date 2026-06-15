# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import sys
import time
import asyncio
import datetime
from os import execle, environ, system

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from database import db
from .broadcast import broadcast_messages
from .premium import fmt_expiry


# ──────────────────────────────────────────────────────────────
#   DURATION PARSER  (e.g. "1d" -> 1, "2m" -> 60, "1y" -> 365, "30" -> 30)
# ──────────────────────────────────────────────────────────────

def parse_duration_to_days(duration: str) -> int:
    duration = duration.strip().lower()
    if duration in ("0", ""):
        return 0
    unit = duration[-1]
    if unit in ("d", "m", "y"):
        value = int(duration[:-1])
        if unit == "d":
            return value
        if unit == "m":
            return value * 30
        if unit == "y":
            return value * 365
    # Plain number -> treat as days
    return int(duration)


# ──────────────────────────────────────────────────────────────
#   MAIN PANEL
# ──────────────────────────────────────────────────────────────

async def admin_main_text():
    users_count, bots_count = await db.total_users_bots_count()
    forwardings = await db.forwad_count()
    prem_users = await db.get_all_premium_users()
    settings = await db.get_bot_settings()
    maint = "🔴 ON" if settings.get("maintenance_mode") else "🟢 OFF"
    return (
        "🛠 <b>ADMIN PANEL</b>\n\n"
        f"👥 Total Users: <code>{users_count}</code>\n"
        f"🤖 User Bots: <code>{bots_count}</code>\n"
        f"📦 Active Forwards: <code>{forwardings}</code>\n"
        f"⭐ Premium Users: <code>{len(prem_users)}</code>\n"
        f"🚧 Maintenance Mode: <b>{maint}</b>\n\n"
        "Choose an option below 👇"
    )


def admin_main_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👥 Users", callback_data="admin#users"),
            InlineKeyboardButton("⭐ Premium", callback_data="admin#premium"),
        ],
        [
            InlineKeyboardButton("🧩 Features", callback_data="admin#features"),
            InlineKeyboardButton("📢 Broadcast", callback_data="admin#broadcast"),
        ],
        [
            InlineKeyboardButton("📊 Stats", callback_data="admin#stats"),
            InlineKeyboardButton("🔄 Restart", callback_data="admin#restart_confirm"),
        ],
        [InlineKeyboardButton("✖ Close", callback_data="admin#close")],
    ])


@Client.on_message(filters.private & filters.command("admin") & filters.user(Config.BOT_OWNER))
async def admin_cmd(client, message):
    await message.reply_text(
        await admin_main_text(),
        reply_markup=admin_main_buttons(),
        disable_web_page_preview=True
    )


# ──────────────────────────────────────────────────────────────
#   FEATURE TOGGLES
# ──────────────────────────────────────────────────────────────

FEATURE_LABELS = {
    "maintenance_mode":     "🚧 Maintenance Mode",
    "new_users_allowed":    "🆕 New User Registration",
    "multi_forward_enabled": "📦 Multi Forward",
    "live_forward_enabled": "📡 Live Forward",
    "broadcast_enabled":    "📢 Broadcast",
}


async def features_buttons():
    settings = await db.get_bot_settings()
    buttons = []
    for key, label in FEATURE_LABELS.items():
        state = settings.get(key, True)
        # For maintenance_mode, ON means restricted -> show 🔴/🟢 accordingly
        emoji = "✅" if state else "❌"
        if key == "maintenance_mode":
            emoji = "🔴" if state else "🟢"
        buttons.append([InlineKeyboardButton(
            f"{emoji} {label}",
            callback_data=f"admin#toggle_{key}"
        )])
    buttons.append([InlineKeyboardButton("« Back", callback_data="admin#main")])
    return InlineKeyboardMarkup(buttons)


FEATURES_TEXT = (
    "🧩 <b>FEATURE TOGGLES</b>\n\n"
    "Tap any feature to enable/disable it bot-wide.\n\n"
    "🚧 <b>Maintenance Mode</b>: when ON, only the owner can use the bot — "
    "all other users get a maintenance message.\n"
    "🆕 <b>New User Registration</b>: when OFF, new users can't /start the bot."
)


# ──────────────────────────────────────────────────────────────
#   USER MANAGEMENT
# ──────────────────────────────────────────────────────────────

async def users_panel_text():
    users_count, bots_count = await db.total_users_bots_count()
    banned = await db.get_banned()
    return (
        "👥 <b>USER MANAGEMENT</b>\n\n"
        f"Total Users: <code>{users_count}</code>\n"
        f"Banned Users: <code>{len(banned)}</code>\n\n"
        "Choose an action 👇"
    )


def users_panel_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin#ban_user")],
        [InlineKeyboardButton("✅ Unban User", callback_data="admin#unban_user")],
        [InlineKeyboardButton("📃 List Banned", callback_data="admin#list_banned")],
        [InlineKeyboardButton("« Back", callback_data="admin#main")],
    ])


# ──────────────────────────────────────────────────────────────
#   PREMIUM MANAGEMENT
# ──────────────────────────────────────────────────────────────

async def premium_panel_text():
    prem_users = await db.get_all_premium_users()
    pending = await db.get_pending_premium_requests()
    return (
        "⭐ <b>PREMIUM MANAGEMENT</b>\n\n"
        f"Premium Users: <code>{len(prem_users)}</code>\n"
        f"Pending Requests: <code>{len(pending)}</code>\n\n"
        "Choose an action 👇"
    )


def premium_panel_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📃 View Plans", callback_data="admin#view_plans")],
        [InlineKeyboardButton("✏️ Edit Plan Prices", callback_data="admin#edit_plans")],
        [InlineKeyboardButton("💳 Edit Payment Info", callback_data="admin#edit_payment_info")],
        [InlineKeyboardButton("➕ Grant Premium", callback_data="admin#grant_premium")],
        [InlineKeyboardButton("➖ Revoke Premium", callback_data="admin#revoke_premium")],
        [InlineKeyboardButton("📋 List Premium Users", callback_data="admin#list_premium")],
        [InlineKeyboardButton("📥 Pending Requests", callback_data="admin#pending_requests")],
        [InlineKeyboardButton("« Back", callback_data="admin#main")],
    ])


async def plans_text():
    plans = await db.get_premium_plans()
    lines = ["📦 <b>PREMIUM PLANS</b>\n"]
    for p in plans:
        lines.append(f"• <b>{p['label']}</b> — {p['price']} ({p['days']} days)  [id: <code>{p['id']}</code>]")
    return "\n".join(lines)


def plans_edit_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ « Back", callback_data="admin#premium")]
    ])


async def edit_plans_buttons():
    plans = await db.get_premium_plans()
    buttons = []
    for p in plans:
        buttons.append([InlineKeyboardButton(
            f"{p['label']} ({p['price']}, {p['days']}d)",
            callback_data=f"admin#editplan_{p['id']}"
        )])
    buttons.append([
        InlineKeyboardButton("➕ Add Plan", callback_data="admin#addplan"),
        InlineKeyboardButton("🗑 Remove Plan", callback_data="admin#removeplan"),
    ])
    buttons.append([InlineKeyboardButton("« Back", callback_data="admin#premium")])
    return InlineKeyboardMarkup(buttons)


# ──────────────────────────────────────────────────────────────
#   CALLBACK ROUTER
# ──────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^admin#") & filters.user(Config.BOT_OWNER))
async def admin_callback(bot, query):
    action = query.data.split("#", 1)[1]
    msg = query.message

    # ── Navigation ──────────────────────────────────────────
    if action == "main":
        return await msg.edit_text(await admin_main_text(), reply_markup=admin_main_buttons(), disable_web_page_preview=True)

    if action == "close":
        return await msg.delete()

    if action == "stats":
        return await msg.edit_text(await admin_main_text(), reply_markup=admin_main_buttons(), disable_web_page_preview=True)

    # ── Feature toggles ─────────────────────────────────────
    if action == "features":
        return await msg.edit_text(FEATURES_TEXT, reply_markup=await features_buttons(), disable_web_page_preview=True)

    if action.startswith("toggle_"):
        key = action.split("_", 1)[1]
        settings = await db.get_bot_settings()
        new_val = not settings.get(key, True)
        await db.update_bot_setting(key, new_val)
        await query.answer(f"{'Enabled' if new_val else 'Disabled'} ✅", show_alert=False)
        return await msg.edit_text(FEATURES_TEXT, reply_markup=await features_buttons(), disable_web_page_preview=True)

    # ── User management ──────────────────────────────────────
    if action == "users":
        return await msg.edit_text(await users_panel_text(), reply_markup=users_panel_buttons(), disable_web_page_preview=True)

    if action == "ban_user":
        await query.answer()
        ask = await bot.ask(msg.chat.id, "👤 Send the <b>user ID</b> to ban.\n/cancel to abort.")
        if ask.text and ask.text.strip().lower() == "/cancel":
            return await ask.reply_text("❌ Cancelled.")
        try:
            target = int(ask.text.strip())
        except (ValueError, AttributeError):
            return await ask.reply_text("⚠️ Invalid user ID.")
        await db.ban_user(target, "Banned by admin")
        return await ask.reply_text(
            f"🚫 User <code>{target}</code> has been banned.",
            reply_markup=users_panel_buttons()
        )

    if action == "unban_user":
        await query.answer()
        ask = await bot.ask(msg.chat.id, "👤 Send the <b>user ID</b> to unban.\n/cancel to abort.")
        if ask.text and ask.text.strip().lower() == "/cancel":
            return await ask.reply_text("❌ Cancelled.")
        try:
            target = int(ask.text.strip())
        except (ValueError, AttributeError):
            return await ask.reply_text("⚠️ Invalid user ID.")
        await db.remove_ban(target)
        return await ask.reply_text(
            f"✅ User <code>{target}</code> has been unbanned.",
            reply_markup=users_panel_buttons()
        )

    if action == "list_banned":
        banned = await db.get_banned()
        if not banned:
            text = "📃 <b>No banned users.</b>"
        else:
            text = "📃 <b>Banned Users:</b>\n\n" + "\n".join(f"• <code>{u}</code>" for u in banned[:100])
        return await msg.edit_text(text, reply_markup=users_panel_buttons(), disable_web_page_preview=True)

    # ── Broadcast ─────────────────────────────────────────────
    if action == "broadcast":
        await query.answer()
        ask = await bot.ask(msg.chat.id, "📢 <b>Reply with the message you want to broadcast</b> (or /cancel).")
        if ask.text and ask.text.strip().lower() == "/cancel":
            return await ask.reply_text("❌ Cancelled.")
        if not await db.is_feature_enabled("broadcast_enabled"):
            return await ask.reply_text("🚫 Broadcast feature is currently disabled in Features panel.")

        users = await db.get_all_users()
        sts = await ask.reply_text("Broadcasting your message...")
        start_time = time.time()
        total_users = await db.total_users_count()
        done = success = blocked = deleted = failed = 0

        async for user in users:
            if 'id' in user:
                pti, sh = await broadcast_messages(int(user['id']), ask)
                if pti:
                    success += 1
                elif sh == "Blocked":
                    blocked += 1
                elif sh == "Deleted":
                    deleted += 1
                elif sh == "Error":
                    failed += 1
                done += 1
                if not done % 20:
                    await sts.edit(
                        f"Broadcast in progress:\n\nTotal Users {total_users}\n"
                        f"Completed: {done} / {total_users}\nSuccess: {success}\n"
                        f"Blocked: {blocked}\nDeleted: {deleted}"
                    )
            else:
                done += 1
                failed += 1

        time_taken = datetime.timedelta(seconds=int(time.time() - start_time))
        return await sts.edit(
            f"Broadcast Completed:\nCompleted in {time_taken} seconds.\n\n"
            f"Total Users {total_users}\nCompleted: {done} / {total_users}\n"
            f"Success: {success}\nBlocked: {blocked}\nDeleted: {deleted}"
        )

    # ── Restart ────────────────────────────────────────────────
    if action == "restart_confirm":
        return await msg.edit_text(
            "🔄 <b>Restart the bot?</b>\n\nThis will pull latest code and restart the process.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Yes, Restart", callback_data="admin#restart_go"),
                    InlineKeyboardButton("❌ Cancel", callback_data="admin#main"),
                ]
            ])
        )

    if action == "restart_go":
        await msg.edit_text("<i>Restarting...</i>")
        await asyncio.sleep(2)
        await msg.edit_text("<i>Server restarted successfully ✅</i>")
        system("git pull -f && pip3 install --no-cache-dir -r requirements.txt")
        execle(sys.executable, sys.executable, "main.py", environ)
        return

    # ── Premium management ───────────────────────────────────
    if action == "premium":
        return await msg.edit_text(await premium_panel_text(), reply_markup=premium_panel_buttons(), disable_web_page_preview=True)

    if action == "view_plans":
        return await msg.edit_text(await plans_text(), reply_markup=plans_edit_buttons(), disable_web_page_preview=True)

    if action == "edit_plans":
        return await msg.edit_text(
            "✏️ <b>Select a plan to edit</b>",
            reply_markup=await edit_plans_buttons(),
            disable_web_page_preview=True
        )

    if action.startswith("editplan_"):
        plan_id = action.split("_", 1)[1]
        plans = await db.get_premium_plans()
        plan = next((p for p in plans if p["id"] == plan_id), None)
        if not plan:
            return await query.answer("⚠️ Plan not found.", show_alert=True)

        await query.answer()
        ask = await bot.ask(
            msg.chat.id,
            f"✏️ Editing <b>{plan['label']}</b>\n\n"
            f"Current: <b>{plan['price']}</b> for <b>{plan['days']} days</b>\n\n"
            "Send new values as:\n<code>price | days</code>\n"
            "Example: <code>₹99 | 30</code>\n\n"
            "/cancel to abort."
        )
        if ask.text and ask.text.strip().lower() == "/cancel":
            return await ask.reply_text("❌ Cancelled.", reply_markup=await edit_plans_buttons())

        try:
            price_part, days_part = ask.text.split("|")
            price = price_part.strip()
            days = int(days_part.strip())
        except Exception:
            return await ask.reply_text("⚠️ Invalid format. Use: price | days", reply_markup=await edit_plans_buttons())

        await db.update_premium_plan(plan_id, price=price, days=days)
        return await ask.reply_text(
            f"✅ Updated <b>{plan['label']}</b> → {price}, {days} days",
            reply_markup=await edit_plans_buttons()
        )

    if action == "addplan":
        await query.answer()
        ask = await bot.ask(
            msg.chat.id,
            "➕ <b>Add a new plan</b>\n\n"
            "Send as:\n<code>id | label | price | duration</code>\n\n"
            "Duration can be in days, months, or years — e.g.\n"
            "<code>1d</code> = 1 day, <code>2m</code> = 2 months, <code>1y</code> = 1 year\n\n"
            "Example:\n<code>6m | 6 Months | ₹199 | 6m</code>\n\n"
            "/cancel to abort."
        )
        if ask.text and ask.text.strip().lower() == "/cancel":
            return await ask.reply_text("❌ Cancelled.", reply_markup=await edit_plans_buttons())

        try:
            parts = [p.strip() for p in ask.text.split("|")]
            plan_id, label, price, duration = parts[0], parts[1], parts[2], parts[3]
            days = parse_duration_to_days(duration)
        except Exception:
            return await ask.reply_text(
                "⚠️ Invalid format. Use: id | label | price | duration",
                reply_markup=await edit_plans_buttons()
            )

        await db.add_premium_plan(plan_id, label, price, days)
        return await ask.reply_text(
            f"✅ Added plan <b>{label}</b> — {price} ({days} days)",
            reply_markup=await edit_plans_buttons()
        )

    if action == "removeplan":
        await query.answer()
        plans = await db.get_premium_plans()
        ids = ", ".join(f"<code>{p['id']}</code>" for p in plans)
        ask = await bot.ask(
            msg.chat.id,
            f"🗑 <b>Send the plan ID to remove</b>\n\nExisting: {ids}\n\n/cancel to abort."
        )
        if ask.text and ask.text.strip().lower() == "/cancel":
            return await ask.reply_text("❌ Cancelled.", reply_markup=await edit_plans_buttons())

        plan_id = ask.text.strip()
        await db.remove_premium_plan(plan_id)
        return await ask.reply_text(
            f"✅ Removed plan <code>{plan_id}</code> (if it existed).",
            reply_markup=await edit_plans_buttons()
        )

    if action == "edit_payment_info":
        await query.answer()
        settings = await db.get_bot_settings()
        ask = await bot.ask(
            msg.chat.id,
            "💳 <b>Send the new payment info text</b> (HTML allowed).\n\n"
            f"Current:\n{settings.get('payment_info')}\n\n/cancel to abort."
        )
        if ask.text and ask.text.strip().lower() == "/cancel":
            return await ask.reply_text("❌ Cancelled.", reply_markup=premium_panel_buttons())
        await db.update_bot_setting("payment_info", ask.html)
        return await ask.reply_text("✅ Payment info updated.", reply_markup=premium_panel_buttons())

    if action == "grant_premium":
        await query.answer()
        ask = await bot.ask(
            msg.chat.id,
            "➕ Send: <code>user_id duration</code>\n\n"
            "Duration examples:\n"
            "<code>123456789 1d</code> — 1 day\n"
            "<code>123456789 1m</code> — 1 month\n"
            "<code>123456789 2m</code> — 2 months\n"
            "<code>123456789 1y</code> — 1 year\n"
            "<code>123456789 0</code> — lifetime\n\n/cancel to abort."
        )
        if ask.text and ask.text.strip().lower() == "/cancel":
            return await ask.reply_text("❌ Cancelled.", reply_markup=premium_panel_buttons())
        try:
            parts = ask.text.split()
            target = int(parts[0])
            duration = parts[1] if len(parts) > 1 else "0"
            days = parse_duration_to_days(duration)
        except Exception:
            return await ask.reply_text("⚠️ Invalid format.", reply_markup=premium_panel_buttons())

        expiry = None if days == 0 else time.time() + days * 86400
        await db.set_premium(target, True, expiry)
        try:
            await bot.send_message(
                target,
                "🎉 <b>You've been upgraded to Premium!</b>\n\n"
                f"📅 Valid Until: {fmt_expiry(expiry)}\n\n"
                "Open /premium to see your perks."
            )
        except Exception:
            pass
        return await ask.reply_text(
            f"✅ Premium granted to <code>{target}</code> (Expiry: {fmt_expiry(expiry)})",
            reply_markup=premium_panel_buttons()
        )

    if action == "revoke_premium":
        await query.answer()
        ask = await bot.ask(msg.chat.id, "➖ Send the <b>user ID</b> to revoke premium from.\n/cancel to abort.")
        if ask.text and ask.text.strip().lower() == "/cancel":
            return await ask.reply_text("❌ Cancelled.", reply_markup=premium_panel_buttons())
        try:
            target = int(ask.text.strip())
        except (ValueError, AttributeError):
            return await ask.reply_text("⚠️ Invalid user ID.", reply_markup=premium_panel_buttons())
        await db.set_premium(target, False, None)
        return await ask.reply_text(
            f"✅ Premium revoked from <code>{target}</code>",
            reply_markup=premium_panel_buttons()
        )

    if action == "list_premium":
        prem_users = await db.get_all_premium_users()
        if not prem_users:
            text = "📋 <b>No premium users.</b>"
        else:
            lines = ["📋 <b>Premium Users:</b>\n"]
            for u in prem_users[:100]:
                exp = u.get("premium_expiry")
                lines.append(f"• <code>{u['id']}</code> — {fmt_expiry(exp)}")
            text = "\n".join(lines)
        return await msg.edit_text(text, reply_markup=premium_panel_buttons(), disable_web_page_preview=True)

    if action == "pending_requests":
        pending = await db.get_pending_premium_requests()
        if not pending:
            text = "📥 <b>No pending premium requests.</b>"
        else:
            plans = await db.get_premium_plans()
            lines = ["📥 <b>Pending Requests:</b>\n"]
            for r in pending[:50]:
                plan = next((p for p in plans if p["id"] == r["plan_id"]), None)
                plan_name = plan["label"] if plan else r["plan_id"]
                lines.append(f"• <code>{r['user_id']}</code> — {plan_name}")
            lines.append("\nUse the Approve/Reject buttons sent to you when the user submitted proof.")
            text = "\n".join(lines)
        return await msg.edit_text(text, reply_markup=premium_panel_buttons(), disable_web_page_preview=True)
