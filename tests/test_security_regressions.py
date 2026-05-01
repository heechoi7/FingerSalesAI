import unittest
from unittest.mock import patch

import main


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def execute(self, *_args, **_kwargs):
        return None

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row):
        self.row = row

    def cursor(self, **_kwargs):
        return FakeCursor(self.row)


class FakeDbContext:
    def __init__(self, row):
        self.row = row

    def __enter__(self):
        return FakeConnection(self.row)

    def __exit__(self, *_args):
        return False


def fake_session_row(user_status="active", tenant_status="active"):
    return {
        "tenant_id": 7,
        "tenant_code": "tenant-a",
        "tenant_name": "Tenant A",
        "tenant_status": tenant_status,
        "user_id": 11,
        "user_name": "Alice",
        "email": "alice@example.com",
        "role": "sales",
        "user_status": user_status,
    }


class SecurityRegressionTests(unittest.TestCase):
    def test_active_session_is_reloaded_from_database(self):
        with patch("main.db_connection", return_value=FakeDbContext(fake_session_row())):
            session = main.active_session_from_db({"tenant_id": 7, "user_id": 11})

        self.assertEqual(session["tenant_id"], 7)
        self.assertEqual(session["user_id"], 11)
        self.assertEqual(session["tenant_status"], "active")

    def test_inactive_user_session_is_rejected(self):
        with patch("main.db_connection", return_value=FakeDbContext(fake_session_row(user_status="inactive"))):
            session = main.active_session_from_db({"tenant_id": 7, "user_id": 11})

        self.assertIsNone(session)

    def test_inactive_tenant_session_is_rejected(self):
        with patch("main.db_connection", return_value=FakeDbContext(fake_session_row(tenant_status="suspended"))):
            session = main.active_session_from_db({"tenant_id": 7, "user_id": 11})

        self.assertIsNone(session)

    def test_linkedin_slug_name_candidate_ignores_numeric_suffix(self):
        name = main.social_name_candidate_from_slug(
            "LinkedIn",
            "person",
            "%ED%9D%AC%EC%A7%84-%EA%B9%80-9b0b62278",
        )

        self.assertEqual(name, "희진 김")

    def test_content_length_limit_rejects_large_upload(self):
        class FakeRequest:
            headers = {"content-length": str(main.MAX_UPLOAD_BYTES + 1)}

        with self.assertRaises(main.HTTPException) as raised:
            main.enforce_content_length(FakeRequest(), main.MAX_UPLOAD_BYTES)

        self.assertEqual(raised.exception.status_code, 413)


if __name__ == "__main__":
    unittest.main()
