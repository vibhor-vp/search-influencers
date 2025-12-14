# Google OAuth using authlib + Starlette integration
import os
from authlib.integrations.starlette_client import OAuth, OAuthError
from starlette.requests import Request
from fastapi import APIRouter, Request as FastAPIRequest
from fastapi.responses import RedirectResponse, JSONResponse

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

oauth = OAuth()
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile https://www.googleapis.com/auth/youtube.readonly"},
)

router = APIRouter()

@router.get("/login")
async def login(request: FastAPIRequest):
    redirect_uri = f"{BASE_URL}/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/callback")
async def auth_callback(request: FastAPIRequest):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as err:
        return JSONResponse({"error": "oauth_error", "details": str(err)}, status_code=400)

    # token contains access_token, refresh_token (if granted), expires_in ...
    userinfo = await oauth.google.parse_id_token(request, token)
    # TODO: persist `token` and user info (store refresh token securely) in DB or Redis
    return JSONResponse({"token": token, "userinfo": userinfo})
