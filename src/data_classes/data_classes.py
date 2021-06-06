# pylint: disable=too-many-instance-attributes

from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class AnnotatedSQL:
    query_set_id: int
    title: str
    query_body: str
    db_id: str
    description: Optional[str] = None
    cleaned_title: Optional[str] = None
    cleaned_description: Optional[str] = None
    cleaned_query_body: Optional[str] = None
    cleaned_query_body_with_values: Optional[str] = None
    schema: Optional[Dict] = None
    parsed_sql: Optional[Dict] = None
