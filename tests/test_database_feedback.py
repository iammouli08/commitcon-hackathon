import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database


class TransactionFeedbackMigrationTests(unittest.TestCase):
    def test_legacy_marked_normal_rows_migrate_to_review_feedback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "users.db"
            connection = sqlite3.connect(db_path)
            try:
                connection.executescript(
                    """
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        salt TEXT NOT NULL
                    );
                    INSERT INTO users VALUES (1, 'tester', 'hash', 'salt');
                    CREATE TABLE transactions (
                        user_id INTEGER NOT NULL,
                        transaction_id TEXT NOT NULL,
                        transaction_date TEXT,
                        merchant TEXT NOT NULL,
                        amount REAL NOT NULL,
                        direction TEXT NOT NULL,
                        category TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        marked_normal INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (user_id, transaction_id)
                    );
                    INSERT INTO transactions VALUES (
                        1, 'legacy-1', '2026-01-01', 'Shop', 600,
                        'Debit', 'Shopping', '', 1
                    );
                    """
                )
                connection.commit()
            finally:
                connection.close()

            with (
                patch.object(database, "DB_PATH", db_path),
                patch.object(database, "_database_url", return_value=None),
            ):
                database.init_db()
                records = database.get_transactions("tester")
                self.assertEqual(records[0]["review_feedback"], "expected")

                database.set_transaction_feedback(
                    "tester", "legacy-1", "legitimate"
                )
                updated = database.get_transactions("tester")
                self.assertEqual(updated[0]["review_feedback"], "legitimate")
                self.assertFalse(updated[0]["marked_normal"])
                database.save_transactions(
                    "tester",
                    [
                        {
                            "id": "timed-1",
                            "date": "2026-01-02",
                            "merchant": "Cafe",
                            "amount": 100,
                            "direction": "Debit",
                            "category": "Food",
                            "transaction_hour": 22,
                        }
                    ],
                )
                timed_record = next(
                    record
                    for record in database.get_transactions("tester")
                    if record["id"] == "timed-1"
                )
                self.assertEqual(timed_record["transaction_hour"], 22)


if __name__ == "__main__":
    unittest.main()
