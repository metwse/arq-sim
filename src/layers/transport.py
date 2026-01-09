"""Transport layer - segmentation and reassembly."""
from .link import SimplexLink

from dataclasses import dataclass


@dataclass
class TransportSenderState:
    """Selective Repeat sender window state."""

    data: bytes
    offset: int = 0


@dataclass
class TransportReceiverState:
    """Selective Repeat receiver window state."""

    received_data: int = 0


class SimplexTransport:
    """Transport layer sender - segments data for transmission."""

    def __init__(self, link: SimplexLink, data: bytes):
        """Initialize sender with data to transmit."""
        self.link = link

        self.sender = TransportSenderState(data=data)
        self.receiver = TransportReceiverState()

    def has_data(self) -> bool:
        """Check if there is more data to send."""

        return self.sender.offset < len(self.sender.data)

    def is_backpressure_active(self) -> bool:
        """Check if receiver buffer is full (backpressure)."""

        raise NotImplementedError("Implement backpressure check")
