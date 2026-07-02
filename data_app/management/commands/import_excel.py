from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from data_app.importers import import_excel_workbook
from data_app.models import ProcessData


class Command(BaseCommand):
    help = "Import process data rows from an Excel .xlsx workbook."

    def add_arguments(self, parser):
        parser.add_argument("file_path", help="Path to the Excel .xlsx file.")
        parser.add_argument(
            "--sheet",
            dest="sheet_name",
            help="Optional sheet name. If omitted, all importable sheets are scanned.",
        )
        parser.add_argument(
            "--replace-source",
            action="store_true",
            help="Delete existing rows from the same source file before importing.",
        )

    def handle(self, *args, **options):
        file_path = options["file_path"]
        sheet_name = options.get("sheet_name")
        replace_source = options["replace_source"]

        if replace_source:
            source_file = Path(file_path).name
            deleted_count, _ = ProcessData.objects.filter(source_file=source_file).delete()
            self.stdout.write(f"Deleted {deleted_count} existing rows from {source_file}.")

        try:
            result = import_excel_workbook(file_path, sheet_name=sheet_name)
        except FileNotFoundError as exc:
            raise CommandError(f"Excel file not found: {file_path}") from exc
        except KeyError as exc:
            raise CommandError(f"Sheet not found: {sheet_name}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {result['rows_created']} rows from {result['source_file']}."
            )
        )
        if result["sheets_imported"]:
            self.stdout.write(f"Sheets: {', '.join(result['sheets_imported'])}")
        else:
            self.stdout.write("No importable sheets were found.")
