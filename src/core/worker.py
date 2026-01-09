"""Worker functions for multiprocessing simulation runs."""
from .constants import FILE_SIZE
from .types import SimulationConfig, SimulationResult
from .engine import Simulation

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
            seed=seed
        )

    sim = Simulation(config)
    data = b'\x00' * FILE_SIZE
    sim.load_data(data)
    return sim.run(progress_callback=progress_cb)
