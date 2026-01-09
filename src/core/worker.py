"""Worker functions for multiprocessing simulation runs."""
from src.core.constants import (
    TRANSPORT_HEADER_SIZE, LINK_HEADER_SIZE, RECEIVER_BUFFER_SIZE, FILE_SIZE
)
from src.core.types import SimulationConfig, SimulationResult
from src.core.engine import Simulation

from typing import Callable, Optional


def run_single_simulation(args: tuple[int, int, int] | SimulationConfig,
                          progress_cb: Optional[Callable] = None
                          ) -> SimulationResult:
    """Run a single simulation with given parameters.

    Args should be (window_size, frame_payload_size, seed).
    Returns SimulationResult dict.
    """
    if isinstance(args, dict):
        config = args
    else:
        window_size, frame_payload_size, seed = args

        config = SimulationConfig(
            window_size=window_size,
            frame_payload_size=frame_payload_size,
            file_size=FILE_SIZE,
            transport_header_size=TRANSPORT_HEADER_SIZE,
            link_header_size=LINK_HEADER_SIZE,
            receiver_buffer_size=RECEIVER_BUFFER_SIZE,
            seed=seed
        )

    sim = Simulation(config)
    data = b'\x00' * FILE_SIZE
    sim.load_data(data)
    return sim.run(progress_callback=progress_cb)
