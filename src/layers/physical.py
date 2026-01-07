"""Gilbert-Elliot burst error channel model."""
import random


class Channel:
    """Two-state Markov channel with burst errors.

    Models a Gilbert-Elliot channel where the channel alternates between
    a good state (low BER) and a bad state (high BER).
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

    def _transition(self):
        if self.state == self.STATE_GOOD:
            if self.rng.random() < self.p_gb:
                self.state = self.STATE_BAD
        else:
            if self.rng.random() < self.p_bg:
                self.state = self.STATE_GOOD

    def transmit_frame(self, frame_bits: int) -> bool:
        """Simulate transmission of a frame through the channel.

        Returns True if frame is corrupted, False otherwise.
        """
        ber = self.good_ber if self.state == self.STATE_GOOD else self.bad_ber

        for _ in range(frame_bits):
            self._transition()
            if self.rng.random() < ber:
                return True

        return False
