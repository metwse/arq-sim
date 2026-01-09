"""Transport layer - segmentation and reassembly."""
from dataclasses import dataclass


@dataclass
class Segment:
    """Transport layer segment."""
    payload: bytes
    is_last: bool = False


class TransportSender:
    """Transport layer sender - segments data for transmission."""

    def __init__(self, data: bytes, segment_size: int, header_size: int):
        """Initialize sender with data to transmit.

        Args:
            data: Data to be transmitted
            segment_size: Maximum payload size per segment
            header_size: Size of transport header
        """
        self.data = data
        self.segment_size = segment_size
        self.header_size = header_size
        self.offset = 0

    def has_data(self) -> bool:
        """Check if there is more data to send."""
        return self.offset < len(self.data)

    def next_segment(self) -> Segment | None:
        """Get next segment to transmit.

        Returns:
            Next segment, or None if no more data
        """
        raise NotImplementedError("Implement segmentation")


class TransportReceiver:
    """Transport layer receiver - reassembles data."""

    def __init__(self, buffer_capacity: int):
        """Initialize receiver.

        Args:
            buffer_capacity: Maximum buffer size for backpressure
        """
        self.buffer_capacity = buffer_capacity
        self.delivered_data = bytearray()
        self.buffer_full_events = 0

    def is_backpressure_active(self) -> bool:
        """Check if receiver buffer is full (backpressure)."""
        raise NotImplementedError("Implement backpressure check")
