from typing import Dict, List

from sacrebleu import corpus_bleu

from metrics.abstract_scorer import AbstractScorer


class BleuScorer(AbstractScorer):
    def __init__(self, lowercase: bool = True):
        self._predicted_lines: List[str] = []
        self._target_lines: List[str] = []
        self._lowercase = lowercase

    # pylint: disable=no-self-use
    def get_name(self) -> str:
        return "bleu"

    def __call__(self, pred_lns: List[str], tgt_lns: List[str]) -> None:
        self._predicted_lines.extend(pred_lns)
        self._target_lines.extend(tgt_lns)

    def reset(self) -> None:
        self._predicted_lines = []
        self._target_lines = []

    def get_metric(self, reset: bool = False) -> Dict[str, float]:
        assert len(self._predicted_lines) == len(self._target_lines)
        bleu = round(corpus_bleu(self._predicted_lines, [self._target_lines], lowercase=self._lowercase).score, 4)
        if reset:
            self.reset()

        return {self.get_metric_names()[0]: bleu}

    # pylint: disable=no-self-use
    def get_metric_names(self) -> List[str]:
        return ["BLEU"]
