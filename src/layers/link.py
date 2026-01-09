"""Selective Repeat ARQ link layer implementation."""
from dataclasses import dataclass, field
from enum import Enum, auto


class FrameType(Enum):
    DATA = auto()
    ACK = auto()
    NAK = auto()


@dataclass
class Frame:
    """Link layer frame with sequence number and payload."""

    frame_type: FrameType
    seq_num: int
    payload: bytes = b''
    corrupted: bool = False

    def size_bits(self, header_size: int) -> int:
        return (header_size + len(self.payload)) * 8


@dataclass
class TimerEntry:
    """Per-frame retransmission timer."""

    seq_num: int
    expiry_time: float
    frame: Frame


@dataclass
class SenderState:
    """Selective Repeat sender window state."""

    base: int = 0
    next_seq: int = 0
    window_size: int = 8
    timers: dict[int, TimerEntry] = field(default_factory=dict)
    buffer: dict[int, Frame] = field(default_factory=dict)

    def in_window(self, seq: int, max_seq: int) -> bool:
        """Check if sequence number is within the send window."""
        end = (self.base + self.window_size) % max_seq
        if self.base < end:
            return self.base <= seq < end
        return seq >= self.base or seq < end

    def can_send(self) -> bool:
        outstanding = len(self.buffer)
        return outstanding < self.window_size


@dataclass
class ReceiverState:
    """Selective Repeat receiver window state."""

    base: int = 0
    window_size: int = 8
    buffer: dict[int, Frame] = field(default_factory=dict)

    def in_window(self, seq: int, max_seq: int) -> bool:
        """Check if sequence number is within the receive window."""
        end = (self.base + self.window_size) % max_seq
        if self.base < end:
            return self.base <= seq < end
        return seq >= self.base or seq < end


class SelectiveRepeatSender:
    """Selective Repeat ARQ sender."""

    def __init__(self, window_size: int, timeout: float, max_seq: int):
        self.timeout = timeout
        self.max_seq = max_seq
        self.state = SenderState(window_size=window_size)
        self.retransmission_count = 0

    def reset(self):
        self.state = SenderState(window_size=self.state.window_size)
        self.retransmission_count = 0

    def has_pending(self) -> bool:
        return bool(self.state.timers)

    def send_frame(self, payload: bytes, current_time: float) -> Frame | None:
        if not self.state.can_send():
            return None

        seq = self.state.next_seq
        frame = Frame(FrameType.DATA, seq, payload)
        self.state.buffer[seq] = frame
        self.state.timers[seq] = TimerEntry(seq, current_time + self.timeout,
                                            frame)
        self.state.next_seq = (seq + 1) % self.max_seq
        return frame

    def receive_ack(self, ack_seq: int):
        if ack_seq in self.state.timers:
            del self.state.timers[ack_seq]
            del self.state.buffer[ack_seq]

        while self.state.base not in self.state.buffer:
            if self.state.base == self.state.next_seq:
                break
            self.state.base = (self.state.base + 1) % self.max_seq

    def check_timeouts(self, current_time: float) -> list[Frame]:
        expired = []
        for entry in self.state.timers.values():
            if current_time >= entry.expiry_time:
                expired.append(entry.frame)
                entry.expiry_time = current_time + self.timeout
                self.retransmission_count += 1
        return expired


class SelectiveRepeatReceiver:
    """Selective Repeat ARQ receiver."""

    def __init__(self, window_size: int, max_seq: int):
        self.max_seq = max_seq
        self.state = ReceiverState(window_size=window_size)

    def reset(self):
        self.state = ReceiverState(window_size=self.state.window_size)

    def receive_frame(self, frame: Frame) -> tuple[Frame | None, list[bytes]]:
        """Process incoming frame, return ACK and any deliverable payloads."""
        if frame.corrupted:
            return Frame(FrameType.NAK, frame.seq_num), []

        if not self.state.in_window(frame.seq_num, self.max_seq):
            return Frame(FrameType.ACK, frame.seq_num), []

        self.state.buffer[frame.seq_num] = frame
        ack = Frame(FrameType.ACK, frame.seq_num)

        delivered: list[bytes] = []
        while self.state.base in self.state.buffer:
            delivered.append(self.state.buffer[self.state.base].payload)
            del self.state.buffer[self.state.base]
            self.state.base = (self.state.base + 1) % self.max_seq

        return ack, delivered
