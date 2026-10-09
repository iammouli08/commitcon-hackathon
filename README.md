# Personal Expense Monitor

A Streamlit app that imports transaction-alert emails from Gmail, saves parsed transactions per app account, and flags unusual debits with explainable rules. Gmail is accessed only after the user authorizes Google OAuth with read-only permission and clicks **Sync Gmail now**.

## Local development

Requirements: Python 3.10+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Create an account in the app with a password of at least 10 characters. Local development uses `users.db` (SQLite). Gmail connection requires the Google OAuth and Supabase settings below; without them, you can use the fictional sample-data toggle or import a JSON list. Imported transactions and review decisions are saved to the current account.

## Deploy on Streamlit Community Cloud

### 1. Set up Supabase PostgreSQL

Create a Supabase project and copy its PostgreSQL connection string. Use the session-pooler connection string if the deployment network requires it. Keep the password URL-encoded and require SSL. The app creates its tables at startup. Do not use local SQLite for a shared deployment: its data is not durable or shared across app instances.

### 2. Configure Gmail OAuth in Google Cloud

1. Create/select a Google Cloud project and enable the **Gmail API**.
2. Configure the OAuth consent screen for external users and add the scope `https://www.googleapis.com/auth/gmail.readonly`.
3. Create a **Web application** OAuth client. Add the exact deployed app URL (for example, `https://your-app.streamlit.app`) as an authorized redirect URI. Add `http://localhost:8501` too if you will test locally.
4. Add test users while the consent screen is in testing mode.

`gmail.readonly` is a restricted Gmail scope. Google requires OAuth verification and may require a security assessment before an app can serve the public. During testing, Google may limit refresh-token lifetime. Complete Google’s current verification requirements before treating the deployment as a public production service.

### 3. Add Streamlit secrets

In Streamlit Community Cloud, open the app's **Settings → Secrets** and add:

```toml
DATABASE_URL = "PASTE_YOUR_SUPABASE_POSTGRES_CONNECTION_STRING"
TOKEN_ENCRYPTION_KEY = "GENERATE_A_FERNET_KEY"

[google_oauth]
client_id = "YOUR_GOOGLE_OAUTH_CLIENT_ID"
client_secret = "YOUR_GOOGLE_OAUTH_CLIENT_SECRET"
redirect_uri = "https://your-app.streamlit.app"
```

Generate the encryption key locally with:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Use a different redirect URI matching the Google OAuth client for local development. Never commit or share the database URL, OAuth client secret, or encryption key. Changing the encryption key makes previously stored Gmail tokens unreadable; affected users must reconnect Gmail.

## Gmail behavior and privacy

- The app requests only Gmail read-only permission. It does not send, modify, or delete messages.
- Sync is manual. The default Gmail search checks the last 90 days and each click fetches at most 100 matching messages. Narrow the search with Gmail query operators (for example, `after:2026/01/01 before:2026/04/01`) to import a different date range.
- Message bodies are processed in memory and are not saved. Parsed transaction fields and review decisions are stored per app account in PostgreSQL. OAuth tokens are encrypted before storage using `TOKEN_ENCRYPTION_KEY`.
- Disconnecting revokes the Google grant and removes the stored token; it does not delete imported transaction history. The **Account data** section can permanently delete the signed-in account's imported transactions. To revoke manually, use the Google Account security settings.
- The local username/password login is a lightweight app login, not a managed identity provider. Add a dedicated authentication provider, abuse protections, a privacy/retention policy, and operational monitoring before offering the app as a public financial-data service.

## Optional JSON import

Upload a JSON list such as:

```json
[
  {
    "id": "TXN100",
    "subject": "Debit alert: Book Shop",
    "date": "2026-10-01",
    "body": "Your account was debited INR 650.00 at Book Shop on 01-Oct-2026. Transaction ID TXN100."
  }
]
```

JSON imports are saved to the signed-in account; use fictional sample data to preview the dashboard without importing it into your history.

## Detection rules

- Flags debits at or above the configurable amount threshold.
- For merchants with at least three debits, flags values that are at least a configurable multiple of the merchant median and at least ₹500 above that median.
- Displays the reason for each alert. These are review signals, not proof of fraud; bank email formats and merchant extraction vary.
