"""Тонкий асинхронный клиент Google OAuth2 + Calendar API v3 на httpx."""
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from jose import jwt

from app.core.config import settings
from app.core.models.Task import Task, TaskPriority

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API_URL = "https://www.googleapis.com/calendar/v3"

# calendar.app.created — доступ только к календарям, созданным приложением
SCOPES = ["https://www.googleapis.com/auth/calendar.app.created", "openid", "email"]

CALENDAR_NAME = "FamilyBot"
TASK_ID_PROPERTY = "familybot_task_id"
DONE_PREFIX = "✅ "
EVENT_DURATION = timedelta(minutes=30)

PRIORITY_COLORS = {TaskPriority.HIGH: "11", TaskPriority.MEDIUM: "5"}  # красный, жёлтый
DONE_COLOR = "8"  # графит

TIMEOUT = httpx.Timeout(15.0)


class GoogleAuthError(Exception):
    """Refresh token отозван/истёк — нужно переподключение."""


class GoogleApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"Google API {status}: {message}")
        self.status = status


class EventNotFound(GoogleApiError):
    pass


class SyncTokenExpired(GoogleApiError):
    pass


# --- OAuth ---


def build_auth_url(state: str) -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # гарантирует выдачу refresh token при повторном подключении
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        resp = await http.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        raise GoogleApiError(resp.status_code, resp.text[:300])
    return resp.json()


def email_from_id_token(id_token: str | None) -> str | None:
    """id_token получен напрямую от Google по TLS, поэтому подпись не перепроверяем."""
    if not id_token:
        return None
    try:
        return jwt.get_unverified_claims(id_token).get("email")
    except Exception:  # noqa: BLE001
        return None


async def refresh_access_token(refresh_token: str) -> str:
    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        resp = await http.post(
            TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code in (400, 401) and "invalid_grant" in resp.text:
        raise GoogleAuthError("invalid_grant")
    if resp.status_code != 200:
        raise GoogleApiError(resp.status_code, resp.text[:300])
    return resp.json()["access_token"]


async def revoke_token(token: str) -> None:
    async with httpx.AsyncClient(timeout=TIMEOUT) as http:
        await http.post(REVOKE_URL, data={"token": token})


# --- Calendar API ---


class CalendarApi:
    def __init__(self, access_token: str, http: httpx.AsyncClient):
        self._http = http
        self._headers = {"Authorization": f"Bearer {access_token}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        resp = await self._http.request(method, f"{API_URL}{path}", headers=self._headers, timeout=TIMEOUT, **kwargs)
        if resp.status_code == 401:
            raise GoogleAuthError("unauthorized")
        return resp

    @staticmethod
    def _raise(resp: httpx.Response) -> None:
        if resp.status_code in (404, 410):
            raise EventNotFound(resp.status_code, resp.text[:300])
        if resp.status_code >= 400:
            raise GoogleApiError(resp.status_code, resp.text[:300])

    async def create_calendar(self, summary: str, tz_name: str) -> str:
        resp = await self._request("POST", "/calendars", json={"summary": summary, "timeZone": tz_name})
        self._raise(resp)
        return resp.json()["id"]

    async def calendar_exists(self, calendar_id: str) -> bool:
        resp = await self._request("GET", f"/calendars/{calendar_id}")
        return resp.status_code == 200

    async def insert_event(self, calendar_id: str, body: dict) -> dict:
        resp = await self._request("POST", f"/calendars/{calendar_id}/events", json=body)
        self._raise(resp)
        return resp.json()

    async def patch_event(self, calendar_id: str, event_id: str, body: dict) -> dict:
        resp = await self._request("PATCH", f"/calendars/{calendar_id}/events/{event_id}", json=body)
        self._raise(resp)
        return resp.json()

    async def delete_event(self, calendar_id: str, event_id: str) -> None:
        resp = await self._request("DELETE", f"/calendars/{calendar_id}/events/{event_id}")
        if resp.status_code in (404, 410):
            return  # уже удалено
        self._raise(resp)

    async def list_changes(self, calendar_id: str, sync_token: str | None) -> tuple[list[dict], str | None]:
        """Изменённые события с прошлого раза. Без sync_token — полный список (для получения токена)."""
        items: list[dict] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"maxResults": 250, "showDeleted": "true"}
            if sync_token:
                params["syncToken"] = sync_token
            if page_token:
                params["pageToken"] = page_token
            resp = await self._request("GET", f"/calendars/{calendar_id}/events", params=params)
            if resp.status_code == 410:
                raise SyncTokenExpired(410, "sync token expired")
            self._raise(resp)
            data = resp.json()
            items.extend(data.get("items", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                return items, data.get("nextSyncToken")


# --- Сопоставление задачи и события ---


def _rfc3339(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat() + "Z"


def build_event(task: Task, tz_name: str) -> dict | None:
    """Тело события для задачи. None — задаче не нужно событие (нет дедлайна / отменена)."""
    if not task.deadline or task.status == "cancelled":
        return None

    is_done = task.status == "done"
    lines: list[str] = []
    if task.description:
        lines.append(task.description)
    if task.subtasks:
        if lines:
            lines.append("")
        lines.extend(f"{'☑' if s.is_done else '☐'} {s.title}" for s in task.subtasks)
    if lines:
        lines.append("")
    lines.append("Задача из FamilyBot")

    color = DONE_COLOR if is_done else PRIORITY_COLORS.get(task.priority) if task.priority else None
    return {
        "summary": f"{DONE_PREFIX if is_done else ''}{task.title}",
        "description": "\n".join(lines),
        "start": {"dateTime": _rfc3339(task.deadline - EVENT_DURATION), "timeZone": tz_name},
        "end": {"dateTime": _rfc3339(task.deadline), "timeZone": tz_name},
        "extendedProperties": {"private": {TASK_ID_PROPERTY: str(task.id)}},
        # None в PATCH сбрасывает цвет к цвету календаря
        "colorId": color,
    }


def parse_google_datetime(value: str) -> datetime:
    """RFC3339 -> наивный UTC."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
