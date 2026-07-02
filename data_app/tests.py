from django.test import TestCase

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
