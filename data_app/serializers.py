from rest_framework import serializers

from .models import ProcessData


class ProcessDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessData
        fields = [
            "id",
            "timestamp",
            "date",
            "time",
            "pygas_flow_rate",
            "biomass_flow_rate",
            "biomass_temperature",
            "reactor_gas_flow_rate",
            "reactor_gas_temperature",
            "heat_carrier_flow_rate",
            "heat_carrier_temperature",
            "product_gas_temperature",
            "heat_carrier_return_temperature",
            "stage",
            "notes",
            "source_file",
            "imported_at",
        ]
