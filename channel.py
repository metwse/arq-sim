"""
Gilbert-Elliot channel model for simulating burst errors.
"""

import random
import math


class GilbertElliotChannel:
    """
    Two-state Markov chain channel model for burst errors.

    States:
    - Good (G): Low error rate
    - Bad (B): High error rate
    """

    def __init__(self, good_ber, bad_ber, p_gb, p_bg, seed=None):
        """
        Initialize the Gilbert-Elliot channel.

        Args:
            good_ber: Bit error rate in good state
            bad_ber: Bit error rate in bad state
            p_gb: Transition probability from Good to Bad
            p_bg: Transition probability from Bad to Good
            seed: Random seed for reproducibility
        """
        self.good_ber = good_ber
        self.bad_ber = bad_ber
        self.p_gb = p_gb
        self.p_bg = p_bg

        # Start in good state
        self.state = 'G'

        # Statistics
        self.total_bits = 0
        self.error_bits = 0
        self.good_state_time = 0
        self.bad_state_time = 0

        if seed is not None:
            random.seed(seed)

    def _update_state(self):
        """Update channel state based on transition probabilities."""
        if self.state == 'G':
            if random.random() < self.p_gb:
                self.state = 'B'
                self.bad_state_time += 1
            else:
                self.good_state_time += 1
        else:  # state == 'B'
            if random.random() < self.p_bg:
                self.state = 'G'
                self.good_state_time += 1
            else:
                self.bad_state_time += 1

    def transmit_frame(self, frame_size_bytes):
        """
        Simulate transmission of a frame through the channel.

        Args:
            frame_size_bytes: Size of the frame in bytes

        Returns:
            bool: True if frame is received without errors, False otherwise
        """
        # Update state before transmission
        self._update_state()

        # Get current BER
        current_ber = self.good_ber if self.state == 'G' else self.bad_ber

        # Calculate number of bits in frame
        num_bits = frame_size_bytes * 8
        self.total_bits += num_bits

        # Calculate probability of frame error
        # P(frame error) = 1 - P(no bit errors) = 1 - (1 - BER)^num_bits
        # For small BER, we can use: P(frame error) ≈ 1 - e^(-BER * num_bits)
        p_frame_error = 1 - math.exp(-current_ber * num_bits)

        # Determine if frame has errors
        has_error = random.random() < p_frame_error

        if has_error:
            # Approximate number of bit errors for statistics
            expected_errors = current_ber * num_bits
            self.error_bits += expected_errors

        return not has_error  # Return True if no errors

    def get_statistics(self):
        """
        Get channel statistics.

        Returns:
            dict: Statistics including average BER, state distribution
        """
        total_time = self.good_state_time + self.bad_state_time

        stats = {
            'total_bits': self.total_bits,
            'error_bits': self.error_bits,
            'average_ber': self.error_bits / self.total_bits if self.total_bits > 0 else 0,
            'good_state_ratio': self.good_state_time / total_time if total_time > 0 else 0,
            'bad_state_ratio': self.bad_state_time / total_time if total_time > 0 else 0,
            'current_state': self.state
        }

        return stats

    def reset(self):
        """Reset channel to initial state."""
        self.state = 'G'
        self.total_bits = 0
        self.error_bits = 0
        self.good_state_time = 0
        self.bad_state_time = 0
