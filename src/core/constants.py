"""Fixed parameters from the assignment specification."""

CHANNEL_CONFIG = {
    'bit_rate': 10_000_000,
    'forward_delay': 0.040,
    'reverse_delay': 0.010,
    'processing_delay': 0.002,
    'good_ber': 1e-6,
    'bad_ber': 5e-3,
    'p_good_to_bad': 0.002,
    'p_bad_to_good': 0.05,
}

FILE_SIZE = 100 * 1024 * 1024
TRANSPORT_HEADER_SIZE = 8
LINK_HEADER_SIZE = 24
RECEIVER_BUFFER_SIZE = 256 * 1024

WINDOW_SIZES = [2, 4, 8, 16, 32, 64]
FRAME_PAYLOADS = [128, 256, 512, 1024, 2048, 4096]
RUNS_PER_CONFIG = 10
