"""Link layer - Selective Repeat ARQ protocol."""
from dataclasses import dataclass, field
from enum import Enum


class FrameType(Enum):
    """Frame types for ARQ protocol."""
    DATA = 1
    ACK = 2
    NAK = 3


@dataclass
class Frame:
    """Network frame structure."""
    frame_type: FrameType
    seq_num: int
    payload: bytes = b''
    corrupted: bool = False

    def size_bits(self, header_size: int) -> int:
        """Calculate total frame size in bits."""
        return (header_size + len(self.payload)) * 8


@dataclass
class SenderState:
    """Selective Repeat sender window state."""

    base: int = 0
    next_seq: int = 0
    window_size: int = 8
    buffer: dict[int, Frame] = field(default_factory=dict)
    timers: dict = field(default_factory=dict)

    def can_send(self) -> bool:
        """Check if sender can send a new frame within window."""
        raise NotImplementedError("Implement window limit check")


@dataclass
class ReceiverState:
    """Selective Repeat receiver window state."""

    base: int = 0
    window_size: int = 8
    buffer: dict[int, Frame] = field(default_factory=dict)

    def in_window(self, seq: int, max_seq: int) -> bool:
        """Check if sequence number is within the receive window."""
        raise NotImplementedError("Implement sequence window check")


class SelectiveRepeatSender:
    """Selective Repeat ARQ sender."""

    def __init__(self, window_size: int, timeout: float, max_seq: int):
        self.window_size = window_size
        self.timeout = timeout
        self.max_seq = max_seq
        self.retransmission_count = 0
        self.state = SenderState(window_size=window_size)

    def send_frame(self, payload: bytes, current_time: float) -> Frame | None:
        """Create and buffer a new frame for transmission.

        Returns:
            Frame to transmit, or None if window is full
        """
        _ = payload, current_time

        raise NotImplementedError("Implement frame creation and buffering")

    def receive_ack(self, ack_seq: int):
        """Process received ACK and slide window if possible."""
        _ = ack_seq

        raise NotImplementedError(
            "Implement ACK processing and window sliding")

    def check_timeouts(self, current_time: float) -> list[Frame]:
        """Check for timeouts and return list of frames to retransmit."""
        _ = current_time

        raise NotImplementedError("Implement timeout detection")

    def has_pending(self) -> bool:
        """Check if there are unacknowledged frames."""
        return len(self.state.buffer) > 0


class SelectiveRepeatReceiver:
    """Selective Repeat ARQ receiver."""

    def __init__(self, window_size: int, max_seq: int):
        self.window_size = window_size
        self.max_seq = max_seq
        self.state = ReceiverState(window_size=window_size)

    def receive_frame(self, frame: Frame) -> tuple[Frame | None, list[bytes]]:
        """Process incoming frame.

        Returns:
            (ACK/NAK frame, list of in-order payloads to deliver)
        """
        _ = frame

        raise NotImplementedError("Implement frame reception and ordering")
