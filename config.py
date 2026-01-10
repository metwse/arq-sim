"""
Configuration module for ARQ simulation.
Contains all simulation parameters and constants.
"""

# Timing parameters (in milliseconds)
FORWARD_DELAY = 40  # Data frame propagation delay (ms)
REVERSE_DELAY = 10  # ACK frame propagation delay (ms)
PROCESSING_DELAY = 2  # Processing delay per frame (ms)

# Gilbert-Elliot channel model parameters
GOOD_BER = 1e-6  # Good state bit error rate
BAD_BER = 5e-3   # Bad state bit error rate
P_GB = 0.002     # Transition probability from Good to Bad
P_BG = 0.05      # Transition probability from Bad to Good

# Protocol parameters
WINDOW_SIZES = [2, 4, 8, 16, 32, 64]
FRAME_SIZES = [128, 256, 512, 1024, 2048, 4096]  # bytes

# Frame overhead (for header, checksum, etc.)
FRAME_HEADER_SIZE = 20  # bytes

# File sizes for simulation
TEST_FILE_SIZE = 100 * 1024  # 100 KB for testing
FULL_FILE_SIZE = 10 * 1024 * 1024  # 10 MB for full simulation

# Simulation parameters
NUM_RUNS = 5  # Number of simulation runs for averaging
RANDOM_SEED = 42  # For reproducibility

# Timeout parameters
TIMEOUT_MULTIPLIER = 2.5  # Timeout = RTT * multiplier
MIN_TIMEOUT = 100  # Minimum timeout in ms


def get_rtt():
    """Calculate round-trip time including processing delays."""
    return FORWARD_DELAY + REVERSE_DELAY + 2 * PROCESSING_DELAY


def get_timeout():
    """Calculate timeout value for retransmission."""
    return max(MIN_TIMEOUT, get_rtt() * TIMEOUT_MULTIPLIER)


def get_all_configs():
    """Generate all combinations of window sizes and frame sizes."""
    configs = []
    for window_size in WINDOW_SIZES:
        for frame_size in FRAME_SIZES:
            configs.append({
                'window_size': window_size,
                'frame_size': frame_size
            })
    return configs
