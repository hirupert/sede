import re
from random import Random
from typing import Dict, Optional


SQL_TOKENS = {
    "select",
    "from",
    "where",
    "group",
    "order",
    "limit",
    "intersect",
    "union",
    "except",
    "join",
    "on",
    "as",
    "not",
    "between",
    "=",
    ">",
    "<",
    ">=",
    "<=",
    "!=",
    "in",
    "like",
    "is",
    "exists",
    "none",
    "max",
    "min",
    "count",
    "sum",
    "avg",
    "or",
    "and",
}


def clean_str(target: str) -> Optional[str]:
    if not target:
        return None

    target = re.sub(r"[^\x00-\x7f]", r" ", target)
    line = re.sub(r"''", r" ", target)
    line = re.sub(r"``", r" ", line)
    line = re.sub(r"\"", r"'", line)
    line = re.sub(r" +", " ", line)
    return line.strip()


def add_schema_description(
    lower: bool, add_column_types: bool, tables_json: Dict, shuffle_schema: bool, random: Random
):

    table_names = tables_json["table_names_original"]

    if shuffle_schema:
        random.shuffle(table_names)

    columns = [
        (column_name[0], column_name[1], column_type)
        for column_name, column_type in zip(tables_json["column_names_original"], tables_json["column_types"])
    ]
    schema_description = ""
    schema_structured = {}
    for table_index, table_name in enumerate(table_names):
        if lower:
            table_name = table_name.lower()
        if table_index == 0:
            schema_description += "<TAB> " + table_name
        else:
            schema_description += " <TAB> " + table_name
        schema_structured[table_name] = []
        schema_description += " <COL>"
        table_columns = [column for column in columns if column[0] == table_index]

        if shuffle_schema:
            random.shuffle(table_columns)

        for table_column in table_columns:
            if add_column_types:
                column_desc = (
                    f"<type: "
                    f"{table_column[2].lower() if lower else table_column[2]}> "
                    f"{table_column[1].lower() if lower else table_column[1]}"
                )
            else:
                column_desc = f"{table_column[1].lower() if lower else table_column[1]}"
            schema_description += " " + column_desc
            schema_structured[table_name].append(column_desc)

    return schema_description, schema_structured
