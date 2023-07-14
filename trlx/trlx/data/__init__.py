from dataclasses import dataclass
from typing import Any, Iterable

from torchtyping import TensorType

from . import configs


@dataclass
class GeneralElement:
    """
    General element outputted by data pipeline being read by orchestrator.
    """

    pass


@dataclass
class SimElement:
    """
    Batch element for Gyarados or Gyarados-like similarity scoring model
    """

    content: Any = None
    preference: Any = None
    score: float = None


@dataclass
class RLElement:
    """
    Batch element for RL model
    """

    state: Iterable[str] = None  # Context/prompts
    action: TensorType["N"] = None  # Tokens generated by model given prompts
    reward: float = None  # Reward obtained for that generation


@dataclass
class BatchElement:
    """
    General batch element for any transformer to use in its forward pass
    """

    tokens: TensorType["BATCH", "SEQ_LEN"]
    masks: TensorType["BATCH", "SEQ_LEN"]
