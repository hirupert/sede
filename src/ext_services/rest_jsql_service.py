import http
from typing import Optional, Dict

import requests

from src.ext_services.abstract_jsql_service import AbstractJSQLService


class RestJSQLService(AbstractJSQLService):
    def __init__(self):
        self._entry_point = "http://localhost:8079/sqltojson"

    def call_jsql(self, sql: str) -> Optional[Dict]:
        response = requests.post(self._entry_point, json={"sql": sql}, timeout=3)
        if response.status_code != http.HTTPStatus.OK:
            raise Exception("")
        output = response.json()
        if "timestamp" not in output.keys():
            return output
        else:
            return None
