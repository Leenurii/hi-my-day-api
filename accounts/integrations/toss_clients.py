import os, json, requests
from typing import Dict, Optional, Tuple

BASE = os.getenv("TOSS_BASE_URL", "https://apps-in-toss-api.toss.im")
GEN_TOKEN_URL = os.getenv("TOSS_GEN_TOKEN_URL", f"{BASE}/api-partner/v1/apps-in-toss/user/oauth2/generate-token")
REFRESH_URL   = os.getenv("TOSS_REFRESH_URL",   f"{BASE}/api-partner/v1/apps-in-toss/user/oauth2/refresh-token")
LOGIN_ME_URL  = os.getenv("TOSS_LOGIN_ME_URL",  f"{BASE}/api-partner/v1/apps-in-toss/user/oauth2/login-me")

CLIENT_CERT = os.getenv("TOSS_CLIENT_CERT")
CLIENT_KEY  = os.getenv("TOSS_CLIENT_KEY")

DEFAULT_TIMEOUT = (6, 20)  # (connect, read)

class TossMTLS:
    def __init__(self):
        if not (CLIENT_CERT and CLIENT_KEY):
            raise RuntimeError("mTLS cert/key 경로가 설정되지 않았습니다.")
        self.cert: Tuple[str, str] = (CLIENT_CERT, CLIENT_KEY)

    def generate_token(self, authorization_code: str, referrer: Optional[str]) -> Dict:
        payload = {"authorizationCode": authorization_code}
        if referrer:
            payload["referrer"] = referrer
        resp = requests.post(
            GEN_TOKEN_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            cert=self.cert, timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def refresh_token(self, refresh_token: str) -> Dict:
        payload = {"refreshToken": refresh_token}
        resp = requests.post(
            REFRESH_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            cert=self.cert, timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def get_login_me(self, access_token: str) -> Dict:
        resp = requests.get(
            LOGIN_ME_URL,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"},
            cert=self.cert, timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
