import unittest

import pandas as pd

from anomaly_detection import (
    classification_metrics,
    detect_anomalies,
    extract_hour_of_day,
)


def transaction(
    transaction_id,
    date,
    amount,
    category="Food",
    merchant="Cafe",
    review_feedback=None,
    transaction_hour=None,
):
    return {
        "id": transaction_id,
        "date": pd.Timestamp(date, tz="UTC"),
        "amount": amount,
        "category": category,
        "merchant": merchant,
        "direction": "Debit",
        "review_feedback": review_feedback,
        "transaction_hour": transaction_hour,
    }


class PersonalBaselineTests(unittest.TestCase):
    def test_amount_threshold_alone_does_not_create_an_alert(self):
        record = transaction(
            "large-first-purchase",
            "2026-01-01",
            6000,
            category="Other",
            merchant="New Merchant",
        )
        result = detect_anomalies(pd.DataFrame([record]), 5000, 3)
        self.assertEqual(result.iloc[0]["anomaly_score"], 10)
        self.assertFalse(result.iloc[0]["is_anomaly"])

    def test_category_baselines_distinguish_food_from_shopping(self):
        records = [
            transaction(f"food-{i}", f"2026-01-{i:02}", amount)
            for i, amount in enumerate((100, 150, 200, 250, 300), start=1)
        ]
        records.extend(
            transaction(
                f"shop-{i}",
                f"2026-02-{i:02}",
                amount,
                category="Shopping",
                merchant="Shop",
            )
            for i, amount in enumerate((500, 700, 900, 1200, 1500, 2000), start=1)
        )
        records.extend(
            [
                transaction("food-outlier", "2026-03-01", 3000, merchant="New Cafe"),
                transaction(
                    "normal-shopping",
                    "2026-03-02",
                    3000,
                    category="Shopping",
                    merchant="New Shop",
                ),
                transaction("normal-food", "2026-03-03", 250, merchant="New Cafe"),
            ]
        )

        result = detect_anomalies(pd.DataFrame(records), 10000, 3)
        labeled = result.set_index("id")
        self.assertTrue(labeled.at["food-outlier", "is_anomaly"])
        self.assertFalse(labeled.at["normal-shopping", "is_anomaly"])
        self.assertFalse(labeled.at["normal-food", "is_anomaly"])

        metrics = classification_metrics(
            [True, False, False],
            [
                labeled.at["food-outlier", "is_anomaly"],
                labeled.at["normal-shopping", "is_anomaly"],
                labeled.at["normal-food", "is_anomaly"],
            ],
        )
        self.assertEqual(metrics["precision"], 1.0)
        self.assertEqual(metrics["recall"], 1.0)
        self.assertEqual(metrics["false_positive_rate"], 0.0)

    def test_recent_frequency_and_unusual_weekday_add_score(self):
        records = [
            transaction("old-1", "2026-01-01", 100, merchant="A"),
            transaction("old-2", "2026-01-15", 100, merchant="B"),
            transaction("old-3", "2026-02-01", 100, merchant="C"),
            transaction("old-4", "2026-02-10", 100, merchant="D"),
            transaction("recent-1", "2026-02-22", 100, merchant="E"),
            transaction("recent-2", "2026-02-24", 100, merchant="F"),
            transaction("recent-3", "2026-02-26", 100, merchant="G"),
            transaction("recent-4", "2026-02-27", 100, merchant="H"),
            transaction("spike", "2026-02-28", 100, merchant="I"),
        ]
        result = detect_anomalies(pd.DataFrame(records), 10000, 3).set_index("id")
        self.assertEqual(result.at["spike", "anomaly_score"], 20)
        self.assertFalse(result.at["spike", "is_anomaly"])

        monday_dates = pd.date_range("2026-01-05", periods=8, freq="W-MON")
        timing_records = [
            transaction(f"monday-{i}", date, 100, merchant=f"merchant-{i}")
            for i, date in enumerate(monday_dates)
        ]
        timing_records.append(
            transaction("tuesday", "2026-03-03", 100, merchant="new-merchant")
        )
        timing = detect_anomalies(
            pd.DataFrame(timing_records), 10000, 3
        ).set_index("id")
        self.assertEqual(timing.at["tuesday", "anomaly_score"], 10)

    def test_monthly_category_spend_compares_complete_prior_months(self):
        records = [
            transaction(f"food-{month}", f"2026-{month:02}-15", 900)
            for month in range(1, 4)
        ]
        records.extend(
            transaction(
                f"shopping-{month}",
                f"2026-{month:02}-16",
                3000,
                category="Shopping",
                merchant=f"Shop {month}",
            )
            for month in range(1, 4)
        )
        records.extend(
            [
                transaction(
                    "food-month-spike",
                    "2026-04-01",
                    3000,
                    category="Food",
                    merchant="New Cafe",
                ),
                transaction(
                    "usual-shopping",
                    "2026-04-02",
                    2000,
                    category="Shopping",
                    merchant="New Shop",
                ),
            ]
        )
        result = detect_anomalies(pd.DataFrame(records), 2500, 3).set_index("id")
        self.assertTrue(result.at["food-month-spike", "is_anomaly"])
        self.assertEqual(result.at["food-month-spike", "anomaly_score"], 30)
        self.assertIn("usual monthly Food spending", result.at["food-month-spike", "reason"])
        self.assertFalse(result.at["usual-shopping", "is_anomaly"])

    def test_explicit_transaction_hour_drives_time_of_day_signal(self):
        self.assertEqual(extract_hour_of_day("Purchase at 9:35 AM"), 9)
        self.assertEqual(extract_hour_of_day("Transaction time: 21:45"), 21)
        self.assertIsNone(extract_hour_of_day("No transaction time provided"))

        records = [
            transaction(
                f"morning-{i}",
                f"2026-01-{i + 1:02}",
                100,
                merchant=f"Merchant {i}",
                transaction_hour=9,
            )
            for i in range(8)
        ]
        records.append(
            transaction(
                "late-night",
                "2026-02-01",
                1000,
                merchant="New Merchant",
                transaction_hour=23,
            )
        )
        result = detect_anomalies(
            pd.DataFrame(records), 10000, 3
        ).set_index("id")
        self.assertEqual(result.at["late-night", "anomaly_score"], 40)
        self.assertIn("unusual time of day", result.at["late-night", "reason"])

    def test_review_feedback_clears_alerts_and_teaches_future_baseline(self):
        records = [
            transaction(f"usual-{i}", f"2026-01-0{i}", 100, merchant="Shop")
            for i in range(1, 4)
        ]
        records.extend(
            transaction(
                f"legitimate-{i}",
                f"2026-01-0{i + 3}",
                600,
                merchant="Shop",
                review_feedback="legitimate",
            )
            for i in range(1, 4)
        )
        records.append(transaction("repeat", "2026-01-07", 600, merchant="Shop"))
        result = detect_anomalies(pd.DataFrame(records), 500, 3).set_index("id")
        self.assertFalse(result.at["legitimate-1", "is_anomaly"])
        self.assertEqual(
            result.at["legitimate-1", "review_status"], "Unusual but legitimate"
        )
        self.assertFalse(result.at["repeat", "is_anomaly"])

    def test_needs_review_is_not_used_to_normalize_future_baseline(self):
        records = [
            transaction(f"usual-{i}", f"2026-01-0{i}", 100, merchant="Shop")
            for i in range(1, 4)
        ]
        records.extend(
            [
                transaction(
                    "unresolved",
                    "2026-01-04",
                    600,
                    merchant="Shop",
                    review_feedback="needs_review",
                ),
                transaction("repeat", "2026-01-05", 600, merchant="Shop"),
            ]
        )
        result = detect_anomalies(pd.DataFrame(records), 500, 3).set_index("id")
        self.assertTrue(result.at["unresolved", "is_anomaly"])
        self.assertTrue(result.at["repeat", "is_anomaly"])

    def test_metrics_reject_mismatched_labels(self):
        with self.assertRaises(ValueError):
            classification_metrics([True], [])


if __name__ == "__main__":
    unittest.main()
