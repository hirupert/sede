from abc import abstractmethod, ABC
from typing import Dict, Optional


class AbstractJSQLService(ABC):
    @abstractmethod
    def call_jsql(self, sql: str) -> Optional[Dict]:
        raise NotImplementedError()
