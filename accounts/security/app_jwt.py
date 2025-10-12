import os, time, jwt

SIGN_KEY = os.getenv("APP_JWT_SIGNING_KEY", "dev-app-jwt")
EXP_MIN  = int(os.getenv("APP_JWT_EXPIRE_MIN", "43200"))

def issue_app_jwt(sub: int | str, extra: dict | None = None) -> str:
    now = int(time.time())
    payload = {"iss": "hi-my-day", "sub": str(sub), "iat": now, "exp": now + EXP_MIN * 60}
    if extra: payload.update(extra)
    return jwt.encode(payload, SIGN_KEY, algorithm="HS256")

def verify_app_jwt(token: str) -> dict:
    return jwt.decode(token, SIGN_KEY, algorithms=["HS256"])
