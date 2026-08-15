import logging
import os

from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def get_credentials():
    creds_path = str(settings.GOOGLE_CREDENTIALS_FILE)
    token_path = str(settings.GOOGLE_TOKEN_FILE)

    creds = None
    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except ValueError as exc:
            logger.warning("Neispravan token.json, ignoriram: %s", exc)
            creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds, token_path)
            return creds
        except Exception as exc:
            logger.warning("Osvježavanje tokena nije uspjelo: %s", exc)

    if not os.path.exists(creds_path):
        raise RuntimeError(
            f"Nedostaje {creds_path}. Preuzmi OAuth podatke iz Google Cloud "
            f"konzole i spremi ih pod tim imenom u korijen projekta."
        )

    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    _save_token(creds, token_path)
    return creds


def _save_token(creds, token_path):
    with open(token_path, "w", encoding="utf-8") as fh:
        fh.write(creds.to_json())
    logger.info("Token spremljen u %s", token_path)