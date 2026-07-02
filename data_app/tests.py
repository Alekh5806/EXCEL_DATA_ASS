from tempfile import NamedTemporaryFile

from django.test import TestCase
from django.utils import timezone
from openpyxl import Workbook

from .importers import import_excel_workbook
from .models import ProcessData


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
