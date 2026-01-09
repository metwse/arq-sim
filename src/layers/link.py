"""Link layer - Selective Repeat ARQ protocol."""
from .physical import Channel

from src.core.channel_config import BIT_RATE, FORWARD_DELAY, REVERSE_DELAY
from src.core.constants import LINK_HEADER_SIZE

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

    def size_bits(self):
        return (len(self.payload) + LINK_HEADER_SIZE) * 8

    def propagation_time(self):
        match self.frame_type:
            case FrameType.DATA:
                return FORWARD_DELAY + self.size_bits() / BIT_RATE
            case _:
                return REVERSE_DELAY


@dataclass
class LinkSenderState:
    """Selective Repeat sender window state."""

    base: int = 0
    next_seq: int = 0
    window_size: int = 8
    buffer: dict[int, Frame] = field(default_factory=dict)
    timers: dict = field(default_factory=dict)


@dataclass
class LinkReceiverState:
    """Selective Repeat receiver window state."""

    base: int = 0
    window_size: int = 8
    buffer: dict[int, Frame] = field(default_factory=dict)


class SimplexLink:
    """Selective Repeat ARQ link layer with non-circular sequence numbers."""

    def __init__(self, channel: Channel, window_size: int, timeout: float):
        self.window_size = window_size
        self.timeout = timeout
        self.retransmission_count = 0

        self.channel = channel

        self.sender = LinkSenderState(window_size=window_size)
        self.receiver = LinkReceiverState(window_size=window_size)

    def can_send(self) -> bool:
        """Check if sender can send a new frame (window not full)."""
        outstanding = self.sender.next_seq - self.sender.base
        return outstanding < self.window_size

    def send_data_frame(self, payload: bytes, current_time: float
                        ) -> Frame | None:
        """Create and buffer a new DATA frame for transmission.

        Args:
            payload: Data to send in this frame
            current_time: Current simulation time

        Returns:
            Frame to transmit, or None if window is full
        """
        if not self.can_send():
            return None

        frame = Frame(
            frame_type=FrameType.DATA,
            seq_num=self.sender.next_seq,
            payload=payload
        )

        # Transmit through channel (may corrupt)
        frame.corrupted = self.channel.transmit_frame(frame.size_bits())

        # Buffer for potential retransmission, set timeout timer
        self.sender.buffer[self.sender.next_seq] = frame
        self.sender.timers[self.sender.next_seq] = current_time + self.timeout

        self.sender.next_seq += 1
        return frame

    def receive_ack(self, ack_seq: int) -> None:
        """Process received ACK and slide sender window.

        Args:
            ack_seq: Sequence number being acknowledged
        """
        # Remove acknowledged frame from buffer
        if ack_seq in self.sender.buffer:
            del self.sender.buffer[ack_seq]
            del self.sender.timers[ack_seq]

        # Slide window base forward if possible
        while (self.sender.base not in self.sender.buffer and
               self.sender.base < self.sender.next_seq):
            self.sender.base += 1

    def receive_nak(self, nak_seq: int) -> Frame | None:
        """Process received NAK and return frame for immediate retransmission.

        Args:
            nak_seq: Sequence number being NAKed

        Returns:
            Frame to retransmit, or None if not in buffer
        """
        if nak_seq in self.sender.buffer:
            self.retransmission_count += 1
            frame = self.sender.buffer[nak_seq]
            # Re-transmit through channel
            frame.corrupted = self.channel.transmit_frame(frame.size_bits())
            return frame

        return None

    def check_timeouts(self, current_time: float) -> list[Frame]:
        """Check for expired timers and return frames to retransmit.

        Args:
            current_time: Current simulation time

        Returns:
            List of frames that timed out and need retransmission
        """
        expired_frames = []

        for seq_num, expiry_time in list(self.sender.timers.items()):
            if current_time >= expiry_time:
                # Timeout occurred
                if seq_num in self.sender.buffer:
                    self.retransmission_count += 1
                    frame = self.sender.buffer[seq_num]
                    # Re-transmit through channel
                    frame.corrupted = self.channel.transmit_frame(
                        frame.size_bits())
                    expired_frames.append(frame)
                    # Reset timer
                    self.sender.timers[seq_num] = current_time + self.timeout

        return expired_frames

    def receive_data_frame(self, frame: Frame) -> tuple[Frame, list[bytes]]:
        """Process received DATA frame.

        Args:
            frame: Received DATA frame

        Returns:
            Tuple of (ACK/NAK frame to send, list of payloads to deliver)
        """
        # Check if corrupted
        if frame.corrupted:
            nak = Frame(frame_type=FrameType.NAK, seq_num=frame.seq_num)
            return nak, []

        # Check if in receive window
        if not (self.receiver.base <= frame.seq_num <
                self.receiver.base + self.window_size):
            # Outside window - send ACK anyway (duplicate)
            ack = Frame(frame_type=FrameType.ACK, seq_num=frame.seq_num)
            return ack, []

        # Send ACK
        ack = Frame(frame_type=FrameType.ACK, seq_num=frame.seq_num)

        # Already received? (duplicate)
        if frame.seq_num < self.receiver.base:
            return ack, []

        # Buffer the frame
        self.receiver.buffer[frame.seq_num] = frame

        # Deliver in-order payloads
        delivered = []
        while self.receiver.base in self.receiver.buffer:
            delivered.append(self.receiver.buffer[self.receiver.base].payload)
            del self.receiver.buffer[self.receiver.base]
            self.receiver.base += 1

        return ack, delivered

    def has_pending_frames(self) -> bool:
        """Check if sender has unacknowledged frames."""
        return len(self.sender.buffer) > 0
