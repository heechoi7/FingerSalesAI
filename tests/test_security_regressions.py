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

    def test_social_links_are_classified_by_platform(self):
        links = main.extract_social_links(
            "https://www.linkedin.com/in/sara-kim-12345678 "
            "https://m.facebook.com/hihihihi2345 "
            "https://www.instagram.com/sales.ai/"
        )

        self.assertEqual([link["platform"] for link in links], ["LinkedIn", "Facebook", "Instagram"])
        self.assertEqual([link["entity_type"] for link in links], ["person", "profile", "profile"])

    def test_social_inspection_uses_metadata_without_saving(self):
        link = main.classify_social_link("https://facebook.com/hihihihi2345", "Facebook")
        with patch(
            "main.fetch_social_public_metadata",
            return_value={
                "title": "박광영 | Facebook",
                "og_title": "박광영 | Facebook",
                "twitter_title": "",
                "description": "Facebook profile",
                "og_description": "",
                "fetch_error": "",
            },
        ):
            item = main.inspect_social_link(link)

        self.assertEqual(item["platform"], "Facebook")
        self.assertEqual(item["profile_name"], "박광영")
        self.assertEqual(item["name_confidence"], "high")
        self.assertFalse(item["saved"])

    def test_admin_session_requires_admin_role(self):
        with patch("main.require_session", return_value={"role": "sales"}):
            with self.assertRaises(main.HTTPException) as raised:
                main.require_admin_session(object())

        self.assertEqual(raised.exception.status_code, 403)

    def test_admin_user_audit_select_excludes_password_hash(self):
        self.assertNotIn("password_hash", main.ADMIN_ENTITY_SELECTS["users"])

    def test_custom_code_tokens_are_normalized(self):
        payload = main.AdminCodesPayload(
            groups=[
                {
                    "group_code": "Industry Type",
                    "name": "산업군",
                    "items": [{"code": "IT Service", "name": "IT 서비스"}],
                }
            ]
        )

        codes = main.normalized_custom_codes(payload)

        self.assertEqual(codes["groups"][0]["group_code"], "industry_type")
        self.assertEqual(codes["groups"][0]["items"][0]["code"], "it_service")

    def test_custom_code_duplicate_group_is_rejected(self):
        payload = main.AdminCodesPayload(
            groups=[
                {"group_code": "source", "name": "유입경로"},
                {"group_code": "source", "name": "중복"},
            ]
        )

        with self.assertRaises(main.HTTPException) as raised:
            main.normalized_custom_codes(payload)

        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
