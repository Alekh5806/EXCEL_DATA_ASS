from pathlib import Path
from datetime import datetime

from django.core.management.base import BaseCommand
from openpyxl import Workbook


SAMPLE_HEADERS = [
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


class Command(BaseCommand):
    help = "Create a sample Excel workbook that matches the importer layout."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            default="sample_process_data.xlsx",
            help="Output .xlsx file path.",
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"])
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Data"

        worksheet.append([])
        worksheet.append(SAMPLE_HEADERS)
        worksheet.append(["Select Tags ->"])
        worksheet.append(["Units ->"])
        worksheet.append(
            [
                datetime(2025, 4, 8, 10, 0),
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
        worksheet.append(
            [
                datetime(2025, 4, 8, 11, 0),
                11.2,
                21.2,
                31.2,
                41.2,
                51.2,
                61.2,
                71.2,
                81.2,
                91.2,
                "RUNNING",
                "Second sample row",
            ]
        )

        workbook.save(output_path)
        self.stdout.write(self.style.SUCCESS(f"Created sample workbook at {output_path.resolve()}"))