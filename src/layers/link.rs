use std::{collections::HashMap, sync::Arc};

use crate::{common::*, event_loop::EventLoop};
use tokio::sync::Mutex;
use tracing::{debug, instrument, trace};

use super::physical::{Frame, SimplexChannel};

const RECEIVER_BUFFER_SIZE: usize = 256 * 1024; // 256 KB

/// Link layer sender state
pub struct Sender {
    /// Send window base (oldest unacknowledged frame)
    base: i64,
    /// Next sequence number to send
    next_seq: i64,
    /// Window size
    window_size: i64,
    /// Buffer of sent but unacknowledged frames
    sent_frames: HashMap<i64, Vec<u8>>,
    /// Active timer event IDs for each sequence number
    timers: HashMap<i64, i64>,
    /// Timeout duration
    timeout: f64,
}

impl Sender {
    /// Creates a new sender
    pub fn new(window_size: i64, timeout: f64) -> Self {
        Self {
            base: 0,
            next_seq: 0,
            window_size,
            sent_frames: HashMap::new(),
            timers: HashMap::new(),
            timeout,
        }
    }

    /// Check if we can send more frames (window not full)
    pub fn can_send(&self) -> bool {
        self.next_seq < self.base + self.window_size
    }

    /// Get next sequence number
    pub fn next_seq(&self) -> i64 {
        self.next_seq
    }

    /// Store sent frame and return sequence number
    pub fn send_frame(&mut self, data: Vec<u8>) -> i64 {
        let seq = self.next_seq;
        self.sent_frames.insert(seq, data);
        self.next_seq += 1;
        seq
    }

    /// Handle ACK - remove frame and slide window
    pub fn handle_ack(&mut self, seq: i64) {
        trace!(seq, base = self.base, "Handling ACK");
        // Remove from sent frames
        if self.sent_frames.remove(&seq).is_some() {
            // Slide window if this was the base
            while !self.sent_frames.contains_key(&self.base) && self.base < self.next_seq {
                self.base += 1;
            }
        }
    }

    /// Handle NAK - return frame data for retransmission
    pub fn handle_nak(&self, seq: i64) -> Option<Vec<u8>> {
        self.sent_frames.get(&seq).cloned()
    }

    /// Get frame for timeout retransmission
    pub fn get_frame_for_timeout(&self, seq: i64) -> Option<Vec<u8>> {
        self.sent_frames.get(&seq).cloned()
    }
}

/// Link layer receiver state
pub struct Receiver {
    /// Receive window base (next expected sequence number)
    base: i64,
    /// Buffered out-of-order frames
    buffer: HashMap<i64, Vec<u8>>,
    /// Current buffer size in bytes
    buffer_size: usize,
    /// Maximum buffer size (256 KB)
    max_buffer_size: usize,
}

impl Default for Receiver {
    fn default() -> Self {
        Self {
            base: 0,
            buffer: HashMap::new(),
            buffer_size: 0,
            max_buffer_size: RECEIVER_BUFFER_SIZE,
        }
    }
}

impl Receiver {
    /// Creates a new Receiver
    pub fn new() -> Self {
        Self::default()
    }

    /// Receive a frame and return:
    /// - Response frame (Rr for ACK, Srej for NAK, None for corrupted)
    /// - List of delivered payloads (in order)
    pub fn receive_frame(&mut self, seq: i64, frame: Frame) -> (Option<Frame>, Vec<Vec<u8>>) {
        match frame {
            Frame::Corrupted => {
                // Ignore corrupted frames (timeout will handle)
                (None, vec![])
            }
            Frame::Data(data) => {
                if seq == self.base {
                    // In-order frame - deliver immediately
                    let mut delivered = vec![data];

                    // Advance base and deliver any buffered frames
                    self.base += 1;
                    while let Some(buffered_data) = self.buffer.remove(&self.base) {
                        self.buffer_size -= buffered_data.len();
                        delivered.push(buffered_data);
                        self.base += 1;
                    }

                    // Send ACK
                    (Some(Frame::Rr(seq)), delivered)
                } else if seq > self.base {
                    // Out-of-order frame - buffer it if space available
                    let data_size = data.len();

                    if self.buffer_size + data_size <= self.max_buffer_size {
                        self.buffer.insert(seq, data);
                        self.buffer_size += data_size;
                    }
                    // else: drop frame (buffer full)

                    // Send NAK for missing frame
                    (Some(Frame::Srej(self.base)), vec![])
                } else {
                    // Duplicate or old frame - just ACK it
                    (Some(Frame::Rr(seq)), vec![])
                }
            }
            _ => {
                // Rr/Srej frames shouldn't come here
                (None, vec![])
            }
        }
    }
}

