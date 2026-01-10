"""
Event-driven simulator for Selective Repeat ARQ protocol.
"""

import heapq
import math

from channel import GilbertElliotChannel
from metrics import Metrics
import config


class Event:
    """Represents a simulation event."""

    def __init__(self, time, event_type, data=None):
        self.time = time
        self.event_type = event_type
        self.data = data or {}

    def __lt__(self, other):
        """For heap ordering."""
        return self.time < other.time


class ARQSimulator:
    """
    Event-driven Selective Repeat ARQ simulator with asymmetric delays.
    """

    def __init__(self, window_size, frame_size, file_size, seed=None):
        """
        Initialize the ARQ simulator.

        Args:
            window_size: Send window size (W)
            frame_size: Frame payload size in bytes (L)
            file_size: Total file size to transmit in bytes
            seed: Random seed for reproducibility
        """
        self.window_size = window_size
        self.frame_size = frame_size
        self.file_size = file_size
        self.seed = seed

        # Calculate total number of frames
        self.total_frames = math.ceil(file_size / frame_size)

        # Initialize channel
        self.channel = GilbertElliotChannel(
            config.GOOD_BER,
            config.BAD_BER,
            config.P_GB,
            config.P_BG,
            seed=seed
        )

        # Initialize metrics
        self.metrics = Metrics()

        # Event queue
        self.event_queue = []
        self.current_time = 0

        # Sender state
        self.send_base = 0  # Base of send window
        self.next_seq_num = 0  # Next frame to send
        self.sent_frames = {}  # {seq_num: send_time}
        self.acked_frames = set()  # Set of acknowledged frame numbers

        # Receiver state
        self.expected_frames = set(range(self.total_frames))  # Frames we expect
        self.received_frames = set()  # Successfully received frames

        # Timeout value
        self.timeout = config.get_timeout()

    def _schedule_event(self, delay, event_type, data=None):
        """Schedule an event."""
        event = Event(self.current_time + delay, event_type, data)
        heapq.heappush(self.event_queue, event)

    def _send_frame(self, seq_num):
        """Send a data frame."""
        # Check if already acknowledged
        if seq_num in self.acked_frames:
            return

        # Determine if this is a retransmission
        is_retrans = seq_num in self.sent_frames

        # Record metrics
        total_frame_size = self.frame_size + config.FRAME_HEADER_SIZE
        self.metrics.record_frame_sent(total_frame_size, is_retrans)

        # Update sent frames tracking
        self.sent_frames[seq_num] = self.current_time

        # Schedule frame arrival at receiver after forward delay + processing
        self._schedule_event(
            config.FORWARD_DELAY + config.PROCESSING_DELAY,
            'FRAME_ARRIVAL',
            {'seq_num': seq_num, 'frame_size': total_frame_size}
        )

        # Schedule timeout
        self._schedule_event(
            self.timeout,
            'TIMEOUT',
            {'seq_num': seq_num, 'send_time': self.current_time}
        )

    def _handle_frame_arrival(self, data):
        """Handle frame arrival at receiver."""
        seq_num = data['seq_num']
        frame_size = data['frame_size']

        # Check if already received
        if seq_num in self.received_frames:
            # Duplicate frame, send ACK anyway
            self._send_ack(seq_num)
            return

        # Simulate transmission through channel
        success = self.channel.transmit_frame(frame_size)

        if success:
            # Frame received successfully
            self.received_frames.add(seq_num)
            self.metrics.record_frame_received(self.frame_size)  # Only payload counts

            # Send ACK
            self._send_ack(seq_num)
        # If frame has errors, it's silently dropped (no ACK sent)

    def _send_ack(self, seq_num):
        """Send an ACK frame."""
        self.metrics.record_ack_sent()

        # Schedule ACK arrival at sender after reverse delay + processing
        self._schedule_event(
            config.REVERSE_DELAY + config.PROCESSING_DELAY,
            'ACK_ARRIVAL',
            {'seq_num': seq_num}
        )

    def _handle_ack_arrival(self, data):
        """Handle ACK arrival at sender."""
        seq_num = data['seq_num']

        self.metrics.record_ack_received()

        # Mark frame as acknowledged
        self.acked_frames.add(seq_num)

        # Update send window base if this ACK is for the base
        while self.send_base in self.acked_frames and self.send_base < self.total_frames:
            self.send_base += 1

        # Try to send new frames
        self._send_new_frames()

    def _handle_timeout(self, data):
        """Handle timeout event."""
        seq_num = data['seq_num']
        send_time = data['send_time']

        # Check if this timeout is still valid
        # (frame might have been ACKed after timeout was scheduled)
        if seq_num in self.acked_frames:
            return

        # Check if this is the most recent send time for this frame
        if seq_num in self.sent_frames and self.sent_frames[seq_num] == send_time:
            # Retransmit the frame
            self._send_frame(seq_num)

    def _send_new_frames(self):
        """Send new frames within the window."""
        while (self.next_seq_num < self.total_frames and
               self.next_seq_num < self.send_base + self.window_size):
            self._send_frame(self.next_seq_num)
            self.next_seq_num += 1

    def _is_complete(self):
        """Check if all frames have been received."""
        return len(self.received_frames) == self.total_frames

    def run(self):
        """
        Run the simulation.

        Returns:
            dict: Simulation results including metrics and channel statistics
        """
        # Initialize
        self.current_time = 0
        self.metrics.set_start_time(self.current_time)

        # Start sending initial frames
        self._send_new_frames()

        # Event loop
        max_iterations = 1_000_000  # Safety limit
        iterations = 0

        while self.event_queue and not self._is_complete() and iterations < max_iterations:
            iterations += 1

            # Get next event
            event = heapq.heappop(self.event_queue)
            self.current_time = event.time

            # Handle event
            if event.event_type == 'FRAME_ARRIVAL':
                self._handle_frame_arrival(event.data)
            elif event.event_type == 'ACK_ARRIVAL':
                self._handle_ack_arrival(event.data)
            elif event.event_type == 'TIMEOUT':
                self._handle_timeout(event.data)

        # Record end time
        self.metrics.set_end_time(self.current_time)

        # Check if simulation completed successfully
        if not self._is_complete():
            print(f"Warning: Simulation did not complete. Received {len(self.received_frames)}/{self.total_frames} frames")

        # Get results
        results = {
            'window_size': self.window_size,
            'frame_size': self.frame_size,
            'file_size': self.file_size,
            'total_frames': self.total_frames,
            'completed': self._is_complete(),
            **self.metrics.get_summary(),
            'channel_stats': self.channel.get_statistics()
        }

        return results


