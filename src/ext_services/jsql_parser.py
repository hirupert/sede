# pylint: disable=broad-except

import http
from typing import Dict, Optional, List, Tuple

import requests

from src.metrics.partial_match_eval.jsql_reader import JSQLReader
from src.preprocessing.sql_utils import preprocess_for_jsql


class JSQLParserServiceException(Exception):
    pass


def _augment_items(items: List[Tuple[int, str]], aliases_to_tables_dict: Dict[str, str]) -> List[Tuple[int, str]]:
    augmented_items: List[Tuple[int, str]] = []
    for item in items:
        if item[1] in aliases_to_tables_dict:
            augmented_items.append((item[0], aliases_to_tables_dict[item[1]]))
        elif "." in item[1]:
            prefix = item[1].split(".")[0]
            rest = item[1].split(".")[1]
            if prefix in aliases_to_tables_dict:
                augmented_items.append((item[0], aliases_to_tables_dict[prefix] + "." + rest))
        else:
            augmented_items.append(item)
    return augmented_items


class JSQLParser:
    def __init__(self):
        service_url = "http://localhost:8079/"
        self._entry_point = service_url + "sqltojson"
        self._jsql_reader = JSQLReader()

    def _sql_to_json(self, sql: str) -> Optional[Dict]:
        # replace apostrophes with quotes, since otherwise JSQLParser might return errors. Note that this simple replace
        # might cause wrong sql queries (e.g. if there are apostrophes as part of an escaped string), so this should
        # be replaced with a smarter fix
        sql_to_parse = sql.replace("'", '"')

        try:
            response = requests.post(self._entry_point, json={"sql": sql_to_parse}, timeout=3)
            if response.status_code != http.HTTPStatus.OK:
                raise JSQLParserServiceException("")
            output = response.json()
            if "timestamp" not in output.keys():
                return output
            else:
                return None
        except Exception:
            return None

    def parse_sql(self, sql: str, clean: bool = True) -> Optional[Dict]:
        if not sql:
            return None

        try:
            if clean:
                sql = preprocess_for_jsql(sql)
                if not sql:
                    return None
            parsed_sql = self._sql_to_json(sql)
            return parsed_sql
        except JSQLParserServiceException:
            return None

    # pylint: disable=too-many-branches
    def _translate_sql(self, sql: str, clean: bool, anonymize_values: bool, parse_on_clause: bool) -> Optional[Dict]:
        parsed_sql = self.parse_sql(sql, clean)

        if not parsed_sql:
            return None

        parsed_dict = self._jsql_reader.parse_sql_to_parsed_body(
            parsed_sql, anonymize_values=anonymize_values, parse_on_clause=parse_on_clause
        )

        return parsed_dict

    def translate(
        self, sql: str, clean: bool = True, anonymize_values: bool = False, parse_on_clause: bool = True
    ) -> Optional[Dict]:
        return self._translate_sql(sql, clean=clean, anonymize_values=anonymize_values, parse_on_clause=parse_on_clause)

    def translate_batch(
        self, sql_list: List[str], clean: bool = True, anonymize_values: bool = False, parse_on_clause: bool = True
    ) -> List[Optional[Dict]]:
        return [
            self._translate_sql(sql, clean=clean, anonymize_values=anonymize_values, parse_on_clause=parse_on_clause)
            for sql in sql_list
        ]
