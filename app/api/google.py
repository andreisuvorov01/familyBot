"""Подключение Google Calendar из Mini App.

OAuth нельзя проходить внутри WebView Telegram (Google отвечает disallowed_useragent),
поэтому Mini App получает ссылку и открывает её через Telegram.WebApp.openLink().
"""
from datetime import timedelta
from html import escape

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from jose import JWTError, jwt
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_async_session
from app.core.logging_config import log_with_context
from app.core.models.google import GoogleAccount, TaskCalendarEvent
from app.core.models.schemas import GoogleStatus
from app.core.models.user import User
from app.core.timeutils import utcnow
from app.services import calendar_sync
from app.services import google_calendar as gc
from app.services.crypto import decrypt, encrypt
from app.services.notifications import send_safe

router = APIRouter(prefix="/api/google", tags=["Google Calendar"])

STATE_PURPOSE = "google_oauth"
STATE_TTL = timedelta(minutes=15)


def _require_enabled() -> None:
    if not settings.google_enabled:
        raise HTTPException(status_code=503, detail="Google Calendar integration is not configured")


def make_state(user: User) -> str:
    payload = {"sub": str(user.id), "purpose": STATE_PURPOSE, "exp": utcnow() + STATE_TTL}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def read_state(state: str) -> int:
    try:
        payload = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    if payload.get("purpose") != STATE_PURPOSE:
        raise HTTPException(status_code=400, detail="Invalid state")
    return int(payload["sub"])


@router.get("/status", response_model=GoogleStatus)
async def google_status(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_async_session)):
    account = await session.get(GoogleAccount, user.id)
    if not account:
        return GoogleStatus(available=settings.google_enabled, connected=False)
    return GoogleStatus(
        available=settings.google_enabled,
        connected=True,
        enabled=account.enabled,
        email=account.email,
        last_error=account.last_error,
        last_synced_at=account.last_synced_at,
    )


@router.post("/auth-url")
async def google_auth_url(user: User = Depends(get_current_user)):
    _require_enabled()
    return {"url": gc.build_auth_url(make_state(user))}


def _result_page(title: str, text: str, ok: bool = True) -> HTMLResponse:
    color = "#22c55e" if ok else "#ef4444"
    html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)}</title>
<style>body{{font-family:-apple-system,system-ui,sans-serif;display:flex;min-height:100vh;align-items:center;
justify-content:center;margin:0;padding:16px;background:#f2f2f7;color:#111}}
.card{{background:#fff;border-radius:20px;padding:32px 24px;max-width:360px;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.06)}}
h1{{font-size:22px;margin:12px 0 8px;color:{color}}}p{{color:#555;line-height:1.5}}
@media (prefers-color-scheme:dark){{body{{background:#000;color:#eee}}.card{{background:#1c1c1e}}p{{color:#aaa}}}}</style>
</head><body><div class="card"><div style="font-size:48px">{'✅' if ok else '⚠️'}</div>
<h1>{escape(title)}</h1><p>{escape(text)}</p></div></body></html>"""
    return HTMLResponse(html, status_code=200 if ok else 400)


@router.get("/callback", response_class=HTMLResponse)
async def google_callback(
    state: str = Query(...),
    code: str | None = Query(None),
    error: str | None = Query(None),
    session: AsyncSession = Depends(get_async_session),
):
    _require_enabled()
    user_id = read_state(state)
    user = await session.get(User, user_id)
    if not user:
        return _result_page("Пользователь не найден", "Начните заново из бота.", ok=False)
    if error or not code:
        return _result_page(
            "Подключение отменено", "Google Календарь не подключён. Можно попробовать ещё раз из Mini App.", ok=False
        )

    try:
        tokens = await gc.exchange_code(code)
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            return _result_page(
                "Не получен доступ", "Google не выдал постоянный доступ. Попробуйте подключить ещё раз.", ok=False
            )

        account = await session.get(GoogleAccount, user.id)
        async with httpx.AsyncClient() as http:
            api = gc.CalendarApi(tokens["access_token"], http)
            calendar_id = account.calendar_id if account else None
            if not calendar_id or not await api.calendar_exists(calendar_id):
                calendar_id = await api.create_calendar(gc.CALENDAR_NAME, user.timezone)
                # Новый календарь — старые связи с событиями больше не действительны
                await session.execute(delete(TaskCalendarEvent).where(TaskCalendarEvent.user_id == user.id))

        if account is None:
            account = GoogleAccount(user_id=user.id, refresh_token_enc="")
            session.add(account)
        account.refresh_token_enc = encrypt(refresh_token)
        account.email = gc.email_from_id_token(tokens.get("id_token"))
        account.calendar_id = calendar_id
        account.enabled = True
        account.last_error = None
        account.sync_token = None
        await session.flush()

        queued = await calendar_sync.enqueue_full_resync(session, user)
        await session.commit()
    except (gc.GoogleApiError, gc.GoogleAuthError, httpx.HTTPError) as e:
        log_with_context("ERROR", f"Google OAuth callback failed: {e}", user_id=user.id)
        return _result_page("Ошибка Google", "Не удалось подключить календарь. Попробуйте позже.", ok=False)

    log_with_context("INFO", "Google Calendar connected", user_id=user.id, tasks_queued=queued)
    await send_safe(
        user.tg_id,
        "📅 <b>Google Календарь подключён!</b>\n"
        f"Задачи с дедлайном появятся в календаре «{gc.CALENDAR_NAME}» в течение минуты.",
    )
    return _result_page(
        "Календарь подключён", "Можно вернуться в Telegram — задачи с дедлайном скоро появятся в календаре «FamilyBot»."
    )


@router.post("/resync")
async def google_resync(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_async_session)):
    _require_enabled()
    account = await session.get(GoogleAccount, user.id)
    if not account or not account.enabled:
        raise HTTPException(status_code=400, detail="Google Calendar is not connected")
    queued = await calendar_sync.enqueue_full_resync(session, user)
    await session.commit()
    return {"ok": True, "queued": queued}


@router.delete("")
async def google_disconnect(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_async_session)):
    account = await session.get(GoogleAccount, user.id)
    if not account:
        return {"ok": True}
    try:
        await gc.revoke_token(decrypt(account.refresh_token_enc))
    except Exception as e:  # noqa: BLE001 — токен мог быть уже отозван
        log_with_context("WARNING", f"Google token revoke failed: {e}", user_id=user.id)
    await session.execute(delete(TaskCalendarEvent).where(TaskCalendarEvent.user_id == user.id))
    await session.delete(account)
    await session.commit()
    log_with_context("INFO", "Google Calendar disconnected", user_id=user.id)
    return {"ok": True}
