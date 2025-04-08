def field_to_sql(field):
    name = field.name
    mode = field.mode or "NULLABLE"
    typ = (field.type or "").upper()

    if typ in {"RECORD", "STRUCT"}:
        subfields = ", ".join(field_to_sql(f) for f in field.fields or [])
        sql_type = f"STRUCT<{subfields}>"
    else:
        sql_type = typ

    if mode == "REPEATED":
        return f"{name} ARRAY<{sql_type}>"
    nullable = "" if mode == "REQUIRED" else "NULL"
    return f"{name} {sql_type} {nullable}".strip()


def bigquery_schema_to_sql(schema: list, table_name: str) -> str:
    columns = ",\n  ".join(field_to_sql(f) for f in schema)
    return f"CREATE TABLE `{table_name}` (\n  {columns}\n);"
