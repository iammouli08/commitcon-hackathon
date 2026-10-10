"""Explainable, per-user spending baselines and anomaly scoring."""

import math

import pandas as pd


ALERT_SCORE_THRESHOLD = 30
REVIEW_FEEDBACK = {
    "expected": "Expected spending",
    "legitimate": "Unusual but legitimate",
    "needs_review": "Needs further review",
}
SIGNAL_WEIGHTS = {
    "amount": 20,
    "category": 30,
    "merchant": 20,
    "frequency": 20,
    "timing": 10,
}


def _timestamp(value):
    return pd.to_datetime(value, errors="coerce", utc=True)


def _category_amount_is_unusual(amount, history, multiplier):
    if len(history) < 5:
        return False
    values = pd.Series(history, dtype="float64")
    median = values.median()
    lower_quartile, upper_quartile = values.quantile([0.25, 0.75])
    upper_fence = max(
        upper_quartile + 1.5 * (upper_quartile - lower_quartile),
        median * multiplier,
        median + 500,
    )
    return amount > upper_fence


def _merchant_amount_is_unusual(amount, history, multiplier):
    if len(history) < 3:
        return False
    median = pd.Series(history, dtype="float64").median()
    return amount >= median * multiplier and amount - median >= 500


def _frequency_is_unusual(current_date, category_history):
    dated_history = [date for date, _ in category_history if not pd.isna(date)]
    if len(dated_history) < 4:
        return False
    first_date = min(dated_history)
    elapsed_days = (current_date - first_date).total_seconds() / 86400
    if elapsed_days < 28:
        return False

    weekly_rate = len(dated_history) / (elapsed_days / 7)
    recent_count = sum(
        0 <= (current_date - date).total_seconds() <= 7 * 86400
        for date in dated_history
    ) + 1
    expected_rate = max(weekly_rate * 2.5, weekly_rate + 2)
    return recent_count >= max(3, math.ceil(expected_rate))


def _timing_is_unusual(current_date, category_history):
    weekdays = [
        date.weekday()
        for date, _ in category_history
        if not pd.isna(date)
    ]
    if len(weekdays) < 8:
        return False
    return weekdays.count(current_date.weekday()) / len(weekdays) <= 0.1


def detect_anomalies(df, absolute_threshold, multiplier):
    """Score debits against each user's earlier, accepted spending history."""
    result = df.copy()
    result["is_anomaly"] = False
    result["anomaly_score"] = 0
    result["reason"] = ""
    result["review_status"] = "Normal"

    category_history = {}
    merchant_history = {}
    ordered = sorted(
        result.index,
        key=lambda index: (
            pd.isna(_timestamp(result.at[index, "date"])),
            _timestamp(result.at[index, "date"])
            if not pd.isna(_timestamp(result.at[index, "date"]))
            else pd.Timestamp.max.tz_localize("UTC"),
        ),
    )

    for index in ordered:
        row = result.loc[index]
        feedback = row.get("review_feedback")
        if feedback not in REVIEW_FEEDBACK:
            feedback = None
        is_debit = row.get("direction") == "Debit"
        amount = float(row.get("amount", 0) or 0)
        category = str(row.get("category", "Other"))
        merchant = str(row.get("merchant", "Unknown merchant"))
        current_date = _timestamp(row.get("date"))
        reasons = []
        score = 0

        if is_debit:
            prior_category = category_history.get(category, [])
            category_amounts = [prior_amount for _, prior_amount in prior_category]
            merchant_amounts = [
                prior_amount
                for _, prior_amount in merchant_history.get(merchant, [])
            ]
            if amount >= absolute_threshold:
                score += SIGNAL_WEIGHTS["amount"]
                reasons.append("above the configured amount threshold")
            if _category_amount_is_unusual(amount, category_amounts, multiplier):
                score += SIGNAL_WEIGHTS["category"]
                reasons.append(f"unusual for {category} spending")
            if _merchant_amount_is_unusual(amount, merchant_amounts, multiplier):
                score += SIGNAL_WEIGHTS["merchant"]
                reasons.append(f"unusual for {merchant}")
            if not pd.isna(current_date) and _frequency_is_unusual(
                current_date, prior_category
            ):
                score += SIGNAL_WEIGHTS["frequency"]
                reasons.append(f"more frequent than your usual {category} spending")
            if not pd.isna(current_date) and _timing_is_unusual(
                current_date, prior_category
            ):
                score += SIGNAL_WEIGHTS["timing"]
                reasons.append(f"unusual timing for {category} spending")

        is_anomaly = is_debit and score >= ALERT_SCORE_THRESHOLD
        result.at[index, "anomaly_score"] = score
        result.at[index, "is_anomaly"] = is_anomaly
        result.at[index, "reason"] = (
            f"Score {score}/100: " + "; ".join(reasons) if is_anomaly else ""
        )
        if feedback:
            result.at[index, "review_status"] = REVIEW_FEEDBACK[feedback]
            if feedback in ("expected", "legitimate"):
                result.at[index, "is_anomaly"] = False
        elif is_anomaly:
            result.at[index, "review_status"] = "Needs review"

        accepted_as_baseline = (
            not is_anomaly or feedback in ("expected", "legitimate")
        )
        if is_debit and accepted_as_baseline:
            category_history.setdefault(category, []).append(
                (current_date, amount)
            )
            merchant_history.setdefault(merchant, []).append(
                (current_date, amount)
            )

    return result


def classification_metrics(labels, predictions):
    """Return precision, recall, and false-positive rate for labeled examples."""
    actual = [bool(value) for value in labels]
    predicted = [bool(value) for value in predictions]
    if len(actual) != len(predicted):
        raise ValueError("Labels and predictions must have the same length.")
    true_positive = sum(y and p for y, p in zip(actual, predicted))
    false_positive = sum(not y and p for y, p in zip(actual, predicted))
    false_negative = sum(y and not p for y, p in zip(actual, predicted))
    true_negative = sum(not y and not p for y, p in zip(actual, predicted))
    return {
        "precision": true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0,
        "recall": true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0,
        "false_positive_rate": false_positive / (false_positive + true_negative)
        if false_positive + true_negative
        else 0.0,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
    }
