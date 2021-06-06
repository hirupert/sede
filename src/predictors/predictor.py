from typing import List

from allennlp.common.util import JsonDict
from allennlp.data import Instance
from allennlp.predictors.predictor import Predictor


@Predictor.register("seq2seq2")
class Seq2SeqPredictor(Predictor):
    """
    Predictor for sequence to sequence models, including
    [`ComposedSeq2Seq`](../models/encoder_decoders/composed_seq2seq.md) and
    [`SimpleSeq2Seq`](../models/encoder_decoders/simple_seq2seq.md) and
    [`CopyNetSeq2Seq`](../models/encoder_decoders/copynet_seq2seq.md).
    """

    def _json_to_instance(self, json_dict: JsonDict) -> Instance:
        raise NotImplementedError()

    def predict_instance(self, instance: Instance) -> JsonDict:
        outputs = self._model.forward_on_instance(instance)
        outputs["predicted_tokens"] = outputs["predicted_tokens"].replace("</s>", "").strip()
        return outputs

    def predict_batch_instance(self, instances: List[Instance]) -> List[JsonDict]:
        predictions = []
        outputs = self._model.forward_on_instances(instances)
        for output in outputs:
            output["predicted_tokens"] = output["predicted_tokens"].replace("</s>", "").strip()
            predictions.append(output)
        return predictions

    def dump_line(self, outputs: JsonDict) -> str:
        query_set_id = outputs["metadata"]["query_set_id"]
        return f"{query_set_id}\t{outputs['predicted_tokens']}\n"
