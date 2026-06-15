# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import time
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from database import db


# ──────────────────────────────────────────────────────────────
#   HELPERS
# ──────────────────────────────────────────────────────────────

def fmt_expiry(expiry):
    if not expiry:
        return "Lifetime ♾️"
    return datetime.fromtimestamp(expiry).strftime("%d %b %Y")


async def premium_panel_text(user_id: int) -> str:
    is_prem = await db.is_premium_user(user_id)
    if is_prem:
        expiry = await db.get_premium_expiry(user_id)
        return (
            "💎 <b>PREMIUM MEMBERSHIP</b>\n\n"
            "✅ Status: <b>Active ⭐</b>\n"
            f"📅 Valid Until: <b>{fmt_expiry(expiry)}</b>\n\n"
            "<b>Your Premium Perks:</b>\n"
            "• Up to <b>10</b> multi-forward tasks\n"
            "• Up to <b>10</b> live forward connections\n"
            "• Higher forward speed limits\n\n"
            "Thanks for supporting the bot! 🙏"
        )
    return (
        "💎 <b>PREMIUM MEMBERSHIP</b>\n\n"
        "🆓 Status: <b>Free</b>\n\n"
        "<b>Upgrade to Premium and get:</b>\n"
        "• Up to <b>10</b> multi-forward tasks (vs 1 on Free)\n"
        "• Up to <b>10</b> live forward connections (vs 1 on Free)\n"
        "• Higher forward speed limits\n"
        "• Priority support\n\n"
        "👇 Choose a plan to get started"
    )


async def premium_panel_buttons(user_id: int) -> InlineKeyboardMarkup:
    is_prem = await db.is_premium_user(user_id)
    buttons = []
    if not is_prem:
        plans = await db.get_premium_plans()
        for plan in plans:
            buttons.append([InlineKeyboardButton(
                f"⭐ {plan['label']} — {plan['price']}",
                callback_data=f"prem#plan_{plan['id']}"
            )])
    buttons.append([InlineKeyboardButton("« Back", callback_data="settings#main")])
    return InlineKeyboardMarkup(buttons)


# ──────────────────────────────────────────────────────────────
#   USER COMMANDS / CALLBACKS
# ──────────────────────────────────────────────────────────────

