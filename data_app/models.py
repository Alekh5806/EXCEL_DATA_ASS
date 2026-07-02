from django.db import models


class ProcessData(models.Model):
    timestamp = models.DateTimeField(null=True, blank=True, db_index=True)
    date = models.DateField(null=True, blank=True, db_index=True)
    time = models.TimeField(null=True, blank=True)

    pygas_flow_rate = models.FloatField(null=True, blank=True)
    biomass_flow_rate = models.FloatField(null=True, blank=True)
    biomass_temperature = models.FloatField(null=True, blank=True)
    reactor_gas_flow_rate = models.FloatField(null=True, blank=True)
    reactor_gas_temperature = models.FloatField(null=True, blank=True)
    heat_carrier_flow_rate = models.FloatField(null=True, blank=True)
    heat_carrier_temperature = models.FloatField(null=True, blank=True)
    product_gas_temperature = models.FloatField(null=True, blank=True)
    heat_carrier_return_temperature = models.FloatField(null=True, blank=True)

    stage = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    source_file = models.CharField(max_length=255, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp", "id"]
        indexes = [
            models.Index(fields=["date", "time"]),
            models.Index(fields=["stage"]),
        ]

    def __str__(self):
        label = self.timestamp or self.date or "No timestamp"
        return f"{label} - {self.stage or 'No stage'}"
