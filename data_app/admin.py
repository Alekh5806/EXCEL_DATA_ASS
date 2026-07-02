from django.contrib import admin

from .models import ProcessData


@admin.register(ProcessData)
class ProcessDataAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "timestamp",
        "stage",
        "product_gas_temperature",
        "reactor_gas_temperature",
        "biomass_flow_rate",
        "source_file",
    )
    list_filter = ("date", "stage", "source_file")
    search_fields = ("stage", "notes", "source_file")
    ordering = ("timestamp", "id")
