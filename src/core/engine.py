"""Core simulation engine for ARQ protocol - optimized version."""
from .types import SimulationConfig, SimulationResult, ProgressCallback
from .constants import CHANNEL_CONFIG

from src.layers.physical import Channel
from src.layers.link import SelectiveRepeatSender, SelectiveRepeatReceiver, \
    Frame, FrameType
from src.layers.transport import TransportSender, TransportReceiver

import heapq
import random
import time as time_module
from dataclasses import dataclass


@dataclass
class SimulationStats:
    """Runtime statistics for a simulation."""

    start_time: float = 0.0
    end_time: float = 0.0
    bytes_delivered: int = 0
    retransmissions: int = 0
    rtt_samples: list[float] | None = None
    buffer_events: int = 0

    def __post_init__(self):
        if self.rtt_samples is None:
            self.rtt_samples = []


class Simulation:
    """Discrete event simulation of Selective Repeat ARQ over burst channel."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.rng = random.Random(config['seed'])

        self.channel = Channel(
            CHANNEL_CONFIG['good_ber'],
            CHANNEL_CONFIG['bad_ber'],
            CHANNEL_CONFIG['p_good_to_bad'],
            CHANNEL_CONFIG['p_bad_to_good'],
            self.rng
        )

        max_seq = 2 ** 31
        timeout = self._calculate_timeout()

        self.sender = SelectiveRepeatSender(
            config['window_size'], timeout, max_seq
        )
        self.receiver = SelectiveRepeatReceiver(
            config['window_size'], max_seq
        )

        self.transport_tx: TransportSender | None = None
        self.transport_rx = TransportReceiver(config['receiver_buffer_size'])

        self.current_time = 0.0
        self.stats = SimulationStats()
        self._events: list[tuple[float, int, str, Frame]] = []
        self._event_counter = 0

    def _calculate_timeout(self) -> float:
        rtt = (CHANNEL_CONFIG['forward_delay'] +
               CHANNEL_CONFIG['reverse_delay'] +
               2 * CHANNEL_CONFIG['processing_delay'])
        return rtt * 2.5

    def _frame_transmission_time(self, frame: Frame) -> float:
        bits = frame.size_bits(self.config['link_header_size'])
        return bits / CHANNEL_CONFIG['bit_rate']

    def _schedule_event(self, delay: float, event_type: str, data: Frame):
        event_time = self.current_time + delay
        self._event_counter += 1
        heapq.heappush(self._events,
                       (event_time, self._event_counter, event_type, data))

    def load_data(self, data: bytes):
        segment_size = (self.config['frame_payload_size'] -
                        self.config['transport_header_size'])
        self.transport_tx = TransportSender(
            data, segment_size, self.config['transport_header_size']
        )

    def run(self, progress_callback: ProgressCallback | None = None
            ) -> SimulationResult:
        if self.transport_tx is None:
            raise ValueError("No data loaded")

        self.stats.start_time = time_module.time()
        total_bytes = len(self.transport_tx.data)
        last_progress_time = 0.0
        progress_interval = 1

        while (self.transport_tx.has_data() or
               self.sender.has_pending() or
               self._events):

            self._try_send_frames()

            if self._events:
                next_event_time = self._events[0][0]

                expired = self.sender.check_timeouts(next_event_time)
                for frame in expired:
                    self._transmit_data_frame(frame)

                self._process_next_event()
            else:
                expired = self.sender.check_timeouts(self.current_time)
                for frame in expired:
                    self._transmit_data_frame(frame)
                if not self._events:
                    self.current_time += 0.001

            if progress_callback:
                if self.current_time - last_progress_time >= progress_interval:
                    progress = \
                        len(self.transport_rx.delivered_data) / total_bytes

                    progress_callback(progress,
                                      f"Time: {self.current_time:.1f}s")

                    last_progress_time = self.current_time

        self.stats.end_time = time_module.time()
        self.stats.bytes_delivered = len(self.transport_rx.delivered_data)
        self.stats.retransmissions = self.sender.retransmission_count
        self.stats.buffer_events = self.transport_rx.buffer_full_events

        return self._build_result()

    def _try_send_frames(self):
        while (self.transport_tx and self.transport_tx.has_data() and
               self.sender.state.can_send() and
               not self.transport_rx.is_backpressure_active()):

            segment = self.transport_tx.next_segment()
            if segment is None:
                break

            frame = self.sender.send_frame(segment.payload, self.current_time)
            if frame:
                self._transmit_data_frame(frame)

    def _transmit_data_frame(self, frame: Frame):
        tx_time = self._frame_transmission_time(frame)
        delay = (tx_time +
                 CHANNEL_CONFIG['forward_delay'] +
                 CHANNEL_CONFIG['processing_delay'])

        frame_bits = frame.size_bits(self.config['link_header_size'])
        frame.corrupted = self.channel.transmit_frame(frame_bits)

        self._schedule_event(delay, 'frame_arrive', frame)

    def _process_next_event(self):
        event_time, _, event_type, data = heapq.heappop(self._events)
        self.current_time = event_time

        if event_type == 'frame_arrive':
            self._handle_frame_arrival(data)
        elif event_type == 'ack_arrive':
            self._handle_ack_arrival(data)

    def _handle_frame_arrival(self, frame: Frame):
        ack, payloads = self.receiver.receive_frame(frame)

        for payload in payloads:
            self.transport_rx.delivered_data.extend(payload)

        if ack:
            delay = (CHANNEL_CONFIG['reverse_delay'] +
                     CHANNEL_CONFIG['processing_delay'])
            self._schedule_event(delay, 'ack_arrive', ack)

    def _handle_ack_arrival(self, ack: Frame):
        if ack.frame_type == FrameType.ACK:
            self.sender.receive_ack(ack.seq_num)
        elif ack.frame_type == FrameType.NAK:
            if ack.seq_num in self.sender.state.timers:
                frame = self.sender.state.buffer.get(ack.seq_num)
                if frame:
                    self._transmit_data_frame(frame)
                    self.sender.retransmission_count += 1
                    self.sender.state.timers[ack.seq_num].expiry_time = (
                        self.current_time + self.sender.timeout
                    )

    def _build_result(self) -> SimulationResult:
        total_time = self.current_time if self.current_time > 0 else 1.0
        goodput = self.stats.bytes_delivered / total_time

        avg_rtt = 0.0
        if self.stats.rtt_samples:
            avg_rtt = sum(self.stats.rtt_samples) / len(self.stats.rtt_samples)

        utilization = 0.0
        max_goodput = CHANNEL_CONFIG['bit_rate'] / 8
        if max_goodput > 0:
            utilization = goodput / max_goodput

        return SimulationResult(
            window_size=self.config['window_size'],
            frame_payload_size=self.config['frame_payload_size'],
            goodput=goodput,
            utilization=utilization,
            avg_rtt=avg_rtt,
            retransmissions=self.stats.retransmissions,
            total_time=total_time,
            bytes_sent=self.transport_tx.offset if self.transport_tx else 0
        )