/// Simplex link layer (sender -> receiver)
pub struct SimplexLink {
    sender: Arc<Mutex<Sender>>,
    receiver: Arc<Mutex<Receiver>>,
    /// Forward channel (sender -> receiver) for data frames
    forward_channel: Arc<SimplexChannel>,
    /// Reverse channel (receiver -> sender) for ACK/NAK
    reverse_channel: Arc<SimplexChannel>,
    event_loop: Arc<EventLoop>,
}

impl SimplexLink {
    /// Creates a new SimplexLink with asymmetric channels
    pub fn new(
        forward_channel: Arc<SimplexChannel>,
        reverse_channel: Arc<SimplexChannel>,
        event_loop: Arc<EventLoop>,
        window_size: i64,
        timeout: f64,
    ) -> Self {
        Self {
            sender: Arc::new(Mutex::new(Sender::new(window_size, timeout))),
            receiver: Arc::new(Mutex::new(Receiver::new())),
            forward_channel,
            reverse_channel,
            event_loop,
        }
    }

    /// Send data frame
    #[instrument(skip(self, data))]
    pub async fn send_data(&self, current_time: f64, data: Vec<u8>) -> Option<i64> {
        let mut sender = self.sender.lock().await;

        if !sender.can_send() {
            return None; // Window full
        }

        let seq = sender.send_frame(data.clone());
        debug!(seq, data_len = data.len(), "Sending frame");

        // Send through forward channel
        let frame = Frame::Data(data);
        self.forward_channel.send(current_time, frame.clone()).await;

        // Calculate propagation time for timer scheduling
        let propagation_time =
            frame.size_bits() as f64 / BIT_RATE as f64 + FORWARD_PATH + PROCESSING_DELAY;

        // Schedule timeout event
        let timeout_time = current_time + propagation_time + sender.timeout;
        let event_loop = self.event_loop.clone();
        let sender_clone = self.sender.clone();
        let channel_clone = self.forward_channel.clone(); // Corrected to forward_channel

        let timer_id = event_loop
            .schedule(
                timeout_time,
                Box::pin(async move {
                    // Timeout handler
                    let sender = sender_clone.lock().await; // Mutex lock for sender
                    if let Some(data) = sender.get_frame_for_timeout(seq) {
                        // Retransmit on forward channel
                        channel_clone.send(timeout_time, Frame::Data(data)).await;
                    }
                }),
            )
            .await;

        sender.timers.insert(seq, timer_id);

        Some(seq)
    }

    /// Receive and process frame at receiver
    #[instrument(skip(self, frame))]
    pub async fn receive_frame(&self, seq: i64, frame: Frame) -> (Option<Frame>, Vec<Vec<u8>>) {
        let mut receiver = self.receiver.lock().await;
        receiver.receive_frame(seq, frame)
    }

    /// Handle ACK reception at sender
    pub async fn handle_ack(&self, seq: i64) {
        let mut sender = self.sender.lock().await;

        // Cancel timer
        if let Some(timer_id) = sender.timers.get(&seq) {
            self.event_loop.cancel(*timer_id).await;
        }

        sender.handle_ack(seq);
    }

    /// Handle NAK reception at sender
    pub async fn handle_nak(&self, current_time: f64, seq: i64) {
        let sender = self.sender.lock().await;

        if let Some(data) = sender.handle_nak(seq) {
            // Retransmit immediately on forward channel
            self.forward_channel
                .send(current_time, Frame::Data(data))
                .await;
        }
    }

