"""Type definitions for the ARQ simulator."""
from typing import Callable, TypedDict


class SimulationConfig(TypedDict):
    """Simulation run configuration."""

    window_size: int
    frame_payload_size: int
    seed: int


class SimulationResult(TypedDict):
    """Result of a single simulation run."""

    window_size: int
    frame_payload_size: int
    goodput: float
    retransmissions: int
    avg_rtt: float
    utilization: float
    total_time: float


ProgressCallback = Callable[[float, str], None]
