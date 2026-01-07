"""Transport layer segmentation and reassembly."""
from dataclasses import dataclass, field


@dataclass
class Segment:
    """Transport layer segment with sequence number."""

    seq_num: int
    payload: bytes
    is_last: bool = False


class TransportSender:
    """Segments file data for transmission."""

    def __init__(self, data: bytes, segment_size: int, header_size: int = 8):
        self.data = data
        self.segment_size = segment_size
        self.header_size = header_size
        self.offset = 0
        self.seq_num = 0

    def has_data(self) -> bool:
        return self.offset < len(self.data)

    def next_segment(self) -> Segment | None:
        if not self.has_data():
            return None

        end = min(self.offset + self.segment_size, len(self.data))
        payload = self.data[self.offset:end]
        is_last = end >= len(self.data)

        segment = Segment(self.seq_num, payload, is_last)
        self.offset = end
        self.seq_num += 1
        return segment

    def reset(self):
        self.offset = 0
        self.seq_num = 0


class TransportReceiver:
    """Reassembles segments with flow control."""

    def __init__(self, buffer_capacity: int):
        self.buffer_capacity = buffer_capacity
        self.buffer: dict[int, Segment] = field(default_factory=dict)
        self.buffer = {}
        self.next_expected = 0
        self.delivered_data = bytearray()
        self.buffer_used = 0
        self.buffer_full_events = 0

    def buffer_available(self) -> int:
        return self.buffer_capacity - self.buffer_used

    def is_backpressure_active(self) -> bool:
        return self.buffer_used >= self.buffer_capacity

    def receive_segment(self, segment: Segment) -> bool:
        """Buffer incoming segment. Returns False if backpressure active."""
        segment_size = len(segment.payload)

        if self.buffer_used + segment_size > self.buffer_capacity:
            self.buffer_full_events += 1
            return False

        self.buffer[segment.seq_num] = segment
        self.buffer_used += segment_size
        self._try_deliver()
        return True

    def _try_deliver(self):
        while self.next_expected in self.buffer:
            segment = self.buffer.pop(self.next_expected)
            self.delivered_data.extend(segment.payload)
            self.buffer_used -= len(segment.payload)
            self.next_expected += 1

    def is_complete(self) -> bool:
        for seg in self.buffer.values():
            if seg.is_last:
                return False
        return self.next_expected > 0 and not self.buffer

    def get_data(self) -> bytes:
        return bytes(self.delivered_data)

    def reset(self):
        self.buffer.clear()
        self.next_expected = 0
        self.delivered_data = bytearray()
        self.buffer_used = 0
        self.buffer_full_events = 0
