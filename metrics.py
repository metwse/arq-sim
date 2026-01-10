"""
Metrics collection and calculation for ARQ simulation.
"""


class Metrics:
    """Tracks and calculates simulation metrics."""

    def __init__(self):
        """Initialize metrics counters."""
        self.frames_sent = 0
        self.frames_received = 0
        self.frames_retransmitted = 0
        self.acks_sent = 0
        self.acks_received = 0
        self.bytes_sent = 0
        self.bytes_delivered = 0
        self.start_time = 0
        self.end_time = 0

    def record_frame_sent(self, frame_size, is_retransmission=False):
        """Record a frame transmission."""
        self.frames_sent += 1
        self.bytes_sent += frame_size
        if is_retransmission:
            self.frames_retransmitted += 1

    def record_frame_received(self, frame_size):
        """Record a successful frame reception."""
        self.frames_received += 1
        self.bytes_delivered += frame_size

    def record_ack_sent(self):
        """Record an ACK transmission."""
        self.acks_sent += 1

    def record_ack_received(self):
        """Record an ACK reception."""
        self.acks_received += 1

    def set_start_time(self, time):
        """Set simulation start time."""
        self.start_time = time

    def set_end_time(self, time):
        """Set simulation end time."""
        self.end_time = time

    def get_simulation_time(self):
        """Get total simulation time in seconds."""
        return (self.end_time - self.start_time) / 1000.0

    def get_throughput(self):
        """
        Calculate throughput (total bits transmitted per second).

        Returns:
            float: Throughput in bits per second
        """
        time_sec = self.get_simulation_time()
        if time_sec == 0:
            return 0
        return (self.bytes_sent * 8) / time_sec

    def get_goodput(self):
        """
        Calculate goodput (successfully delivered bits per second).

        Returns:
            float: Goodput in bits per second
        """
        time_sec = self.get_simulation_time()
        if time_sec == 0:
            return 0
        return (self.bytes_delivered * 8) / time_sec

    def get_efficiency(self):
        """
        Calculate protocol efficiency (goodput/throughput).

        Returns:
            float: Efficiency (0-1)
        """
        throughput = self.get_throughput()
        if throughput == 0:
            return 0
        return self.get_goodput() / throughput

    def get_retransmission_rate(self):
        """
        Calculate retransmission rate.

        Returns:
            float: Ratio of retransmitted frames to total frames sent
        """
        if self.frames_sent == 0:
            return 0
        return self.frames_retransmitted / self.frames_sent

    def get_summary(self):
        """
        Get summary of all metrics.

        Returns:
            dict: Dictionary containing all metrics
        """
        return {
            'simulation_time_sec': self.get_simulation_time(),
            'frames_sent': self.frames_sent,
            'frames_received': self.frames_received,
            'frames_retransmitted': self.frames_retransmitted,
            'retransmission_rate': self.get_retransmission_rate(),
            'bytes_sent': self.bytes_sent,
            'bytes_delivered': self.bytes_delivered,
            'throughput_bps': self.get_throughput(),
            'goodput_bps': self.get_goodput(),
            'goodput_kbps': self.get_goodput() / 1000,
            'goodput_mbps': self.get_goodput() / 1_000_000,
            'efficiency': self.get_efficiency()
        }
