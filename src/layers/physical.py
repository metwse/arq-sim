"""Physical layer - Gilbert-Elliot channel model."""
from src.core.channel_config import \
    BAD_BER, GOOD_BER, P_BAD_TO_GOOD, P_GOOD_TO_BAD

import random


class Channel:
    """Gilbert-Elliot burst error channel."""

    STATE_GOOD = 0
    STATE_BAD = 1

    def __init__(self, rng_seed: int):
        """Initialize channel with transition probabilities."""
        self.rng = random.Random(rng_seed)

        self.state = self.STATE_GOOD

    def transmit_frame(self, frame_bits: int) -> bool:
        """Simulate transmission of a frame through the channel.

        Returns:
            Whether or not the frame transmitted successfully, True if an error
            occured.
        """

        error = False

        for _ in range(frame_bits):
            r = self.rng.random()

            if self.state == self.STATE_GOOD:
                if r < GOOD_BER:
                    error = True

                if r < P_GOOD_TO_BAD:
                    self.state = self.STATE_BAD
            else:
                if r < BAD_BER:
                    error = True

                if r < P_BAD_TO_GOOD:
                    self.state = self.STATE_GOOD

        return error
