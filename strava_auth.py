"""One-time Strava OAuth helper — prints the refresh token for .env.

Setup (once):
1. Create an app: https://www.strava.com/settings/api
   → record Client ID and Client Secret.
2. Run:  python strava_auth.py <client_id> <client_secret>
3. Open the printed URL in a browser, authorize, and copy the full redirect
   URL (it contains ?code=...).
4. Paste the code when prompted.
5. Put the printed values into .env:
   STRAVA_CLIENT_ID=...
   STRAVA_CLIENT_SECRET=...
   STRAVA_REFRESH_TOKEN=...

The bot refreshes and rotates the token automatically afterwards.
"""

from __future__ import annotations

import sys
import urllib.parse

import httpx

TOKEN_URL = "https://www.strava.com/oauth/token"
AUTH_URL = "https://www.strava.com/oauth/authorize"
REDIRECT_URI = "http://localhost/exchange_token"


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: python strava_auth.py <client_id> <client_secret>")
        sys.exit(1)
    client_id, client_secret = sys.argv[1], sys.argv[2]

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": "activity:read",
        "approval_prompt": "auto",
    }
    print("\n1) Open this URL, authorize, and copy the FULL redirect URL:\n")
    print(f"   {AUTH_URL}?{urllib.parse.urlencode(params)}\n")

    code = input("2) Paste the ?code= value here: ").strip()
    if not code:
        print("no code given — aborting")
        sys.exit(1)

    response = httpx.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
    )
    if response.status_code >= 400:
        print(f"token exchange failed (HTTP {response.status_code}): {response.text}")
        sys.exit(1)
    data = response.json()
    print("\n3) Put these in .env:\n")
    print(f"STRAVA_CLIENT_ID={client_id}")
    print(f"STRAVA_CLIENT_SECRET={client_secret}")
    print(f"STRAVA_REFRESH_TOKEN={data['refresh_token']}\n")


if __name__ == "__main__":
    main()
