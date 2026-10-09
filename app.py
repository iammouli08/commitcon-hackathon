import hmac
import json
import re
from pathlib import Path
from datetime import datetime

import pandas as pd
import psycopg
import streamlit as st

import database
import gmail_integration

st.set_page_config(
    page_title="Personal Expense Monitor",
    page_icon="🛡️",
    layout="wide",
)

ROOT = Path(__file__).parent
DATA_PATH = ROOT / "sample_emails.json"

try:
    database.init_db()
except psycopg.OperationalError as exc:
    st.title("Personal Expense Monitor")
    if "failed to resolve host" in str(exc).lower():
        st.error("The configured Supabase database hostname cannot be resolved by this computer.")
        st.info(
            "In Supabase, open **Connect**, select **Session pooler**, and replace the entire "
            "DATABASE_URL in `.streamlit/secrets.toml` with the provided connection string. "
            "Then restart the app. Do not use the direct database host from the `psql` command."
        )
    else:
        st.error("The app could not connect to the configured Supabase PostgreSQL database.")
        st.info(
            "Check that DATABASE_URL contains the current Supabase connection string and password, "
            "then restart the app. Do not share the connection string."
        )
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

oauth_callback_message = None
oauth_callback_is_error = False
oauth_error = st.query_params.get("error")
authorization_code = st.query_params.get("code")
returned_state = st.query_params.get("state", "")
if oauth_error:
    try:
        callback_username = gmail_integration.cancel_authorization(returned_state)
        st.session_state.authenticated = True
        st.session_state.username = callback_username
    except ValueError:
        pass
    oauth_callback_message = f"Google authorization was not completed: {oauth_error}"
    oauth_callback_is_error = True
    st.query_params.clear()
elif authorization_code:
    try:
        callback_username = gmail_integration.complete_authorization(authorization_code, returned_state)
        st.session_state.authenticated = True
        st.session_state.username = callback_username
        oauth_callback_message = "Gmail connected with read-only access."
    except (
        ValueError,
        RuntimeError,
        gmail_integration.GoogleAuthError,
        gmail_integration.OAuth2Error,
        gmail_integration.RequestException,
    ) as exc:
        oauth_callback_message = f"Could not connect Gmail: {exc}"
        oauth_callback_is_error = True
    finally:
        st.query_params.clear()

