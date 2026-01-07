"""Type definitions for the ARQ simulator."""
from typing import Callable, TypedDict


class ChannelConfig(TypedDict):
    """Gilbert-Elliot channel configuration."""

    bit_rate: float
    forward_delay: float
    reverse_delay: float
    processing_delay: float
    good_ber: float
    bad_ber: float
    p_good_to_bad: float
    p_bad_to_good: float


class SimulationConfig(TypedDict):
    """Simulation run configuration."""

    window_size: int
    frame_payload_size: int
    file_size: int
    transport_header_size: int
    link_header_size: int
    receiver_buffer_size: int
    seed: int


class SimulationResult(TypedDict):
    """Result of a single simulation run."""

    window_size: int
    frame_payload_size: int
    run_id: int
    goodput: float
    retransmissions: int
    avg_rtt: float
    utilization: float
    buffer_events: int
    total_time: float


ProgressCallback = Callable[[float, str], None]
