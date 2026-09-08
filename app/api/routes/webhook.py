"""
Webhook endpoint для приема обновлений от Telegram на Vercel / Serverless.
"""
from fastapi import APIRouter, Header, HTTPException, Request, Response
from aiogram.types import Update

from app.bot.bot import get_bot, get_dispatcher
from app.core.config import settings
from app.core.seed import seed_database

router = APIRouter(tags=["Telegram Webhook"])

_db_initialized = False

@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None),
):
    global _db_initialized
    if settings.WEBHOOK_SECRET and x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    if not _db_initialized:
        try:
            await seed_database()
            _db_initialized = True
        except Exception:
            pass

    data = await request.json()
    update = Update.model_validate(data, context={"bot": get_bot()})
    bot = get_bot()
    dp = get_dispatcher()
    await dp.feed_update(bot=bot, update=update)
    return Response(content="ok", status_code=200)
