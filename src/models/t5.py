from functools import partial
from typing import Dict, Tuple, Any, List

import torch
import torch.nn.functional as F
from allennlp.data import Vocabulary
from allennlp.data.fields.text_field import TextFieldTensors
from allennlp.data.token_indexers.pretrained_transformer_indexer import PretrainedTransformerIndexer
from allennlp.models.model import Model
from allennlp.nn.util import sequence_cross_entropy_with_logits
from allennlp.training.metrics import Average
from overrides import overrides
from transformers import T5ForConditionalGeneration

from src.metrics.abstract_scorer import AbstractScorer
from src.metrics.bleu.bleu_scorer import BleuScorer
from src.metrics.partial_match_eval.evaluate import evaluate
from src.ext_services.jsql_parser import JSQLParser
from src.spider_evaluator import evaluate_single
from src.preprocessing.restore_oov import fix_oov


# pylint: disable=too-many-instance-attributes,too-many-arguments
@Model.register("t5")
class T5(Model):
    """
    T5 model from the paper "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer"
    (https://arxiv.org/abs/1910.10683). The T5 model here uses a language
    modeling head and thus can be used for text generation.
    """

    def __init__(
        self,
        model_name: str,
        max_decoding_steps: int,
        beam_size: int,
        vocab: Vocabulary,
        indexer: PretrainedTransformerIndexer = None,
        measure_partial_match: bool = False,
        punish_invalid_sql: bool = False,
        debug_mode: bool = False,
        measure_sql_match: bool = False,
        label_smoothing: float = None,
        cross_entropy_average: str = "batch",
    ):
        super().__init__(vocab)
        self.model = T5ForConditionalGeneration.from_pretrained(model_name)
        self._indexer = indexer or PretrainedTransformerIndexer(model_name, namespace="tokens")

        self._start_id = self.model.config.bos_token_id  # CLS
        self._decoder_start_id = self.model.config.decoder_start_token_id or self._start_id
        self._end_id = self.model.config.eos_token_id  # SEP
        self._pad_id = self.model.config.pad_token_id  # PAD

        self._max_decoding_steps = max_decoding_steps or 150
        self._beam_size = beam_size or 4

        self._measure_partial_match = measure_partial_match
        self._pcm_f1 = Average()
        self._pcm_em = Average()
        self._jsql_parser = JSQLParser.create()

        self._metric: AbstractScorer = BleuScorer()

        self._punish_invalid_sql = punish_invalid_sql
        self._debug_mode = debug_mode

        self._measure_sql_match = measure_sql_match
        if self._measure_sql_match:
            self._spider_evaluate_func = partial(
                evaluate_single.evaluate, db_dir="data/spider/database", table="data/spider/tables.json"
            )
            self._accuracy = Average()

        self._label_smoothing = label_smoothing
        self._cross_entropy_average = cross_entropy_average

        self._parsable_queries_accuracy = Average()

    # pylint: disable=arguments-differ
    @overrides
    def forward(
        self, source_tokens: TextFieldTensors, target_tokens: TextFieldTensors = None, metadata: Dict = None
    ) -> Dict[str, torch.Tensor]:
        """
        Performs the forward step of T5.

        # Parameters

        source_tokens : `TextFieldTensors`, required
            The source tokens for the encoder. We assume they are stored under the `tokens` key.
        target_tokens : `TextFieldTensors`, optional (default = `None`)
            The target tokens for the decoder. We assume they are stored under the `tokens` key. If no target
            tokens are given, the source tokens are shifted to the right by 1.

        # Returns

        `Dict[str, torch.Tensor]`
            During training, this dictionary contains the `decoder_logits` of shape `(batch_size,
            max_target_length, target_vocab_size)` and the `loss`. During inference, it contains `predictions`
            of shape `(batch_size, max_decoding_steps)` and `log_probabilities` of shape `(batch_size,)`.

        """
        inputs = source_tokens
        targets = target_tokens
        input_ids, input_mask = inputs["tokens"]["token_ids"], inputs["tokens"]["mask"]

        outputs = {}
        tgs = {}

        # If no targets are provided, then shift input to right by 1. T5 already does this internally
        # but it does not use them for loss calculation.
        if targets is not None:
            target_ids, target_mask = targets["tokens"]["token_ids"], targets["tokens"]["mask"]
        else:
            target_ids = input_ids[:, 1:]
            target_mask = input_mask[:, 1:]

        tgs["predictions"] = target_ids

        if self.training:
            self._add_loss_to_outputs(input_ids, input_mask, outputs, target_ids, target_mask)
        else:
            self._add_loss_to_outputs(input_ids, input_mask, outputs, target_ids, target_mask)

            predictions = self.model.generate(
                input_ids, num_beams=self._beam_size, max_length=self._max_decoding_steps, min_length=5
            )

            outputs["predictions"] = predictions

            self.make_output_human_readable(outputs)

            outputs["metadata"] = metadata

            if targets is not None:
                self._calculate_metrics(input_ids, outputs, target_ids, metadata)

        return outputs

    def _add_loss_to_outputs(self, input_ids, input_mask, outputs, target_ids, target_mask):
        decoder_logits = self.model(
            input_ids=input_ids,
            attention_mask=input_mask,
            decoder_input_ids=target_ids[:, :-1].contiguous(),
            decoder_attention_mask=target_mask[:, :-1].contiguous(),
            use_cache=False,
        )[0]

        outputs["decoder_logits"] = decoder_logits

        outputs["loss"] = sequence_cross_entropy_with_logits(
            decoder_logits,
            target_ids[:, 1:].contiguous(),
            target_mask[:, 1:].contiguous(),
            label_smoothing=self._label_smoothing,
            average=self._cross_entropy_average,
        )

    # pylint: disable=too-many-branches
    def _calculate_metrics(self, input_ids, outputs, target_ids, metadata: Dict):
        prediction_lines: List[str] = []
        target_lines: List[str] = []
        for index in range(input_ids.shape[0]):
            target = self._indexer.indices_to_tokens({"token_ids": target_ids[index].tolist()}, self.vocab)
            target = self._build_sentence_from_tokens(target)
            prediction_str = outputs["predicted_tokens"][index].replace("</s>", "").strip()
            prediction_str = fix_oov(prediction_str)
            target_str = target.replace("</s>", "").strip()
            target_str = fix_oov(target_str)
            prediction_lines.append(prediction_str)
            target_lines.append(target_str)
        assert len(prediction_lines) == len(target_lines)
        self._metric(prediction_lines, target_lines)

        if self._measure_partial_match:
            if self._debug_mode:
                print(prediction_lines)
            translated_predicted = self._jsql_parser.translate_batch(prediction_lines)
            translated_gold = [item["parsed_sql"] for item in metadata]

            for translated_predicted_query in translated_predicted:
                if translated_predicted_query:
                    self._parsable_queries_accuracy(1.0)
                else:
                    self._parsable_queries_accuracy(0.0)

            # PCM-F1
            pcm_f1_scores = evaluate(translated_gold, translated_predicted, self._punish_invalid_sql)
            pcm_f1_scores = [num for num in pcm_f1_scores if isinstance(num, (int, float))]
            if not pcm_f1_scores:
                if self._punish_invalid_sql:
                    self._pcm_f1(0)
            else:
                self._pcm_f1(sum(pcm_f1_scores) / len(pcm_f1_scores))

            # PCM-EM
            pcm_em_scores = evaluate(translated_gold, translated_predicted, self._punish_invalid_sql, exact_match=True)
            pcm_em_scores = [num for num in pcm_em_scores if isinstance(num, (int, float))]
            if not pcm_em_scores:
                if self._punish_invalid_sql:
                    self._pcm_em(0)
            else:
                self._pcm_em(sum(pcm_em_scores) / len(pcm_em_scores))

        # Spider's Exact-Match
        if self._measure_sql_match:
            for index, pred in enumerate(prediction_lines):
                gold = metadata[index]["gold_sql"]
                db_id = metadata[index]["db_id"]
                correct = self._spider_evaluate_func(gold, pred, db_id)
                self._accuracy(int(correct))

    @staticmethod
    def _decoder_cache_to_dict(decoder_cache):
        cache_dict = {}
        for layer_index, layer_cache in enumerate(decoder_cache):
            for attention_name, attention_cache in enumerate(layer_cache):
                for tensor_name, cache_value in attention_cache.items():
                    key = (layer_index, attention_name, tensor_name)
                    cache_dict[key] = cache_value
        return cache_dict

    @staticmethod
    def _dict_to_decoder_cache(cache_dict):
        decoder_cache = []
        for key, cache_value in cache_dict.items():
            # Split key and extract index and dict keys
            layer_idx, attention_name, tensor_name = key
            # Extend decoder_cache to fit layer_idx + 1 layers
            decoder_cache = decoder_cache + [{} for _ in range(layer_idx + 1 - len(decoder_cache))]
            cache = decoder_cache[layer_idx]
            if attention_name not in cache:
                cache[attention_name] = {}
            assert tensor_name not in cache[attention_name]
            cache[attention_name][tensor_name] = cache_value
        return decoder_cache

    def take_step(
        self, last_predictions: torch.Tensor, state: Dict[str, torch.Tensor], step: int
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Take step during beam search.

        # Parameters

        last_predictions : `torch.Tensor`
            The predicted token ids from the previous step. Shape: `(group_size,)`
        state : `Dict[str, torch.Tensor]`
            State required to generate next set of predictions
        step : `int`
            The time step in beam search decoding.


        # Returns

        `Tuple[torch.Tensor, Dict[str, torch.Tensor]]`
            A tuple containing logits for the next tokens of shape `(group_size, target_vocab_size)` and
            an updated state dictionary.
        """
        if len(last_predictions.shape) == 1:
            last_predictions = last_predictions.unsqueeze(-1)

        # Only the last predictions are needed for the decoder, but we need to pad the decoder ids
        # to not mess up the positional embeddings in the decoder.
        padding_size = 0
        if step > 0:
            padding_size = step + 1

            # pylint: disable=no-member
            padding = torch.full(
                (last_predictions.shape[0], padding_size),
                self._pad_id,
                dtype=last_predictions.dtype,
                device=last_predictions.device,
            )

            # pylint: disable=no-member
            last_predictions = torch.cat([padding, last_predictions], dim=-1)

        decoder_cache = state.get("decoder_cache")

        log_probabilities = None
        for i in range(padding_size, last_predictions.shape[1]):
            encoder_outputs = (state["encoder_states"],) if state["encoder_states"] is not None else None
            outputs = self.model(
                input_ids=state["input_ids"],
                attention_mask=state["input_mask"],
                encoder_outputs=encoder_outputs,
                decoder_input_ids=last_predictions[:, : i + 1],
                past_key_values=decoder_cache,
                use_cache=True,
            )

            decoder_log_probabilities = F.log_softmax(outputs[0][:, 0], dim=-1)

            if log_probabilities is None:
                log_probabilities = decoder_log_probabilities
            else:
                idx = last_predictions[:, i].view(-1, 1)
                log_probabilities = decoder_log_probabilities + log_probabilities.gather(dim=-1, index=idx)

            decoder_cache = outputs[1]

            state["encoder_states"] = outputs[2]

        state["decoder_cache"] = decoder_cache

        return log_probabilities, state

    @overrides
    def make_output_human_readable(self, output_dict: Dict[str, torch.Tensor]) -> Dict[str, Any]:
        """

        # Parameters

        output_dict : `Dict[str, torch.Tensor]`
            A dictionary containing a batch of predictions with key `predictions`. The tensor should have
            shape `(batch_size, max_sequence_length)`

        # Returns

        `Dict[str, Any]`
            Original `output_dict` with an additional `predicted_tokens` key that maps to a list of lists of
            tokens.

        """
        predictions = output_dict["predictions"]
        predicted_tokens = [None] * predictions.shape[0]
        for i in range(predictions.shape[0]):
            sample_predicted_tokens = self._indexer.indices_to_tokens(
                {"token_ids": predictions[i].tolist()}, self.vocab
            )

            output_tokens = self._build_sentence_from_tokens(sample_predicted_tokens)
            predicted_tokens[i] = output_tokens

        output_dict["predicted_tokens"] = predicted_tokens

        return output_dict

    @staticmethod
    def _build_sentence_from_tokens(sample_predicted_tokens):
        # add whitespaces only where needed to account for subwords
        output_tokens = ""
        for token in sample_predicted_tokens:
            token = str(token)
            if token.startswith("▁"):
                output_tokens += " "
                token = token[1:]
            if token not in ["</s>", "<s>", "<pad>"]:
                output_tokens += token
        return output_tokens

    @overrides
    def get_metrics(self, reset: bool = False) -> Dict[str, float]:
        metrics: Dict[str, float] = {}
        if not self.training:
            metrics.update(self._metric.get_metric(reset=reset))
            if self._measure_partial_match:
                metrics["partial_match_f1"] = self._pcm_f1.get_metric(reset=reset)
                metrics["partial_match_em"] = self._pcm_em.get_metric(reset=reset)
                metrics["parsable_queries_accuracy"] = self._parsable_queries_accuracy.get_metric(reset=reset)
            if self._measure_sql_match:
                metrics["exact_match_accuracy"] = self._accuracy.get_metric(reset=reset)
        return metrics
