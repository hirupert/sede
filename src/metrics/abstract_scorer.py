from typing import List, Dict
from abc import ABC, abstractmethod


class AbstractScorer(ABC):
    @abstractmethod
    def get_name(self) -> str:
        raise NotImplementedError()

    @abstractmethod
    def __call__(self, pred_lns: List[str], tgt_lns: List[str]) -> None:
        raise NotImplementedError()

    @abstractmethod
    def get_metric(self, reset: bool = False) -> Dict[str, float]:
        raise NotImplementedError()

    @abstractmethod
    def reset(self) -> None:
        raise NotImplementedError()

    @abstractmethod
    def get_metric_names(self) -> List[str]:
        raise NotImplementedError()