    /// Check if sender can send more
    pub async fn can_send(&self) -> bool {
        self.sender.lock().await.can_send()
    }

    /// Send ACK on reverse channel
    pub async fn send_ack(&self, current_time: f64, seq: i64) {
        self.reverse_channel
            .send(current_time, Frame::Rr(seq))
            .await;
    }

    /// Send NAK on reverse channel
    pub async fn send_nak(&self, current_time: f64, seq: i64) {
        self.reverse_channel
            .send(current_time, Frame::Srej(seq))
            .await;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    #[test_log::test]
    async fn test_comprehensive_link_layer() {
        let event_loop = Arc::new(EventLoop::default());
        let forward_channel = Arc::new(SimplexChannel::new(event_loop.clone(), FORWARD_PATH));
        let reverse_channel = Arc::new(SimplexChannel::new(event_loop.clone(), REVERSE_PATH));
        let link = SimplexLink::new(forward_channel, reverse_channel, event_loop.clone(), 8, 0.1);

        // ========== SECTION 1: In-order delivery ==========
        tracing::info!("Section 1: Testing in-order delivery");

        let data1 = vec![1, 2, 3];
        let data2 = vec![4, 5, 6];
        let data3 = vec![7, 8, 9];

        link.send_data(0.0, data1.clone()).await;
        link.send_data(0.001, data2.clone()).await;
        link.send_data(0.002, data3.clone()).await;

        event_loop.advance().await;
        event_loop.advance().await;
        event_loop.advance().await;

        let (ack1, delivered1) = link.receive_frame(0, Frame::Data(data1.clone())).await;
        assert!(matches!(ack1, Some(Frame::Rr(0))), "Should ACK frame 0");
        assert_eq!(delivered1.len(), 1, "Should deliver 1 frame");
        assert_eq!(delivered1[0], data1);

        let (ack2, delivered2) = link.receive_frame(1, Frame::Data(data2.clone())).await;
        assert!(matches!(ack2, Some(Frame::Rr(1))), "Should ACK frame 1");
        assert_eq!(delivered2.len(), 1);
        assert_eq!(delivered2[0], data2);

        let (ack3, delivered3) = link.receive_frame(2, Frame::Data(data3.clone())).await;
        assert!(matches!(ack3, Some(Frame::Rr(2))), "Should ACK frame 2");
        assert_eq!(delivered3.len(), 1);
        assert_eq!(delivered3[0], data3);

        // ========== SECTION 2: Out-of-order with NAK ==========
        tracing::info!("Section 2: Testing out-of-order frames and NAK");

        let data10 = vec![10; 100];
        let data11 = vec![11; 100];
        let data12 = vec![12; 100];

        // Receive frame 3 (in order after previous section)
        let (ack10, delivered10) = link.receive_frame(3, Frame::Data(data10.clone())).await;
        assert!(matches!(ack10, Some(Frame::Rr(3))));
        assert_eq!(delivered10.len(), 1);

        // Skip frame 4, receive frame 5 (out of order)
        let (nak, delivered_nak) = link.receive_frame(5, Frame::Data(data12.clone())).await;
        assert!(matches!(nak, Some(Frame::Srej(4))), "Should NAK for missing frame 4");
        assert_eq!(delivered_nak.len(), 0, "Should buffer frame 5, not deliver");

        // Now receive missing frame 4
        let (ack11, delivered11) = link.receive_frame(4, Frame::Data(data11.clone())).await;
        assert!(matches!(ack11, Some(Frame::Rr(4))));
        assert_eq!(delivered11.len(), 2, "Should deliver frame 4 and buffered frame 5");
        assert_eq!(delivered11[0], data11);
        assert_eq!(delivered11[1], data12);

        // ========== SECTION 3: Corrupted frames ==========
        tracing::info!("Section 3: Testing corrupted frame handling");

        // Receive corrupted frame
        let (response, delivered) = link.receive_frame(6, Frame::Corrupted).await;
        assert!(response.is_none(), "Should not respond to corrupted frames");
        assert_eq!(delivered.len(), 0, "Should not deliver corrupted frames");

        // Receive valid frame after corrupted one
        let data13 = vec![13; 50];
        let (ack13, delivered13) = link.receive_frame(6, Frame::Data(data13.clone())).await;
        assert!(matches!(ack13, Some(Frame::Rr(6))));
        assert_eq!(delivered13.len(), 1);
        assert_eq!(delivered13[0], data13);

        // ========== SECTION 4: Window size limits ==========
        tracing::info!("Section 4: Testing window size flow control");

        // Create new link with small window for this test
        let small_link = SimplexLink::new(
            Arc::new(SimplexChannel::new(event_loop.clone(), FORWARD_PATH)),
            Arc::new(SimplexChannel::new(event_loop.clone(), REVERSE_PATH)),
            event_loop.clone(),
            2, // Small window
            0.1
        );

        // Fill window
        let seq0 = small_link.send_data(1.0, vec![20; 10]).await;
        let seq1 = small_link.send_data(1.001, vec![21; 10]).await;
        assert_eq!(seq0, Some(0));
        assert_eq!(seq1, Some(1));

        // Try to send when window is full
        let seq2 = small_link.send_data(1.002, vec![22; 10]).await;
        assert_eq!(seq2, None, "Should reject when window is full");

        // ACK first frame to make room
        small_link.handle_ack(0).await;

        // Now should be able to send
        let seq2_retry = small_link.send_data(1.003, vec![22; 10]).await;
        assert_eq!(seq2_retry, Some(2), "Should allow send after ACK");

        tracing::info!("✓ Window flow control works correctly");

        // ========== SECTION 5: Buffer overflow ==========
        tracing::info!("Section 5: Testing 256KB buffer overflow protection");

        // Create new link for this test
        let overflow_link = SimplexLink::new(
            Arc::new(SimplexChannel::new(event_loop.clone(), FORWARD_PATH)),
            Arc::new(SimplexChannel::new(event_loop.clone(), REVERSE_PATH)),
            event_loop.clone(),
            1000,
            0.1
        );

        let large_data = vec![0u8; 100 * 1024]; // 100KB per frame

        // Buffer frames out of order to test overflow
        let (nak1, _) = overflow_link.receive_frame(1, Frame::Data(large_data.clone())).await;
        assert!(matches!(nak1, Some(Frame::Srej(0))), "NAK for frame 0");

        let (nak2, _) = overflow_link.receive_frame(2, Frame::Data(large_data.clone())).await;
        assert!(matches!(nak2, Some(Frame::Srej(0))), "NAK for frame 0");

        // Third frame should be dropped (100 + 100 + 100 > 256KB)
        let (nak3, delivered3) = overflow_link.receive_frame(3, Frame::Data(large_data.clone())).await;
        assert!(matches!(nak3, Some(Frame::Srej(0))), "Still NAK even when dropping");
        assert_eq!(delivered3.len(), 0);

        // Send missing frame 0
        let (ack0, delivered0) = overflow_link.receive_frame(0, Frame::Data(vec![0; 10])).await;
        assert!(matches!(ack0, Some(Frame::Rr(0))));
        // Should deliver 0, 1, 2 but NOT 3 (was dropped)
        assert_eq!(delivered0.len(), 3, "Should deliver buffered frames, but not the dropped one");

        // ========== SECTION 6: Duplicate frames ==========
        tracing::info!("Section 6: Testing duplicate frame handling");

        let dup_data = vec![30; 50];

        // Send and receive frame 7
        let (ack_first, delivered_first) = link.receive_frame(7, Frame::Data(dup_data.clone())).await;
        assert!(matches!(ack_first, Some(Frame::Rr(7))));
        assert_eq!(delivered_first.len(), 1);

        // Receive duplicate of frame 7
        let (ack_dup, delivered_dup) = link.receive_frame(7, Frame::Data(dup_data.clone())).await;
        assert!(matches!(ack_dup, Some(Frame::Rr(7))), "Should ACK duplicate");
        assert_eq!(delivered_dup.len(), 0, "Should not deliver duplicate");
    }
}
