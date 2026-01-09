"""Gilbert-Elliot burst error channel model."""
import random


class Channel:
    """Two-state Markov channel with burst errors.

    Uses current state BER for frame error calculation. State transitions
    are probabilistic based on Markov chain parameters.
    """

    STATE_GOOD = 0
    STATE_BAD = 1

    def __init__(self, good_ber: float, bad_ber: float,
                 p_good_to_bad: float, p_bad_to_good: float,
                 rng: random.Random | None = None):
        self.good_ber = good_ber
        self.bad_ber = bad_ber
        self.p_gb = p_good_to_bad
        self.p_bg = p_bad_to_good
        self.rng = rng or random.Random()
        self.state = self.STATE_GOOD

    def reset(self):
        self.state = self.STATE_GOOD

    def transmit_frame(self, frame_bits: int) -> bool:
        """Simulate transmission of a frame through the channel."""
        ber = self.good_ber if self.state == self.STATE_GOOD else self.bad_ber
        p_no_error = (1.0 - ber) ** frame_bits
        corrupted = self.rng.random() >= p_no_error

        if self.state == self.STATE_GOOD:
            if self.rng.random() < self.p_gb:
                self.state = self.STATE_BAD
        else:
            if self.rng.random() < self.p_bg:
                self.state = self.STATE_GOOD

        return corrupted
