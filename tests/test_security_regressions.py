import unittest
import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import database
import agent_commands
import main
import mysql.connector
import json


class FakeCursor:
    def __init__(self, row):
        self.row = row

    def execute(self, *_args, **_kwargs):
        return None

    def fetchone(self):
        return self.row


class FakeListCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *_args, **_kwargs):
        return None

    def fetchall(self):
        return self.rows


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

    def test_record_audit_event_skips_missing_session(self):
        with patch("main.db_connection") as db_connection:
            main.record_audit_event(None, "view", "customer")

        db_connection.assert_not_called()

    def test_record_audit_event_does_not_break_user_flow(self):
        with patch("main.db_connection", side_effect=RuntimeError("audit unavailable")), patch("builtins.print"):
            main.record_audit_event({"tenant_id": 1, "user_id": 2}, "view", "customer")

    def test_identifier_quote_escapes_backticks(self):
        self.assertEqual(database.quote_identifier("a`b"), "`a``b`")

    def test_application_code_does_not_use_hard_delete_sql(self):
        workspace = Path(__file__).resolve().parents[1]
        source = "\n".join((workspace / name).read_text(encoding="utf-8") for name in ("main.py", "database.py"))

        self.assertNotIn("DELETE FROM", source.upper())

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

    def test_team_leader_setting_parser_keeps_integer_mapping(self):
        leaders = main.parse_team_leaders_setting({"leaders": {"10": 25, "bad": "x"}})

        self.assertEqual(leaders, {"10": 25})

    def test_default_pipeline_stage_codes_match_expected_order(self):
        codes = [stage["stage_code"] for stage in main.DEFAULT_PIPELINE_STAGES]

        self.assertEqual(codes, ["lead", "prospect", "opportunity", "proposal", "contract", "success"])

    def test_sales_activity_schedule_intent_is_detected(self):
        self.assertTrue(main.is_sales_activity_schedule_request("SK 렌터카 이재성 내일 오후 2시 미팅 일정 등록해줘"))
        self.assertTrue(main.is_sales_activity_schedule_request("내일 미팅 일정 취소해줘"))
        self.assertTrue(main.is_sales_activity_schedule_request("영업활동 목록 보여줘"))
        self.assertFalse(main.is_sales_activity_schedule_request("SK 렌터카 정보 알려줘"))

    def test_sales_activity_due_at_parses_relative_korean_time(self):
        now = main.datetime(2026, 5, 1, 10, 0)
        due_at = main.parse_sales_activity_due_at("내일 오후 2시 미팅 일정 등록", now)

        self.assertEqual(due_at, main.datetime(2026, 5, 2, 14, 0))

    def test_sales_activity_type_parses_call(self):
        self.assertEqual(main.parse_sales_activity_type("내일 오전 10시 전화 일정 등록"), "call")

    def test_sales_activity_new_due_at_uses_last_date_candidate(self):
        now = main.datetime(2026, 5, 1, 10, 0)
        due_at = main.parse_sales_activity_new_due_at("내일 일정을 모레 오후 3시로 변경", now)

        self.assertEqual(due_at, main.datetime(2026, 5, 3, 15, 0))

    def test_sales_activity_recurrence_rule_caps_count(self):
        first_due_at = main.datetime(2026, 5, 4, 10, 0)
        rule = main.parse_recurrence_rule("매주 월요일 오전 10시 99회 반복 일정 등록", first_due_at)

        self.assertEqual(rule["frequency"], "weekly")
        self.assertEqual(rule["count"], main.MAX_RECURRING_ACTIVITY_COUNT)
        self.assertEqual(main.recurrence_due_at(rule, 1), main.datetime(2026, 5, 11, 10, 0))

    def test_sales_activity_time_does_not_read_repeat_count_as_minutes(self):
        now = main.datetime(2026, 5, 1, 10, 0)
        due_at = main.parse_sales_activity_due_at("매주 월요일 오전 10시 2회 반복 일정 등록", now)

        self.assertEqual(due_at, main.datetime(2026, 5, 4, 10, 0))

    def test_sales_activity_weekday_parser_ignores_schedule_word(self):
        now = main.datetime(2026, 5, 1, 10, 0)
        candidates = main.parse_sales_activity_due_at_candidates("일정을 다음 주 화요일 오후 3시로 변경", now)

        self.assertEqual(candidates, [main.datetime(2026, 5, 5, 15, 0)])

    def test_customer_mention_scores_company_or_contact(self):
        row = {"company_name": "Acme Korea", "contact_name": "Chris Park"}

        self.assertGreater(main.score_customer_mention("Acme Korea meeting", row), 0)
        self.assertGreater(main.score_customer_mention("Chris Park call", row), 0)
        self.assertEqual(main.score_customer_mention("other customer", row), 0)

    def test_command_context_injects_single_customer_candidate(self):
        row = {
            "contact_id": 42,
            "tenant_id": 7,
            "account_id": 9,
            "owner_user_id": 11,
            "company_name": "Acme Korea",
            "contact_name": "Chris Park",
        }

        context = main.context_with_selected_customer({}, row)

        self.assertEqual(context["selectedCustomer"]["contactId"], 42)
        self.assertEqual(context["selectedCustomer"]["accountId"], 9)

    def test_customer_preflight_returns_selection_for_multiple_matches(self):
        rows = [
            {"contact_id": 1, "tenant_id": 7, "owner_user_id": 11, "account_id": 10, "company_name": "Acme Korea", "contact_name": "Chris Park"},
            {"contact_id": 2, "tenant_id": 7, "owner_user_id": 11, "account_id": 10, "company_name": "Acme Korea", "contact_name": "Dana Lee"},
        ]

        context, candidates, resolved = main.resolve_command_customer_preflight(
            FakeListCursor(rows),
            {"tenant_id": 7, "user_id": 11},
            "Acme Korea 일정 잡아줘",
            {},
        )

        self.assertEqual(context, {})
        self.assertIsNone(resolved)
        self.assertEqual({candidate["contact_id"] for candidate in candidates}, {1, 2})

    def test_customer_preflight_auto_selects_single_match(self):
        rows = [
            {"contact_id": 1, "tenant_id": 7, "owner_user_id": 11, "account_id": 10, "company_name": "Acme Korea", "contact_name": "Chris Park"},
        ]

        context, candidates, resolved = main.resolve_command_customer_preflight(
            FakeListCursor(rows),
            {"tenant_id": 7, "user_id": 11},
            "Chris Park 일정 잡아줘",
            {},
        )

        self.assertEqual(candidates, [])
        self.assertEqual(resolved["contact_id"], 1)
        self.assertEqual(context["selectedCustomer"]["contactId"], 1)

    def test_docx_text_extraction_reads_document_xml(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "word/document.xml",
                "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
                "<w:body><w:p><w:r><w:t>Quote for Acme Korea</w:t></w:r></w:p></w:body></w:document>",
            )

        text = main.extract_docx_text(buffer.getvalue())

        self.assertIn("Quote for Acme Korea", text)

    def test_xlsx_text_extraction_reads_shared_strings(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "xl/sharedStrings.xml",
                "<sst xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>"
                "<si><t>Contract Amount</t></si><si><t>1000000</t></si></sst>",
            )
            archive.writestr(
                "xl/worksheets/sheet1.xml",
                "<worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>"
                "<sheetData><row><c t='s'><v>0</v></c><c t='s'><v>1</v></c></row></sheetData></worksheet>",
            )

        text = main.extract_xlsx_text(buffer.getvalue())

        self.assertIn("Contract Amount", text)
        self.assertIn("1000000", text)

    def test_sales_document_heuristic_classifies_quote(self):
        info = main.heuristic_sales_document_info("견적서\n고객사: Acme Korea\n합계 1,200,000원", "quote.txt")

        self.assertEqual(info.document_type, "quote")
        self.assertEqual(info.company_name, "Acme Korea")
        self.assertEqual(info.total_amount, 1200000.0)

    def test_mysql_duplicate_error_is_mapped_to_conflict_code(self):
        error = mysql.connector.Error(errno=1062, msg="Duplicate entry")

        error_code, status_code, _situation, details = main.classify_mysql_error(error)

        self.assertEqual(error_code, "FSI-DB-DUPLICATE")
        self.assertEqual(status_code, 409)
        self.assertEqual(details["db_errno"], 1062)

    def test_error_response_includes_error_code_and_request_id(self):
        response = main.error_response("테스트 오류", 500, "FSI-SYSTEM-ERROR")
        body = json.loads(response.body)

        self.assertFalse(body["success"])
        self.assertEqual(body["error_code"], "FSI-SYSTEM-ERROR")
        self.assertIn("request_id", body)

    def test_agent_command_routes_sns_before_llm(self):
        route = agent_commands.route_agent_command("https://www.linkedin.com/in/hyundohbak/ 확인해줘")

        self.assertEqual(route.case_id, "sns_profile_research")
        self.assertTrue(route.requires_customer_preflight)

    def test_agent_command_routes_sales_activity(self):
        route = agent_commands.route_agent_command("Acme Korea 김철수 내일 오후 2시 미팅 일정 등록해줘")

        self.assertEqual(route.case_id, "sales_activity_schedule")
        self.assertTrue(route.requires_customer_preflight)

    def test_agent_command_fallback_is_last(self):
        route = agent_commands.route_agent_command("이번 분기 영업 전략을 정리해줘")

        self.assertEqual(route.case_id, "general_sales_agent")
        self.assertTrue(route.requires_customer_preflight)

    def test_agent_command_docs_include_flow_steps(self):
        docs = agent_commands.command_cases_for_docs()
        case_ids = [item["case_id"] for item in docs]

        self.assertEqual(case_ids[-1], "general_sales_agent")
        self.assertIn("sales_activity_schedule", case_ids)
        self.assertTrue(all(item["flow_steps"] for item in docs))


if __name__ == "__main__":
    unittest.main()
