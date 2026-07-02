from io import BytesIO
from tempfile import NamedTemporaryFile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from openpyxl import Workbook

from .importers import import_excel_workbook
from .llm_answer import build_answer_prompt, build_fallback_answer
from .llm_sql import build_sql_prompt
from .models import ProcessData
from .sql_runner import run_safe_select_sql
from .sql_security import ensure_limit, validate_select_sql


class ProcessDataModelTests(TestCase):
    def test_process_data_can_store_excel_row_values(self):
        row = ProcessData.objects.create(
            product_gas_temperature=418.77,
            biomass_flow_rate=0,
            stage="HEAT UP",
            notes="Sample process note",
            source_file="sample.xlsx",
        )

        self.assertEqual(ProcessData.objects.count(), 1)
        self.assertEqual(row.stage, "HEAT UP")
        self.assertEqual(row.product_gas_temperature, 418.77)


class ExcelImporterTests(TestCase):
    def test_import_excel_workbook_creates_process_data_rows(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Data"
        worksheet.append([])
        worksheet.append(
            [
                "Description ->",
                "PYGAS FLOW RATE",
                "BIOMASS FLOW RATE",
                "BIOMASS TEMPERATURE",
                "REACTOR GAS FLOW RATE",
                "REACTOR GAS TEMPERATURE",
                "HEAT CARRIER FLOW RATE",
                "HEAT CARRIER TEMPERATURE",
                "PRODUCT GAS TEMPERATURE",
                "HEAT CARRIER RETURN TEMPERATURE",
                "COMMENTS 1\n(STAGE)",
                "COMMENTS 2\n(PROCESS NOTES)",
            ]
        )
        worksheet.append(["Select Tags ->"])
        worksheet.append(["Units ->"])
        worksheet.append(
            [
                timezone.datetime(2025, 4, 8, 10, 0),
                10.5,
                20.5,
                30.5,
                40.5,
                50.5,
                60.5,
                70.5,
                80.5,
                90.5,
                "HEAT UP",
                "Sample note",
            ]
        )

        temporary_file = NamedTemporaryFile(suffix=".xlsx")
        workbook.save(temporary_file.name)

        result = import_excel_workbook(temporary_file.name)
        row = ProcessData.objects.get()

        self.assertEqual(result["rows_created"], 1)
        self.assertEqual(row.date.isoformat(), "2025-04-08")
        self.assertEqual(row.product_gas_temperature, 80.5)
        self.assertEqual(row.stage, "HEAT UP")
        self.assertEqual(row.notes, "Sample note")


class ProcessDataApiTests(TestCase):
    def setUp(self):
        ProcessData.objects.create(
            timestamp=timezone.make_aware(timezone.datetime(2025, 4, 8, 10, 0)),
            date=timezone.datetime(2025, 4, 8).date(),
            time=timezone.datetime(2025, 4, 8, 10, 0).time(),
            product_gas_temperature=80,
            reactor_gas_temperature=50,
            biomass_flow_rate=20,
            stage="HEAT UP",
            notes="First row",
            source_file="sample.xlsx",
        )
        ProcessData.objects.create(
            timestamp=timezone.make_aware(timezone.datetime(2025, 4, 8, 11, 0)),
            date=timezone.datetime(2025, 4, 8).date(),
            time=timezone.datetime(2025, 4, 8, 11, 0).time(),
            product_gas_temperature=90,
            reactor_gas_temperature=55,
            biomass_flow_rate=30,
            stage="RUNNING",
            notes="Second row",
            source_file="sample.xlsx",
        )
        ProcessData.objects.create(
            timestamp=timezone.make_aware(timezone.datetime(2025, 4, 9, 10, 0)),
            date=timezone.datetime(2025, 4, 9).date(),
            time=timezone.datetime(2025, 4, 9, 10, 0).time(),
            product_gas_temperature=70,
            reactor_gas_temperature=45,
            biomass_flow_rate=10,
            stage="COOLING",
            notes="Third row",
            source_file="sample.xlsx",
        )

    def test_data_api_returns_rows_filtered_by_date(self):
        response = self.client.get("/api/data/?date=2025-04-08")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual(len(response.json()["results"]), 2)

    def test_summary_api_returns_summary_for_date(self):
        response = self.client.get("/api/summary/?date=2025-04-08")

        self.assertEqual(response.status_code, 200)
        summary = response.json()["summary"]
        self.assertEqual(summary["row_count"], 2)
        self.assertEqual(summary["product_gas_temperature"]["maximum"], 90)
        self.assertEqual(summary["product_gas_temperature"]["minimum"], 80)

    def test_stats_api_returns_requested_operation(self):
        response = self.client.get(
            "/api/stats/?column=product_gas_temperature&operation=max&date=2025-04-08"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["value"], 90)

    def test_stats_api_supports_column_alias(self):
        response = self.client.get(
            "/api/stats/?column=temperature&operation=average&date=2025-04-08"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["column"], "product_gas_temperature")
        self.assertEqual(response.json()["value"], 85)

    def test_chat_api_answers_highest_temperature_question(self):
        response = self.client.post(
            "/api/chat/",
            {"message": "What was the highest temperature on April 8?"},
            content_type="application/json",
        )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["data"], [{"value": 90}])
        self.assertIn("highest product gas temperature", body["answer"])
        self.assertEqual(
            body["sql"],
            "SELECT MAX(product_gas_temperature) AS value FROM data_app_processdata "
            "WHERE date = '2025-04-08';",
        )

    def test_chat_api_asks_for_clarification_when_question_is_unclear(self):
        response = self.client.post(
            "/api/chat/",
            {"message": "Tell me something interesting"},
            content_type="application/json",
        )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["sql"], "")
        self.assertEqual(body["data"], [])
        self.assertIn("Please ask", body["answer"])

    def test_chat_api_returns_chart_data_for_trend_question(self):
        response = self.client.post(
            "/api/chat/",
            {"message": "Show temperature trend on April 8"},
            content_type="application/json",
        )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["chart"]["type"], "line")
        self.assertEqual(body["chart"]["xKey"], "time")
        self.assertEqual(body["chart"]["yKey"], "product_gas_temperature")
        self.assertEqual(
            body["data"],
            [
                {"time": "10:00", "product_gas_temperature": 80.0},
                {"time": "11:00", "product_gas_temperature": 90.0},
            ],
        )

    def test_chat_api_returns_daily_summary(self):
        response = self.client.post(
            "/api/chat/",
            {"message": "Summarize April 8"},
            content_type="application/json",
        )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Summary for 2025-04-08", body["answer"])
        self.assertEqual(len(body["data"]), 9)

    def test_chat_api_compares_two_dates(self):
        response = self.client.post(
            "/api/chat/",
            {"message": "Compare temperature April 8 and April 9"},
            content_type="application/json",
        )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["chart"]["xKey"], "date")
        self.assertEqual(body["chart"]["yKey"], "average")
        self.assertEqual(body["data"][0]["date"], "2025-04-08")
        self.assertEqual(body["data"][1]["date"], "2025-04-09")

    def test_chat_api_detects_abnormal_values(self):
        for index, value in enumerate([82, 85, 88, 84, 87], start=12):
            ProcessData.objects.create(
                timestamp=timezone.make_aware(timezone.datetime(2025, 4, 8, index, 0)),
                date=timezone.datetime(2025, 4, 8).date(),
                time=timezone.datetime(2025, 4, 8, index, 0).time(),
                product_gas_temperature=value,
                stage="RUNNING",
                source_file="sample.xlsx",
            )
        ProcessData.objects.create(
            timestamp=timezone.make_aware(timezone.datetime(2025, 4, 8, 18, 0)),
            date=timezone.datetime(2025, 4, 8).date(),
            time=timezone.datetime(2025, 4, 8, 18, 0).time(),
            product_gas_temperature=500,
            stage="RUNNING",
            source_file="sample.xlsx",
        )

        response = self.client.post(
            "/api/chat/",
            {"message": "Detect abnormal temperature on April 8"},
            content_type="application/json",
        )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertIn("abnormal product gas temperature", body["answer"])
        self.assertEqual(body["data"][0]["reason"], "above expected range")

    def test_upload_excel_api_imports_uploaded_workbook(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Data"
        worksheet.append([])
        worksheet.append(
            [
                "Description ->",
                "PYGAS FLOW RATE",
                "BIOMASS FLOW RATE",
                "BIOMASS TEMPERATURE",
                "REACTOR GAS FLOW RATE",
                "REACTOR GAS TEMPERATURE",
                "HEAT CARRIER FLOW RATE",
                "HEAT CARRIER TEMPERATURE",
                "PRODUCT GAS TEMPERATURE",
                "HEAT CARRIER RETURN TEMPERATURE",
                "COMMENTS 1\n(STAGE)",
                "COMMENTS 2\n(PROCESS NOTES)",
            ]
        )
        worksheet.append(["Select Tags ->"])
        worksheet.append(["Units ->"])
        worksheet.append(
            [
                timezone.datetime(2025, 4, 10, 10, 0),
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                9,
                "TEST",
                "Uploaded row",
            ]
        )
        stream = BytesIO()
        workbook.save(stream)
        stream.seek(0)

        upload = SimpleUploadedFile(
            "uploaded.xlsx",
            stream.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(
            "/api/upload/",
            {"file": upload, "replace_source": "true"},
        )

        body = response.json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(body["source_file"], "uploaded.xlsx")
        self.assertEqual(body["rows_created"], 1)
        self.assertTrue(ProcessData.objects.filter(source_file="uploaded.xlsx").exists())

    @patch("data_app.chatbot.generate_final_answer")
    @patch("data_app.chatbot.generate_sql_from_question")
    def test_chat_api_runs_llm_sql_and_generates_final_answer(
        self, mock_generate_sql, mock_generate_final_answer
    ):
        mock_generate_sql.return_value = {
            "sql": (
                "SELECT MAX(product_gas_temperature) AS value "
                "FROM data_app_processdata WHERE date = '2025-04-08';"
            ),
            "explanation": "Gets the highest product gas temperature for April 8.",
            "clarification_question": "",
            "used_llm": True,
        }
        mock_generate_final_answer.return_value = "The highest temperature was 90."

        response = self.client.post(
            "/api/chat/",
            {"message": "What was the highest temperature on April 8?"},
            content_type="application/json",
        )

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["answer"], "The highest temperature was 90.")
        self.assertEqual(body["data"], [{"value": 90.0}])
        mock_generate_final_answer.assert_called_once()


class NaturalLanguageToSqlTests(TestCase):
    def test_select_sql_for_allowed_table_is_valid(self):
        sql = (
            "SELECT MAX(product_gas_temperature) AS value "
            "FROM data_app_processdata WHERE date = '2025-04-08';"
        )

        is_safe, message = validate_select_sql(sql)

        self.assertTrue(is_safe)
        self.assertEqual(message, "SQL is safe.")

    def test_non_select_sql_is_blocked(self):
        is_safe, message = validate_select_sql("DROP TABLE data_app_processdata;")

        self.assertFalse(is_safe)
        self.assertEqual(message, "Only SELECT queries are allowed.")

    def test_sql_for_unknown_table_is_blocked(self):
        is_safe, message = validate_select_sql("SELECT * FROM auth_user;")

        self.assertFalse(is_safe)
        self.assertEqual(message, "Query uses a table that is not allowed.")

    def test_limit_is_added_when_missing(self):
        sql = ensure_limit("SELECT id, date FROM data_app_processdata;")

        self.assertEqual(sql, "SELECT id, date FROM data_app_processdata LIMIT 100;")

    def test_prompt_contains_safety_rules(self):
        prompt = build_sql_prompt("highest temperature on April 8")

        self.assertIn("Only generate SELECT queries", prompt)
        self.assertIn("data_app_processdata", prompt)
        self.assertIn("product_gas_temperature", prompt)


class SafeSqlRunnerTests(TestCase):
    def setUp(self):
        ProcessData.objects.create(
            timestamp=timezone.make_aware(timezone.datetime(2025, 4, 8, 10, 0)),
            date=timezone.datetime(2025, 4, 8).date(),
            time=timezone.datetime(2025, 4, 8, 10, 0).time(),
            product_gas_temperature=80,
            stage="HEAT UP",
            source_file="sample.xlsx",
        )
        ProcessData.objects.create(
            timestamp=timezone.make_aware(timezone.datetime(2025, 4, 8, 11, 0)),
            date=timezone.datetime(2025, 4, 8).date(),
            time=timezone.datetime(2025, 4, 8, 11, 0).time(),
            product_gas_temperature=90,
            stage="RUNNING",
            source_file="sample.xlsx",
        )

    def test_safe_sql_runner_executes_valid_select(self):
        result = run_safe_select_sql(
            "SELECT MAX(product_gas_temperature) AS value "
            "FROM data_app_processdata WHERE date = '2025-04-08';"
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], [{"value": 90.0}])
        self.assertEqual(result["columns"], ["value"])

    def test_safe_sql_runner_blocks_unsafe_sql(self):
        result = run_safe_select_sql("DELETE FROM data_app_processdata;")

        self.assertFalse(result["ok"])
        self.assertEqual(result["data"], [])
        self.assertEqual(result["sql"], "DELETE FROM data_app_processdata;")
        self.assertIn("Only SELECT queries are allowed", result["error"])

    def test_safe_sql_runner_adds_limit_to_row_queries(self):
        result = run_safe_select_sql(
            "SELECT id, product_gas_temperature FROM data_app_processdata;"
        )

        self.assertTrue(result["ok"])
        self.assertTrue(result["sql"].endswith(" LIMIT 100;"))
        self.assertEqual(len(result["data"]), 2)


class FinalAnswerTests(TestCase):
    def test_fallback_answer_for_single_value_result(self):
        answer = build_fallback_answer([{"value": 90.123456}])

        self.assertEqual(answer, "The result is 90.1235.")

    def test_fallback_answer_mentions_missing_data(self):
        answer = build_fallback_answer([])

        self.assertEqual(answer, "I ran the query, but no matching data was found.")

    def test_answer_prompt_forbids_hallucination(self):
        prompt = build_answer_prompt(
            "What was the highest temperature on April 8?",
            "SELECT MAX(product_gas_temperature) AS value FROM data_app_processdata;",
            [{"value": 90}],
            "Gets the highest temperature.",
        )

        self.assertIn("Answer only from the SQL result", prompt)
        self.assertIn("Do not invent", prompt)
        self.assertIn('"value": 90', prompt)