def run_simulation(window_size, frame_size, file_size=None, seed=None,
                   num_runs=1):
    """
    Run ARQ simulation with specified parameters.

    Args:
        window_size: Send window size
        frame_size: Frame payload size in bytes
        file_size: File size to transmit (default: from config)
        seed: Random seed
        num_runs: Number of runs to average over

    Returns:
        dict: Averaged simulation results
    """
    if file_size is None:
        file_size = config.TEST_FILE_SIZE

    all_results = []

    for run in range(num_runs):
        run_seed = seed + run if seed is not None else None

        simulator = ARQSimulator(window_size, frame_size, file_size,
                                 seed=run_seed)
        results = simulator.run()
        all_results.append(results)

    # Average results
    if num_runs == 1:
        return all_results[0]

    # Average numeric fields
    avg_results = {
        'window_size': window_size,
        'frame_size': frame_size,
        'file_size': file_size,
        'num_runs': num_runs
    }

    numeric_fields = [
        'simulation_time_sec', 'frames_sent', 'frames_received',
        'frames_retransmitted', 'retransmission_rate', 'bytes_sent',
        'bytes_delivered', 'throughput_bps', 'goodput_bps',
        'goodput_kbps', 'goodput_mbps', 'efficiency'
    ]

    for field in numeric_fields:
        values = [r.get(field, 0) for r in all_results if field in r]
        avg_results[field] = sum(values) / len(values) if values else 0

    # Average channel stats
    channel_ber = [r['channel_stats']['average_ber'] for r in all_results]
    avg_results['average_channel_ber'] = sum(channel_ber) / len(channel_ber)

    return avg_results