@Client.on_message(filters.command("premium") & filters.private)
async def premium_cmd(client, message):
    user_id = message.from_user.id
    await message.reply_text(
        await premium_panel_text(user_id),
        reply_markup=await premium_panel_buttons(user_id),
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex(r"^prem#"))
async def premium_callback(bot, query):
    user_id = query.from_user.id
    action = query.data.split("#", 1)[1]

    # ── Main panel ──────────────────────────────────────────
    if action == "main":
        return await query.message.edit_text(
            await premium_panel_text(user_id),
            reply_markup=await premium_panel_buttons(user_id),
            disable_web_page_preview=True
        )

    # ── Plan selected -> show payment info ──────────────────
    if action.startswith("plan_"):
        plan_id = action.split("_", 1)[1]
        plans = await db.get_premium_plans()
        plan = next((p for p in plans if p["id"] == plan_id), None)
        if not plan:
            return await query.answer("⚠️ Plan not found.", show_alert=True)

        settings = await db.get_bot_settings()
        payment_info = settings.get("payment_info", "Contact admin to pay.")

        text = (
            f"⭐ <b>{plan['label']} Plan</b>\n"
            f"💰 Price: <b>{plan['price']}</b>\n"
            f"⏳ Duration: <b>{plan['days']} days</b>\n\n"
            f"{payment_info}"
        )
        buttons = [
            [InlineKeyboardButton("✅ I've Paid", callback_data=f"prem#paid_{plan_id}")],
            [InlineKeyboardButton("« Back", callback_data="prem#main")],
        ]
        return await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )

    # ── User claims they've paid -> ask for screenshot ───────
    if action.startswith("paid_"):
        plan_id = action.split("_", 1)[1]
        plans = await db.get_premium_plans()
        plan = next((p for p in plans if p["id"] == plan_id), None)
        if not plan:
            return await query.answer("⚠️ Plan not found.", show_alert=True)

        await query.message.delete()

        try:
            ss = await bot.ask(
                chat_id=query.message.chat.id,
                text=(
                    "📸 <b>Send a screenshot of your payment</b> (as a photo) in this chat.\n\n"
                    "Your request will be forwarded to the admin for verification.\n"
                    "/cancel — cancel this process"
                ),
                timeout=300
            )
        except Exception:
            return await bot.send_message(
                query.message.chat.id,
                "⌛ Timed out waiting for screenshot. Use /premium to try again."
            )

        if ss.text and ss.text.strip().lower() == "/cancel":
            return await ss.reply_text("❌ Process cancelled.")

        if not ss.photo and not ss.document:
            return await ss.reply_text(
                "⚠️ Please send a photo/screenshot. Use /premium to try again."
            )

        # Forward proof to owner with approve/reject buttons
        caption = (
            f"💳 <b>New Premium Request</b>\n\n"
            f"👤 User: {ss.from_user.mention} (<code>{user_id}</code>)\n"
            f"📦 Plan: <b>{plan['label']}</b> ({plan['price']}, {plan['days']} days)"
        )
        req_id = await db.add_premium_request(user_id, plan_id)
        approve_buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"premadm#approve_{req_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"premadm#reject_{req_id}"),
            ]
        ])
        try:
            await ss.copy(chat_id=Config.BOT_OWNER, caption=caption, reply_markup=approve_buttons)
        except Exception:
            pass

        return await ss.reply_text(
            "✅ <b>Your request has been sent for verification.</b>\n\n"
            "You'll be notified once it's approved. This usually takes a "
            "short while — thanks for your patience! 🙏"
        )


# ──────────────────────────────────────────────────────────────
#   ADMIN: APPROVE / REJECT PREMIUM REQUESTS
# ──────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^premadm#") & filters.user(Config.BOT_OWNER))
async def premium_admin_callback(bot, query):
    action = query.data.split("#", 1)[1]
    kind, req_id = action.split("_", 1)

    req = await db.get_premium_request(req_id)
    if not req:
        return await query.answer("⚠️ Request not found / already handled.", show_alert=True)

    if req["status"] != "pending":
        return await query.answer("⚠️ This request was already handled.", show_alert=True)

    target = req["user_id"]
    plan_id = req["plan_id"]
    plans = await db.get_premium_plans()
    plan = next((p for p in plans if p["id"] == plan_id), None)

    if kind == "approve":
        days = plan["days"] if plan else 30
        expiry = time.time() + days * 86400
        await db.set_premium(target, True, expiry)
        await db.set_premium_request_status(req_id, "approved")

        await query.message.edit_caption(
            query.message.caption + "\n\n✅ <b>APPROVED</b>"
        )
        try:
            await bot.send_message(
                target,
                "🎉 <b>Your Premium purchase has been approved!</b>\n\n"
                f"⭐ Plan: {plan['label'] if plan else plan_id}\n"
                f"📅 Valid Until: {fmt_expiry(expiry)}\n\n"
                "Enjoy your premium perks! Open /premium to see details."
            )
        except Exception:
            pass
        return await query.answer("✅ Approved & user upgraded.", show_alert=True)

    if kind == "reject":
        await db.set_premium_request_status(req_id, "rejected")
        await query.message.edit_caption(
            query.message.caption + "\n\n❌ <b>REJECTED</b>"
        )
        try:
            await bot.send_message(
                target,
                "❌ <b>Your Premium payment could not be verified.</b>\n\n"
                "If you believe this is a mistake, please contact the admin "
                f"({Config.BOT_OWNER})."
            )
        except Exception:
            pass
        return await query.answer("❌ Rejected.", show_alert=True)
