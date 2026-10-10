# Personal Expense Monitor

A Streamlit app that imports transaction-alert emails from Gmail, saves parsed transactions per app account, and scores unusual debits against explainable personal spending baselines. Gmail is accessed only after the user authorizes Google OAuth with read-only permission and clicks **Sync Gmail now**.

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
3. Create a **Web application** OAuth client. Add the exact deployed app URL as an **Authorized redirect URI** (not a JavaScript origin); this server-side OAuth flow does not need an authorized JavaScript origin. The URI must exactly match `redirect_uri` in Streamlit secrets, including the scheme, hostname, path, and trailing slash if present. For example, if the secret is `https://your-app.streamlit.app/`, register that exact value. Add the local `redirect_uri` too if you will test locally.
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
redirect_uri = "https://your-app.streamlit.app/"
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
- Personal anomaly baselines are learned separately for each account from earlier debits. Category amounts use a robust range, monthly category totals use prior calendar months, merchant amounts use the merchant median, and frequency, weekday, and explicit transaction-time patterns are used only when enough history exists. Time-of-day analysis uses an explicit time found in the message body; email delivery timestamps are not treated as transaction times.
- Each alert can be marked **Expected spending**, **Unusual but legitimate**, or **Needs further review**. Expected and legitimate decisions clear that alert and let the transaction inform later baselines; unresolved alerts remain out of later baselines. Review outcomes are saved with transaction history.
- The detector is regression-tested against labeled synthetic examples. Tests compute and assert precision, recall, and false-positive rate; these benchmark metrics are not a guarantee of real-world fraud detection performance.
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

- Scores each debit from 0–100 using the configured amount threshold, category amount history, monthly category spend, merchant amount history, recent category frequency, weekday timing, and explicit time-of-day patterns. A score of 30 or more creates a review alert; the amount threshold alone is not enough to alert.
- Compares category amounts after at least five accepted examples and merchant amounts after at least three. Category amount limits use the interquartile range and configured multiplier; merchant limits use the merchant median, multiplier, and a ₹500 minimum difference.
- Compares recent category frequency with the user's dated history after at least four prior examples spanning 28 days. Monthly spend is compared with prior calendar-month totals after three months of history. Weekday patterns use dated history, and time-of-day patterns use only explicit transaction times parsed from message bodies (not email delivery times); transactions without a reliably stated time do not contribute to that timing baseline.
- Keeps reasons visible for each alert and lets users correct outcomes. An expected or legitimate transaction can influence later personal baselines; a transaction marked for further review does not.
- Run the focused labeled regression benchmark with `python -m unittest discover -s tests`. It tracks precision, recall, and false-positive rate on synthetic known-normal and known-unusual cases.
