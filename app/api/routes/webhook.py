"""
Webhook endpoint для приема обновлений от Telegram на Vercel / Serverless.
"""
from fastapi import APIRouter, Header, HTTPException, Request, Response
from aiogram.types import Update, MenuButtonWebApp, WebAppInfo

from app.bot.bot import get_bot, get_dispatcher
from app.core.config import settings
from app.core.seed import seed_database

router = APIRouter(tags=["Telegram Webhook"])

_db_initialized = False


async def _ensure_seeded():
    global _db_initialized
    if not _db_initialized:
        try:
            await seed_database()
            _db_initialized = True
        except Exception as e:
            print(f"Seed database warning: {e}")


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str = Header(None),
):
    if settings.WEBHOOK_SECRET and x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret token")

    await _ensure_seeded()

    data = await request.json()
    bot = get_bot()
    update = Update.model_validate(data, context={"bot": bot})
    dp = get_dispatcher()
    await dp.feed_update(bot=bot, update=update)
    return Response(content="ok", status_code=200)


@router.get("/webhook")
async def webhook_status():
    """Проверка статуса вебхука."""
    await _ensure_seeded()
    bot = get_bot()
    info = await bot.get_webhook_info()
    return {
        "status": "active",
        "webhook_url": info.url,
        "pending_updates": info.pending_update_count,
        "last_error_message": info.last_error_message,
    }


@router.get("/setup-webhook")
async def setup_webhook():
    """Устанавливает Telegram Webhook и настраивает кнопку Mini App в боте."""
    await _ensure_seeded()
    bot = get_bot()
    webhook_url = f"{settings.FRONTEND_URL.rstrip('/')}/api/webhook"
    
    # 1. Установка вебхука
    set_webhook_res = await bot.set_webhook(
        url=webhook_url,
        secret_token=settings.WEBHOOK_SECRET or None,
        drop_pending_updates=True,
    )

    # 2. Установка кнопки Меню бота (Mini App)
    menu_button = MenuButtonWebApp(
        text="Мини-приложение",
        web_app=WebAppInfo(url=f"{settings.FRONTEND_URL.rstrip('/')}/")
    )
    await bot.set_chat_menu_button(menu_button=menu_button)

    return {
        "ok": True,
        "webhook_set": set_webhook_res,
        "webhook_url": webhook_url,
        "menu_button_url": f"{settings.FRONTEND_URL.rstrip('/')}/",
    }

