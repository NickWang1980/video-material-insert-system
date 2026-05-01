from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..config import get_settings
from ..services.auth_service import decode_token

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_PUBLIC_PATHS = frozenset({"/api/auth/login"})

# Only these path prefixes require admin role for write operations.
# All other authenticated users may perform writes (tasks, rough-cut, materials, etc.)
_ADMIN_ONLY_WRITE_PREFIXES = ("/api/users", "/api/roles")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Non-API routes (static files, frontend) — skip
        if not path.startswith("/api/"):
            return await call_next(request)

        # Public endpoints — skip
        if path in _PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            # For GET requests, accept token via ?token= query param.
            # Browsers cannot send custom headers with <a href>, window.open,
            # <video src>, <img src> — all direct-download / media-play paths need this.
            if request.method == "GET":
                token_param = request.query_params.get("token", "")
                if token_param:
                    auth_header = f"Bearer {token_param}"
            if not auth_header.startswith("Bearer "):
                return JSONResponse({"detail": "未登录或会话已过期"}, status_code=401)

        token = auth_header[7:]
        settings = get_settings()
        payload = decode_token(token, settings.jwt_secret)
        if payload is None:
            return JSONResponse({"detail": "未登录或会话已过期"}, status_code=401)

        role = payload.get("role", "user")

        # Non-admin users may not write to admin-only endpoints
        if role != "admin" and request.method in _WRITE_METHODS:
            if any(path.startswith(prefix) for prefix in _ADMIN_ONLY_WRITE_PREFIXES):
                return JSONResponse({"detail": "权限不足，仅管理员可执行此操作"}, status_code=403)

        request.state.current_user = payload
        return await call_next(request)