if not st.session_state.authenticated:
    if oauth_callback_message:
        st.error(oauth_callback_message)
    # High-end scoped styling for modern, responsive login interface
    st.markdown(
        """
        <style>
        /* Hide sidebar on login screen */
        [data-testid="stSidebar"], [data-testid="collapsedControl"] {
            display: none !important;
        }

        /* Ambient background styling */
        .stApp {
            background: radial-gradient(circle at 50% 15%, #181c30 0%, #0d111d 55%, #07090f 100%) !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
        }

        /* Container centering & responsive max-width */
        .auth-wrapper {
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 1.5rem 0.5rem 3rem 0.5rem;
            width: 100%;
        }

        .auth-card {
            background: rgba(18, 24, 38, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 24px;
            padding: 2.2rem 2.4rem;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.5), 0 0 35px rgba(99, 102, 241, 0.12);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            width: 100%;
            max-width: 500px;
            margin: 0 auto;
            animation: fadeIn 0.4s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(12px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Header elements */
        .auth-badge-container {
            display: flex;
            justify-content: center;
            margin-bottom: 1rem;
        }

        .auth-badge {
            background: rgba(99, 102, 241, 0.12);
            border: 1px solid rgba(99, 102, 241, 0.3);
            color: #818cf8;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 5px 14px;
            border-radius: 9999px;
            display: inline-flex;
            align-items: center;
            gap: 7px;
        }

        .badge-dot {
            width: 6px;
            height: 6px;
            background: #6366f1;
            border-radius: 50%;
            box-shadow: 0 0 8px #6366f1;
        }

        .auth-title {
            text-align: center;
            font-size: 1.7rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin: 0.4rem 0 0.3rem 0;
            background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .auth-subtitle {
            text-align: center;
            color: #94a3b8;
            font-size: 0.88rem;
            margin-bottom: 1.6rem;
            line-height: 1.45;
        }

        /* Tab styling */
        div[data-testid="stTabs"] {
            display: flex;
            justify-content: center;
            margin-bottom: 1.2rem;
        }

        div[data-testid="stTabs"] button[role="tab"] {
            background: rgba(255, 255, 255, 0.04) !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 12px !important;
            color: #94a3b8 !important;
            font-weight: 600 !important;
            padding: 0.55rem 1.4rem !important;
            font-size: 0.9rem !important;
            transition: all 0.25s ease !important;
            margin: 0 4px !important;
        }

        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.3) 0%, rgba(139, 92, 246, 0.25) 100%) !important;
            border-color: rgba(99, 102, 241, 0.6) !important;
            color: #ffffff !important;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.25) !important;
        }

        /* Form styling */
        div[data-testid="stForm"] {
            border: none !important;
            padding: 0 !important;
            background: transparent !important;
        }

        div[data-testid="stTextInput"] label {
            color: #cbd5e1 !important;
            font-size: 0.85rem !important;
            font-weight: 500 !important;
            margin-bottom: 0.25rem !important;
        }

        div[data-testid="stTextInput"] input {
            background: rgba(15, 23, 42, 0.75) !important;
            border: 1px solid rgba(148, 163, 184, 0.2) !important;
            border-radius: 10px !important;
            color: #f8fafc !important;
            padding: 0.65rem 0.9rem !important;
            font-size: 0.92rem !important;
            transition: all 0.2s ease !important;
        }

        div[data-testid="stTextInput"] input:focus {
            border-color: #6366f1 !important;
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25) !important;
            background: rgba(15, 23, 42, 0.95) !important;
        }

        /* Submit Buttons */
        div[data-testid="stFormSubmitButton"] button {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
            color: #ffffff !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
            border-radius: 11px !important;
            padding: 0.7rem 1.2rem !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            letter-spacing: 0.02em !important;
            box-shadow: 0 8px 24px rgba(79, 70, 229, 0.35) !important;
            transition: all 0.25s ease !important;
            margin-top: 0.5rem !important;
        }

        div[data-testid="stFormSubmitButton"] button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 12px 30px rgba(79, 70, 229, 0.5) !important;
            background: linear-gradient(135deg, #4338ca 0%, #6d28d9 100%) !important;
        }

        /* Quick Demo Chip */
        .demo-box {
            background: rgba(30, 41, 59, 0.45);
            border: 1px dashed rgba(99, 102, 241, 0.35);
            border-radius: 12px;
            padding: 0.75rem 1rem;
            margin: 1.2rem 0 0.8rem 0;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.5rem;
        }

        .demo-info {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .demo-title {
            font-size: 0.75rem;
            color: #818cf8;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .demo-creds {
            font-size: 0.82rem;
            color: #cbd5e1;
            font-family: monospace;
        }

        /* Security Badges Footer */
        .auth-footer {
            margin-top: 1.6rem;
            padding-top: 1.2rem;
            border-top: 1px solid rgba(255, 255, 255, 0.06);
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 1.2rem;
            flex-wrap: wrap;
        }

        .auth-footer-badge {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            font-size: 0.74rem;
            color: #64748b;
            font-weight: 500;
        }

        /* Mobile responsiveness adjustments */
        @media (max-width: 640px) {
            .auth-card {
                padding: 1.5rem 1.2rem;
                border-radius: 18px;
            }
            .auth-title {
                font-size: 1.4rem;
            }
            .demo-box {
                flex-direction: column;
                align-items: flex-start;
                gap: 0.6rem;
            }
            div[data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
                min-width: 100% !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Center card in grid layout
    _, center_col, _ = st.columns([1, 2.2, 1])

    with center_col:
        st.markdown(
            """
            <div class="auth-card">
                <div class="auth-badge-container">
                    <div class="auth-badge">
                        <span class="badge-dot"></span>
                        <span>Personal finance · private account</span>
                    </div>
                </div>
                <h1 class="auth-title">Personal Expense Monitor</h1>
                <p class="auth-subtitle">Track your expenses from read-only Gmail transaction alerts.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_login, tab_signup = st.tabs(["🔑 Sign In", "✨ Create Account"])

        with tab_login:
            with st.form("signin_form"):
                login_user = st.text_input("Username", placeholder="Your username", key="form_login_user")
                login_pass = st.text_input("Password", type="password", placeholder="••••••••", key="form_login_pass")
                submit_login = st.form_submit_button("Sign In to Portal", use_container_width=True)

            if submit_login:
                if database.verify_user(login_user, login_pass):
                    st.session_state.authenticated = True
                    st.session_state.username = login_user.strip()
                    st.rerun()
                else:
                    st.error("Incorrect username or password. Please verify or register an account.")

        with tab_signup:
            with st.form("signup_form"):
                new_user = st.text_input("Choose Username", placeholder="e.g. analyst_01", key="form_reg_user")
                new_pass = st.text_input("Choose Password", type="password", placeholder="At least 10 characters", key="form_reg_pass")
                confirm_pass = st.text_input("Confirm Password", type="password", placeholder="Repeat password", key="form_reg_confirm")
                submit_signup = st.form_submit_button("Create Account", use_container_width=True)

            if submit_signup:
                if new_pass != confirm_pass:
                    st.error("Passwords do not match. Please re-enter carefully.")
                else:
                    success, msg = database.create_user(new_user, new_pass)
                    if success:
                        st.success(msg)
                        st.session_state.authenticated = True
                        st.session_state.username = new_user.strip()
                        st.rerun()
                    else:
                        st.error(msg)

        # Micro Security Indicators
        st.markdown(
            """
            <div class="auth-footer">
                <span class="auth-footer-badge">🔒 Persistent account storage</span>
                <span class="auth-footer-badge">🛡️ PBKDF2-HMAC (100k)</span>
                <span class="auth-footer-badge">✉️ Gmail read-only</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.stop()


st.title("Personal Expense Monitor")
if oauth_callback_message:
    if oauth_callback_is_error:
        st.error(oauth_callback_message)
    else:
        st.success(oauth_callback_message)
navigation_slot = st.empty()
st.markdown(
    """
    <style>
    div[data-testid="stElementContainer"].st-key-dashboard_page,
    div.st-key-dashboard_page,
    div.st-key-dashboard_page [data-testid="stRadio"] {
        width: 100%;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        gap: 0.5rem;
        width: 100%;
    }
    div[data-testid="stRadio"] [data-testid="stRadioOption"] {
        box-sizing: border-box;
        min-height: 2.75rem;
        padding: 0.55rem 0.75rem;
        border: 1px solid var(--secondary-background-color);
        border-radius: 6px;
    }
    div[data-testid="stRadio"] [data-testid="stRadioOption"][data-selected="true"] {
        border-color: var(--primary-color);
    }
    @media (max-width: 640px) {
        div[data-testid="stRadio"] div[role="radiogroup"] {
            display: grid !important;
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        div[data-testid="stRadio"] div[role="radiogroup"] > label {
            justify-content: center;
            min-width: 0;
            width: 100%;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.caption("Personal expense monitoring from transaction alerts you choose to import.")
st.info("Alerts are indicators for your review, not confirmation of fraud.")

CURRENCY_RE = re.compile(
    r'(?i)(?:INR|Rs\.?|₹)\s*((?:\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?)'
)
DATE_PATTERNS = [
    re.compile(r'(?i)\bon\s+(\d{1,2}[-/][A-Za-z0-9]{3,9}[-/]\d{2,4})'),
    re.compile(r'\b(\d{1,2}-[A-Za-z]{3}-\d{4})\b'),
    re.compile(r'\b(\d{4}-\d{2}-\d{2})\b'),
]

PROMO_WORDS = ("special offer", "50% off", "newsletter", "promotional email", "shop now")
CREDIT_WORDS = ("refund", "received", "credited", "reimbursement", "cashback", "deposit")
DEBIT_WORDS = ("debited", "paid to", "payment successful", "purchase", "spent")

def parse_date(text, fallback):
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            raw = match.group(1)
            for fmt in ("%d-%b-%Y", "%d/%b/%Y", "%d-%B-%Y", "%d/%B/%Y", "%Y-%m-%d", "%d-%b-%y"):
                try:
                    return pd.Timestamp(datetime.strptime(raw, fmt).date())
                except ValueError:
                    pass
    try:
        return pd.Timestamp(fallback)
    except Exception:
        return pd.NaT

def categorize(merchant, body):
    text = f"{merchant} {body}".lower()
    if any(w in text for w in ("coffee", "restaurant", "food", "cafe")):
        return "Food"
    if "cinema" in text:
        return "Entertainment"
    if any(w in text for w in ("metro", "transit", "taxi", "cab")):
        return "Transport"
    if any(w in text for w in ("travel", "airline")):
        return "Travel"
    if any(w in text for w in ("fresh mart", "grocery", "supermarket", "market")):
        return "Groceries"
    if "book" in text:
        return "Books"
    if "stationery" in text:
        return "Education"
    if any(w in text for w in ("pharmacy", "medical", "clinic")):
        return "Health"
    if any(w in text for w in ("electronics", "gadgets", "online")):
        return "Shopping"
    return "Other"

def _nearest_distance(low, words, span):
    """Smallest character distance from the amount to any keyword hit."""
    best = None
    for w in words:
        start = 0
        while True:
            i = low.find(w, start)
            if i == -1:
                break
            if span[0] <= i <= span[1]:
                dist = 0
            else:
                dist = min(abs(i - span[1]), abs(span[0] - (i + len(w))))
            if best is None or dist < best:
                best = dist
            start = i + 1
    return best

def infer_direction(low, amount_span):
    """Pick the signal (credit or debit) closest to the amount mention.

    Direction verbs attach to the amount ("₹2,000 debited"), while refunds
    and cashback are often mentioned later in the same email. Nearest-hit
    distance keeps those later mentions from flipping the classification.
    """
    d_credit = _nearest_distance(low, CREDIT_WORDS, amount_span)
    d_debit = _nearest_distance(low, DEBIT_WORDS, amount_span)
    if d_credit is None and d_debit is None:
        return None
    if d_credit is None:
        return "Debit"
    if d_debit is None:
        return "Credit"
    return "Credit" if d_credit < d_debit else "Debit"

def parse_email(email):
    subject = str(email.get("subject", ""))
    body = str(email.get("body", ""))
    combined = f"{subject}. {body}"
    low = combined.lower()

    amount_match = CURRENCY_RE.search(combined)
    if not amount_match:
        return None
    try:
        amount = float(amount_match.group(1).replace(",", ""))
    except ValueError:
        return None

    # Use a known ID if present; otherwise make a stable ID from fields.
    txid = str(email.get("id") or f"{subject}-{email.get('date','')}-{amount}")

    direction = infer_direction(low, amount_match.span())
    if direction is None:
        # Avoid guessing from messages that merely mention an amount.
        return None
    if any(word in low for word in PROMO_WORDS):
        return None

    merchant_match = re.search(r'(?i)(?:at|to|from)\s+([A-Za-z][A-Za-z0-9 &._-]{1,35}?)(?:\s+on\b|[.,;]|$)', body)
    merchant = merchant_match.group(1).strip(" .,-") if merchant_match else subject.split(":")[-1].strip()
    merchant = re.sub(r'\s+', ' ', merchant)
    date = parse_date(body, email.get("date", pd.Timestamp.today().date()))
    return {
        "id": txid, "date": date, "merchant": merchant or "Unknown merchant",
        "amount": amount, "direction": direction,
        "category": categorize(merchant, body), "subject": subject,
        "raw_email": combined
    }

def load_sample_emails():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)

def detect_anomalies(df, absolute_threshold, multiplier):
    df = df.copy()
    df["is_anomaly"] = False
    df["reason"] = ""
    debits = df[df["direction"] == "Debit"]
    # A global threshold catches very large single purchases even with a small sample.
    df.loc[(df["direction"] == "Debit") & (df["amount"] >= absolute_threshold), "is_anomaly"] = True
    df.loc[(df["direction"] == "Debit") & (df["amount"] >= absolute_threshold), "reason"] = (
        "Amount is at or above your configured review threshold"
    )

    # Merchant baseline: median is robust to an occasional large purchase.
    for merchant, group in debits.groupby("merchant"):
        if len(group) < 3:
            continue
        baseline = group["amount"].median()
        # Require a meaningful absolute difference as well as a multiple of the baseline.
        candidates = group[(group["amount"] >= baseline * multiplier) & ((group["amount"] - baseline) >= 500)]
        for idx in candidates.index:
            df.loc[idx, "is_anomaly"] = True
            prior_reason = df.loc[idx, "reason"]
            extra = f"{df.loc[idx, 'amount']:,.0f} is {df.loc[idx, 'amount'] / max(baseline, 1):.1f}× the median for {merchant} (₹{baseline:,.0f})"
            df.loc[idx, "reason"] = f"{prior_reason}; {extra}".strip("; ")
    df["review_status"] = df["is_anomaly"].map({True: "Review", False: "Normal"})
    return df

with st.sidebar:
    username = st.session_state.username
    st.caption(f"Signed in as {username}")
    if st.button("Log out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.pop("username", None)
        st.session_state.pop("notified_anomaly_ids", None)
        st.session_state.pop("normal_override_ids", None)
        st.session_state.pop("gmail_oauth_url", None)
        st.session_state.pop("gmail_notice", None)
        st.session_state.pop("confirm_delete_history", None)
        st.rerun()
    if st.session_state.get("gmail_notice"):
        notice = st.session_state.pop("gmail_notice")
        if notice.startswith("WARNING:"):
            st.warning(notice.removeprefix("WARNING:").strip())
        else:
            st.success(notice)
    st.header("Gmail sync")
    gmail_connected = database.has_gmail_token(username)
    if gmail_connected:
        st.success("Gmail connected")
        gmail_query = st.text_input(
            "Gmail search",
            value=gmail_integration.DEFAULT_QUERY,
            help="Search is limited to matching transaction-alert messages; at most 100 are fetched per sync.",
            key=f"gmail_search_{username}",
        )
        if st.button("Sync Gmail now", type="primary", use_container_width=True):
            try:
                with st.spinner("Reading transaction-alert messages from Gmail..."):
                    messages, checked, more_available = gmail_integration.fetch_transaction_emails(
                        username, gmail_query
                    )
                    new_records = [
                        record for email in messages
                        if (record := parse_email(email)) is not None
                    ]
                    database.save_transactions(username, new_records)
                st.success(f"Checked {checked} messages; parsed {len(new_records)} transaction(s).")
                if more_available:
                    st.info("More matches exist than the 100-message limit. Narrow the search to a date range to import older matches.")
            except (
                ValueError,
                RuntimeError,
                gmail_integration.GoogleAuthError,
                gmail_integration.HttpError,
                gmail_integration.OAuth2Error,
                gmail_integration.RequestException,
            ) as exc:
                st.error(f"Gmail sync failed: {exc}")
        if st.button("Disconnect Gmail", use_container_width=True):
            try:
                gmail_integration.disconnect_gmail(username)
                st.session_state.gmail_notice = "Gmail access disconnected and revoked."
                st.rerun()
            except (
                RuntimeError,
                gmail_integration.InvalidToken,
                json.JSONDecodeError,
                UnicodeDecodeError,
                gmail_integration.RequestException,
            ) as exc:
                st.session_state.gmail_notice = (
                    f"WARNING: The stored connection was removed, but Google may not have revoked it: {exc}. "
                    "Check your Google Account security settings."
                )
                st.rerun()
    else:
        st.caption("Connect with Google to import transaction alerts. The app requests Gmail read-only access only.")
        if st.button("Connect Gmail", use_container_width=True):
            try:
                url, _ = gmail_integration.authorization_url(username)
                st.session_state.gmail_oauth_url = url
            except RuntimeError as exc:
                st.error(str(exc))
        if st.session_state.get("gmail_oauth_url"):
            st.link_button("Continue to Google consent", st.session_state.gmail_oauth_url)

    with st.expander("Account data"):
        st.caption("Disconnecting Gmail does not delete transactions already imported.")
        if st.button("Delete saved transaction history", key=f"delete_history_{username}"):
            st.session_state.confirm_delete_history = True
        if st.session_state.get("confirm_delete_history"):
            st.warning("This permanently deletes all imported transactions and review decisions for this account.")
            confirm_col, cancel_col = st.columns(2)
            if confirm_col.button("Confirm delete", key=f"confirm_delete_{username}"):
                database.delete_transactions(username)
                st.session_state.confirm_delete_history = False
                st.session_state.notified_anomaly_ids = set()
                st.session_state.normal_override_ids = set()
                st.session_state.gmail_notice = "Saved transaction history deleted."
                st.rerun()
            if cancel_col.button("Cancel", key=f"cancel_delete_{username}"):
                st.session_state.confirm_delete_history = False
                st.rerun()

    st.divider()
    st.header("Review settings")
    threshold = st.number_input("Flag debits at or above (₹)", min_value=1000, max_value=500000, value=5000, step=500)
    multiplier = st.slider("Merchant baseline multiplier", min_value=1.5, max_value=8.0, value=3.0, step=0.5)
    st.caption("Alerts are explainable review signals, not confirmation of fraud.")
    uploaded = st.file_uploader(
        "Optional: import email JSON", type=["json"], key=f"email_json_upload_{username}"
    )
    st.caption("JSON imports are saved to your account. Expected: a list with id, subject, date, and body.")
    show_sample = st.checkbox(
        "Show fictional sample transactions", value=False, key=f"show_sample_{username}"
    )

if uploaded:
    try:
        emails = json.load(uploaded)
        if not isinstance(emails, list):
            raise ValueError("JSON root must be a list.")
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        st.error(f"Could not read JSON file: {exc}")
        st.stop()
    source_label = "Imported JSON"
    records = [record for email in emails if isinstance(email, dict)
               if (record := parse_email(email)) is not None]
    database.save_transactions(username, records)
    records = database.get_transactions(username)
elif show_sample:
    emails = load_sample_emails()
    source_label = "Fictional sample data"
    records = [record for email in emails if isinstance(email, dict)
               if (record := parse_email(email)) is not None]
else:
    emails = []
    source_label = "Your saved transactions"
    records = database.get_transactions(username)
if not records:
    st.info("No transactions yet. Connect Gmail and use **Sync Gmail now**, import JSON, or enable the fictional sample data.")
    st.stop()

df = pd.DataFrame(records)
df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True, format="mixed")
df = df.drop_duplicates(subset=["id"], keep="first").sort_values("date", ascending=False)
df = detect_anomalies(df, threshold, multiplier)
if "marked_normal" not in df:
    df["marked_normal"] = False
df["user_marked_normal"] = df["marked_normal"].fillna(False).astype(bool)
if "normal_override_ids" not in st.session_state:
    st.session_state.normal_override_ids = set()
df["user_marked_normal"] |= df["id"].astype(str).isin(st.session_state.normal_override_ids)
df.loc[df["user_marked_normal"], "is_anomaly"] = False
df.loc[df["user_marked_normal"], "review_status"] = "Marked normal"

debits = df[df["direction"] == "Debit"]
credits = df[df["direction"] == "Credit"]
anomalies = df[df["is_anomaly"]]

if "notified_anomaly_ids" not in st.session_state:
    st.session_state.notified_anomaly_ids = set()
    st.session_state.skip_next_toasts = True
current_anomaly_ids = set(anomalies["id"].astype(str))
new_anomaly_ids = current_anomaly_ids - st.session_state.notified_anomaly_ids
if new_anomaly_ids and not st.session_state.pop("skip_next_toasts", False):
    if len(new_anomaly_ids) == 1:
        a = anomalies[anomalies["id"].astype(str).isin(new_anomaly_ids)].iloc[0]
        st.toast(f"Review {a['merchant']}: ₹{a['amount']:,.2f}", icon="⚠️")
    else:
        st.toast(f"{len(new_anomaly_ids)} new transactions need review", icon="⚠️")
st.session_state.notified_anomaly_ids.update(current_anomaly_ids)

with navigation_slot.container():
    page = st.radio(
        "Dashboard pages",
        ["Overview", "Alerts", "Transactions", "How it works"],
        horizontal=True,
        label_visibility="collapsed",
        key="dashboard_page",
    )
    st.caption(f"{len(anomalies)} alert(s) need review")

if page == "Overview":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total debits", f"₹{debits['amount'].sum():,.0f}")
    c2.metric("Total credits", f"₹{credits['amount'].sum():,.0f}")
    c3.metric("Transactions parsed", f"{len(df)}")
    c4.metric("Flagged for review", f"{len(anomalies)}")
    st.caption(
        f"Data source: {source_label} · {len(df)} saved transaction(s). "
        "Messages that do not match a transaction pattern are skipped."
    )

    st.subheader("Notifications")
    if anomalies.empty:
        st.success("No transactions need review.")
    else:
        st.warning(f"{len(anomalies)} transaction(s) need review.", icon="⚠️")
        with st.expander("View flagged transaction notifications"):
            for _, anomaly in anomalies.sort_values("date", ascending=False).iterrows():
                st.markdown(
                    f"**{anomaly['merchant']}** · ₹{anomaly['amount']:,.2f} · "
                    f"{anomaly['date'].strftime('%d %b %Y') if pd.notna(anomaly['date']) else 'Date unknown'}"
                )
                st.caption(anomaly["reason"] or "This transaction crossed an alert rule.")

    left, right = st.columns(2)
    with left:
        st.subheader("Spending by category")
        category_totals = debits.groupby("category", as_index=False)["amount"].sum().sort_values("amount", ascending=False)
        if not category_totals.empty:
            st.bar_chart(category_totals.set_index("category"))
        else:
            st.write("No debit transactions to chart.")
    with right:
        st.subheader("Debits over time")
        daily = debits.copy()
        if not daily.empty:
            daily["day"] = daily["date"].dt.strftime("%d %b")
            daily_totals = daily.groupby("day", as_index=False)["amount"].sum()
            st.line_chart(daily_totals.set_index("day"))
        else:
            st.write("No debit transactions to chart.")
    st.subheader("Latest alerts")
    if anomalies.empty:
        st.success("No transactions crossed the current alert rules.")
    else:
        show = anomalies[["date", "merchant", "amount", "category", "reason"]].copy()
        show["date"] = show["date"].dt.strftime("%d %b %Y")
        show["amount"] = show["amount"].map(lambda x: f"₹{x:,.2f}")
        st.dataframe(show, use_container_width=True, hide_index=True)

elif page == "Alerts":
    st.subheader("Transactions to review")
    if anomalies.empty:
        st.success("No anomalies detected with the current settings.")
    else:
        for _, row in anomalies.sort_values("amount", ascending=False).iterrows():
            with st.container(border=True):
                a, b = st.columns([1, 4])
                a.metric("Amount", f"₹{row['amount']:,.2f}")
                b.markdown(f"**{row['merchant']}** · {row['date'].strftime('%d %b %Y') if pd.notna(row['date']) else 'Date unknown'}")
                b.write(row["reason"] or "This transaction crossed an alert rule.")
                b.caption(f"Category: {row['category']} · Transaction ID: {row['id']}")
                if b.button("Mark as normal", key=f"mark_normal_{row['id']}"):
                    database.set_transaction_marked_normal(username, str(row["id"]), True)
                    st.session_state.normal_override_ids.add(str(row["id"]))
                    st.rerun()
    marked_normal = df[df["user_marked_normal"]]
    if not marked_normal.empty:
        st.subheader("Marked as normal")
        st.caption("Your review decisions are saved to your account.")
        for _, row in marked_normal.sort_values("date", ascending=False).iterrows():
            with st.container(border=True):
                a, b = st.columns([1, 4])
                a.metric("Amount", f"₹{row['amount']:,.2f}")
                b.markdown(f"**{row['merchant']}** · {row['date'].strftime('%d %b %Y') if pd.notna(row['date']) else 'Date unknown'}")
                b.caption(f"Category: {row['category']} · Transaction ID: {row['id']}")
                if b.button("Restore alert", key=f"restore_alert_{row['id']}"):
                    database.set_transaction_marked_normal(username, str(row["id"]), False)
                    st.session_state.normal_override_ids.discard(str(row["id"]))
                    st.rerun()
    st.caption("Always verify against your bank's records. An alert is not a fraud determination.")

elif page == "Transactions":
    st.subheader("Transaction explorer")
    q = st.text_input("Search merchant, category, or transaction ID")
    category_filter = st.selectbox("Category", ["All categories", *sorted(df["category"].unique())])
    direction_filter = st.multiselect("Direction", ["Debit", "Credit"], default=["Debit", "Credit"])
    anomaly_filter = st.selectbox("Review status", ["All", "Review only", "Normal only"])
    view = df[df["direction"].isin(direction_filter)].copy()
    if category_filter != "All categories":
        view = view[view["category"] == category_filter]
    if q:
        mask = (
            view["merchant"].str.contains(q, case=False, na=False)
            | view["category"].str.contains(q, case=False, na=False)
            | view["id"].str.contains(q, case=False, na=False)
        )
        view = view[mask]
    if anomaly_filter == "Review only":
        view = view[view["is_anomaly"]]
    elif anomaly_filter == "Normal only":
        view = view[~view["is_anomaly"]]
    display = view[["date", "id", "merchant", "category", "direction", "amount", "review_status", "reason"]].copy()
    display["date"] = display["date"].dt.strftime("%Y-%m-%d")
    st.dataframe(display, use_container_width=True, hide_index=True)
    csv = view.drop(columns=["raw_email"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button("Download filtered transactions as CSV", data=csv, file_name="transactions.csv", mime="text/csv")

elif page == "How it works":
    st.subheader("Explainable baseline rules")
    st.markdown("""
    1. **Connect:** authorize this app to read Gmail transaction alerts only. No email is sent, modified, or deleted.
    2. **Sync:** manually fetch up to 100 messages matching the Gmail search query.
    3. **Parse:** detect a currency amount, transaction direction, date, and merchant from each message.
    4. **Filter and deduplicate:** skip promotions and unrecognized messages, and keep one row per message ID.
    5. **Flag large purchases:** mark debits at or above the configurable amount threshold.
    6. **Compare merchant behavior:** for merchants with at least three debit examples, compare amounts with that merchant's median. An amount is flagged if it is at least the chosen multiple of the median and at least ₹500 higher.

    Imported transactions and review decisions are saved to your account. Email message bodies are processed for parsing but are not saved.
    """)
    st.warning("Limitations: bank email formats vary, merchant extraction is heuristic, and Gmail must be synced manually. This is not a bank-grade fraud detector.")
    if emails:
        with st.expander("Preview imported message text"):
            for email in emails[:8]:
                st.markdown(f"**{email.get('subject','(no subject)')}**")
                st.code(email.get("body", ""))

st.divider()
st.caption("Gmail access is read-only and user-initiated. Disconnect here and revoke the app in your Google Account to remove its grant.")