# pylint: disable=too-many-arguments

from typing import Any, Dict, List, Tuple

import torch
import transformers
from allennlp.training.optimizers import Optimizer, make_parameter_groups


@Optimizer.register("huggingface_adafactor")
class HuggingfaceAdafactorOptimizer(Optimizer, transformers.Adafactor):
    """
    Registered as an `Optimizer` with name "huggingface_adafactor".
    """

    def __init__(
        self,
        model_parameters: List[Tuple[str, torch.nn.Parameter]],
        parameter_groups: List[Tuple[List[str], Dict[str, Any]]] = None,
        lr: float = None,
        eps: Tuple[float, float] = (1e-30, 1e-3),
        clip_threshold: float = 1.0,
        decay_rate: float = -0.8,
        beta1: float = None,
        weight_decay: float = 0.0,
        scale_parameter: bool = True,
        relative_step: bool = True,
        warmup_init: bool = False,
    ):
        super().__init__(
            params=make_parameter_groups(model_parameters, parameter_groups),
            lr=lr,
            eps=eps,
            clip_threshold=clip_threshold,
            decay_rate=decay_rate,
            beta1=beta1,
            weight_decay=weight_decay,
            scale_parameter=scale_parameter,
            relative_step=relative_step,
            warmup_init=warmup_init,
        )
