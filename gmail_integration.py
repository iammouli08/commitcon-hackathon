"""Read-only Gmail OAuth and transaction-alert message import."""

import base64
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests
import streamlit as st
from cryptography.fernet import Fernet, InvalidToken
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauthlib.oauth2 import OAuth2Error
from requests.exceptions import RequestException
from streamlit.errors import StreamlitSecretNotFoundError

import database

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DEFAULT_QUERY = "newer_than:90d {debit debited credited transaction payment purchase spent}"
MAX_MESSAGES_PER_SYNC = 100


def _settings():
    try:
        settings = st.secrets.get("google_oauth", {})
        values = {
            key: settings.get(key) or st.secrets.get(key)
            for key in ("client_id", "client_secret", "redirect_uri")
        }
    except (KeyError, FileNotFoundError, StreamlitSecretNotFoundError):
        values = {key: None for key in ("client_id", "client_secret", "redirect_uri")}
    for key in ("client_id", "client_secret", "redirect_uri"):
        values[key] = values[key] or os.getenv(f"GOOGLE_{key.upper()}")
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            "Gmail OAuth is missing these settings: "
            f"{', '.join(missing)}. Add them under [google_oauth] in "
            "C:\\commitcon\\.streamlit\\secrets.toml as described in README.md."
        )
    return values


def _token_cipher():
    try:
        secret_key = st.secrets.get("TOKEN_ENCRYPTION_KEY")
    except StreamlitSecretNotFoundError:
        secret_key = None
    key = os.getenv("TOKEN_ENCRYPTION_KEY") or secret_key
    if not key:
        raise RuntimeError("Set TOKEN_ENCRYPTION_KEY in Streamlit secrets before connecting Gmail.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is invalid; use a Fernet-generated key.") from exc


def _new_flow(state=None, code_verifier=None):
    settings = _settings()
    config = {
        "web": {
            "client_id": settings["client_id"],
            "client_secret": settings["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings["redirect_uri"]],
        }
    }
    return Flow.from_client_config(
        config,
        scopes=[GMAIL_SCOPE],
        redirect_uri=settings["redirect_uri"],
        state=state,
        code_verifier=code_verifier,
    )


def _serialize_credentials(credentials):
    token_info = json.loads(credentials.to_json())
    token_info.pop("client_secret", None)
    return json.dumps(token_info)


def authorization_url(username):
    if not database.is_persistent():
        raise RuntimeError("Configure Supabase PostgreSQL before connecting Gmail.")
    _token_cipher()
    flow = _new_flow()
    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    encrypted_verifier = _token_cipher().encrypt(
        flow.code_verifier.encode("ascii")
    ).decode("ascii")
    database.save_gmail_oauth_state(
        username, state_hash, int(time.time()) + 600, encrypted_verifier
    )
    return url, state


def _consume_state(returned_state):
    if not returned_state:
        raise ValueError("The Gmail authorization state did not match. Please try connecting again.")
    state_hash = hashlib.sha256(returned_state.encode("utf-8")).hexdigest()
    stored_state = database.consume_gmail_oauth_state(state_hash)
    if not stored_state:
        raise ValueError("The Gmail authorization state expired or was already used. Please try again.")
    username, encrypted_verifier = stored_state
    try:
        verifier = _token_cipher().decrypt(encrypted_verifier.encode("ascii")).decode("ascii")
    except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError("The Gmail authorization session could not be verified. Start Gmail connection again.") from exc
    return username, verifier


def cancel_authorization(returned_state):
    username, _ = _consume_state(returned_state)
    return username


def complete_authorization(code, returned_state):
    username, verifier = _consume_state(returned_state)
    flow = _new_flow(state=returned_state, code_verifier=verifier)
    flow.fetch_token(code=code)
    encrypted = _token_cipher().encrypt(_serialize_credentials(flow.credentials).encode("utf-8")).decode("ascii")
    database.save_gmail_token(username, encrypted)
    return username


def disconnect_gmail(username):
    try:
        encrypted = database.get_gmail_token(username)
        if encrypted:
            token_json = _token_cipher().decrypt(encrypted.encode("ascii")).decode("utf-8")
            token_data = json.loads(token_json)
            token = token_data.get("refresh_token") or token_data.get("token")
            if token:
                response = requests.post(
                    "https://oauth2.googleapis.com/revoke",
                    data={"token": token},
                    timeout=10,
                )
                response.raise_for_status()
    finally:
        database.delete_gmail_token(username)


def _credentials_for_user(username):
    encrypted = database.get_gmail_token(username)
    if not encrypted:
        raise RuntimeError("Connect a Gmail account before syncing.")
    cipher = _token_cipher()
    try:
        token_info = json.loads(cipher.decrypt(encrypted.encode("ascii")).decode("utf-8"))
        settings = _settings()
        token_info["client_id"] = settings["client_id"]
        token_info["client_secret"] = settings["client_secret"]
        credentials = Credentials.from_authorized_user_info(token_info, scopes=[GMAIL_SCOPE])
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        raise RuntimeError("The stored Gmail authorization could not be read. Reconnect Gmail.") from exc
    if credentials.expired:
        if not credentials.refresh_token:
            raise RuntimeError("Gmail authorization expired. Reconnect Gmail.")
        credentials.refresh(Request())
        encrypted = cipher.encrypt(_serialize_credentials(credentials).encode("utf-8")).decode("ascii")
        database.save_gmail_token(username, encrypted)
    return credentials


def _decode_body(data):
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _collect_body(payload):
    plain_parts = []
    html_parts = []
    stack = [payload]
    while stack:
        part = stack.pop()
        mime_type = part.get("mimeType", "")
        body_data = part.get("body", {}).get("data")
        if body_data and mime_type == "text/plain":
            plain_parts.append(_decode_body(body_data))
        elif body_data and mime_type == "text/html":
            html_parts.append(re.sub(r"<[^>]+>", " ", _decode_body(body_data)))
        stack.extend(part.get("parts", []))
    return "\n".join(plain_parts or html_parts)


def _message_to_email(message):
    payload = message.get("payload", {})
    headers = {
        header.get("name", "").lower(): header.get("value", "")
        for header in payload.get("headers", [])
    }
    date_text = headers.get("date")
    if date_text:
        try:
            message_date = parsedate_to_datetime(date_text)
            if message_date.tzinfo is None:
                message_date = message_date.replace(tzinfo=timezone.utc)
            message_date = message_date.isoformat()
        except (TypeError, ValueError, OverflowError):
            message_date = None
    else:
        message_date = None
    if not message_date and message.get("internalDate"):
        message_date = datetime.fromtimestamp(
            int(message["internalDate"]) / 1000, tz=timezone.utc
        ).isoformat()
    return {
        "id": message["id"],
        "subject": headers.get("subject", ""),
        "date": message_date,
        "body": _collect_body(payload),
    }


def fetch_transaction_emails(username, query=DEFAULT_QUERY):
    if not query.strip():
        raise ValueError("Enter a Gmail search query before syncing.")
    credentials = _credentials_for_user(username)
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    response = service.users().messages().list(
        userId="me", q=query.strip(), maxResults=MAX_MESSAGES_PER_SYNC
    ).execute()
    messages = response.get("messages", [])
    emails = []
    for message_ref in messages:
        message = service.users().messages().get(
            userId="me", id=message_ref["id"], format="full"
        ).execute()
        emails.append(_message_to_email(message))
    return emails, len(messages), bool(response.get("nextPageToken"))
