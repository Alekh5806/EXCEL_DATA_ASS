PROCESS_DATA_SEMANTIC_LAYER = {
    "table_name": "data_app_processdata",
    "description": (
        "One row represents a process measurement captured at a specific timestamp. "
        "The table stores daily and time-series measurements imported from Excel."
    ),
    "row_grain": "One row per timestamped measurement record.",
    "common_questions": [
        "highest/lowest/average values for a measurement",
        "trend over time for a measurement",
        "comparison between two dates",
        "abnormal or outlier detection",
        "daily summary for a given date",
    ],
    "forbidden_operations": [
        "ALTER",
        "ATTACH",
        "CREATE",
        "DELETE",
        "DETACH",
        "DROP",
        "INSERT",
        "PRAGMA",
        "REPLACE",
        "TRUNCATE",
        "UPDATE",
        "VACUUM",
    ],
    "columns": {
        "timestamp": {
            "description": "Full timestamp of the measurement record.",
            "synonyms": ["time stamp", "datetime", "date time"],
        },
        "date": {
            "description": "Calendar date of the measurement.",
            "synonyms": ["day", "day of measurement"],
        },
        "time": {
            "description": "Time of day when the measurement was recorded.",
            "synonyms": ["clock time"],
        },
        "pygas_flow_rate": {
            "description": "Pyrolysis gas flow rate.",
            "synonyms": ["pygas flow", "gas flow rate"],
        },
        "biomass_flow_rate": {
            "description": "Biomass feed flow rate.",
            "synonyms": ["biomass flow"],
        },
        "biomass_temperature": {
            "description": "Biomass temperature.",
            "synonyms": ["biomass temp"],
        },
        "reactor_gas_flow_rate": {
            "description": "Reactor gas flow rate.",
            "synonyms": ["reactor gas flow"],
        },
        "reactor_gas_temperature": {
            "description": "Reactor gas temperature.",
            "synonyms": ["reactor temp", "reactor gas temp"],
        },
        "heat_carrier_flow_rate": {
            "description": "Heat carrier flow rate.",
            "synonyms": ["heat carrier flow"],
        },
        "heat_carrier_temperature": {
            "description": "Heat carrier temperature.",
            "synonyms": ["heat carrier temp"],
        },
        "product_gas_temperature": {
            "description": "Product gas temperature. This is the default temperature metric when a user asks for 'temperature'.",
            "synonyms": ["temperature", "product temperature", "product gas temp"],
        },
        "heat_carrier_return_temperature": {
            "description": "Return temperature of the heat carrier loop.",
            "synonyms": ["return temperature", "heat carrier return temp"],
        },
        "stage": {
            "description": "Process stage label imported from the spreadsheet. Treat this as a categorical text field, not a numeric stability range.",
            "synonyms": ["phase", "state", "operating stage"],
            "sample_values": ["HEAT UP", "RAMP UP", "STABLE"],
            "filter_guidance": (
                "When the user mentions a stage such as STABLE, HEAT UP, or RAMP UP, "
                "filter with stage = '<VALUE>' or a case-insensitive text comparison against the literal stage value."
            ),
        },
        "notes": {
            "description": "Free-text process notes imported from the spreadsheet.",
            "synonyms": ["comment", "remarks"],
        },
        "source_file": {
            "description": "Original Excel filename for the imported row.",
            "synonyms": ["file name"],
        },
        "imported_at": {
            "description": "Timestamp when the row was imported into the database.",
            "synonyms": ["import time"],
        },
    },
    "question_to_columns": [
        {
            "phrases": ["temperature", "temp"],
            "column": "product_gas_temperature",
            "reason": "Default temperature metric for the dataset.",
        },
        {
            "phrases": ["flow rate", "gas flow"],
            "column": "pygas_flow_rate",
            "reason": "Default flow metric for generic flow questions.",
        },
        {
            "phrases": ["stable", "heat up", "ramp up", "stage", "phase"],
            "column": "stage",
            "reason": "These phrases refer to literal categorical values in the stage column.",
        },
    ],
}


def build_semantic_layer_prompt():
    lines = []
    lines.append(f"Table: {PROCESS_DATA_SEMANTIC_LAYER['table_name']}")
    lines.append(f"Description: {PROCESS_DATA_SEMANTIC_LAYER['description']}")
    lines.append(f"Row grain: {PROCESS_DATA_SEMANTIC_LAYER['row_grain']}")
    lines.append("Common question types:")
    for item in PROCESS_DATA_SEMANTIC_LAYER["common_questions"]:
        lines.append(f"- {item}")

    lines.append("SQL guardrails:")
    lines.append("- Generate read-only SQL only.")
    lines.append("- Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, REPLACE, ATTACH, DETACH, PRAGMA, or VACUUM.")
    lines.append(
        "- Forbidden operations list: "
        + ", ".join(PROCESS_DATA_SEMANTIC_LAYER["forbidden_operations"])
    )

    lines.append("Column meanings:")
    for column_name, column_info in PROCESS_DATA_SEMANTIC_LAYER["columns"].items():
        synonyms = ", ".join(column_info.get("synonyms", []))
        lines.append(f"- {column_name}: {column_info['description']}")
        if synonyms:
            lines.append(f"  Synonyms: {synonyms}")
        sample_values = ", ".join(column_info.get("sample_values", []))
        if sample_values:
            lines.append(f"  Sample values: {sample_values}")
        filter_guidance = column_info.get("filter_guidance", "")
        if filter_guidance:
            lines.append(f"  Filter guidance: {filter_guidance}")

    lines.append("Question mapping hints:")
    for mapping in PROCESS_DATA_SEMANTIC_LAYER["question_to_columns"]:
        phrases = ", ".join(mapping["phrases"])
        lines.append(f"- If the user mentions {phrases}, prefer {mapping['column']}: {mapping['reason']}")

    return "\n".join(lines)