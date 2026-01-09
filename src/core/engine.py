"""Core simulation engine for ARQ protocol."""

from .types import SimulationConfig, SimulationResult, ProgressCallback

from dataclasses import dataclass


@dataclass
class SimulationStats:
    """Runtime statistics for a simulation."""

    start_time: float = 0.0
    end_time: float = 0.0
    bytes_delivered: int = 0
    retransmissions: int = 0
    rtt_samples: list[float] | None = None
    buffer_events: int = 0

    def __post_init__(self):
        if self.rtt_samples is None:
            self.rtt_samples = []


class Simulation:
    """Discrete event simulation of Selective Repeat ARQ over burst channel."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.stats = SimulationStats()

        raise NotImplementedError(
            "Initialize channel, sender, receiver, transport")

    def load_data(self, data: bytes):
        """Load data to be transmitted."""

        _ = data

        raise NotImplementedError("Initialize transport sender with data")

    def run(self, progress_callback: ProgressCallback | None = None
            ) -> SimulationResult:
        """Run the simulation until all data is delivered.

        Returns:
            SimulationResult with performance metrics"""

        _ = progress_callback

        raise NotImplementedError("Implement main simulation loop")

    def _build_result(self) -> SimulationResult:
        """Build final simulation result from statistics."""

        raise NotImplementedError("Calculate goodput, utilization, etc.")
