"""Physical layer - Gilbert-Elliot channel model."""
import random


class Channel:
    """Gilbert-Elliot burst error channel."""

    STATE_GOOD = 0
    STATE_BAD = 1

    def __init__(self, good_ber: float, bad_ber: float,
                 p_good_to_bad: float, p_bad_to_good: float,
                 rng: random.Random):
        """Initialize channel with transition probabilities.

        Args:
            good_ber: Bit error rate in good state
            bad_ber: Bit error rate in bad state
            p_good_to_bad: Probability of transition from good to bad
            p_bad_to_good: Probability of transition from bad to good
            rng: Random number generator for reproducibility
        """
        self.good_ber = good_ber
        self.bad_ber = bad_ber
        self.p_gb = p_good_to_bad
        self.p_bg = p_bad_to_good
        self.rng = rng
        self.state = self.STATE_GOOD

    def transmit_frame(self, frame_bits: int) -> bool:
        """Simulate frame transmission through channel.

        Args:
            frame_bits: Number of bits in the frame

        Returns:
            True if frame is corrupted, False otherwise
        """
        _ = frame_bits

        raise NotImplementedError(
            "Implement Gilbert-Elliot channel simulation")
