use std::{collections::HashMap, sync::Arc};

use crate::event_loop::EventLoop;
use async_recursion::async_recursion;
use futures::future::BoxFuture;
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
}

impl Sender {
    /// Creates a new sender
    pub fn new(window_size: i64) -> Self {
        Self {
            base: 0,
            next_seq: 0,
            window_size,
            sent_frames: HashMap::new(),
            timers: HashMap::new(),
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
    ) -> Self {
        Self {
            sender: Arc::new(Mutex::new(Sender::new(window_size))),
            receiver: Arc::new(Mutex::new(Receiver::new())),
            forward_channel,
            reverse_channel,
            event_loop,
        }
    }

    /// Send data frame
    #[instrument(skip(self, data))]
    pub async fn send_data(&self, current_time: f64, data: Vec<u8>) -> Option<f64> {
        let seq;

        {
            let mut sender = self.sender.lock().await;

            if !sender.can_send() {
                return None; // Window full
            }

            seq = sender.send_frame(data.clone());
        }

        debug!(seq, data_len = data.len(), "Sending frame");

        // Send through forward channel
        let frame = Frame::Data(data);
        let (propagation_duration, rtt) =
            self.forward_channel.send(current_time, frame.clone()).await;

        setup_timer(
            SetupTimerEnv {
                sender: Arc::clone(&self.sender),
                forward_channel: Arc::clone(&self.forward_channel),
                event_loop: Arc::clone(&self.event_loop),
                seq,
                rtt,
            },
            current_time,
        )
        .await;

        Some(propagation_duration)
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
        if let Some(timer_id) = sender.timers.remove(&seq) {
            self.event_loop.cancel(timer_id).await;
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

#[derive(Clone)]
struct SetupTimerEnv {
    sender: Arc<Mutex<Sender>>,
    forward_channel: Arc<SimplexChannel>,
    event_loop: Arc<EventLoop>,
    seq: i64,
    rtt: f64,
}

#[async_recursion]
#[instrument(skip(env))]
async fn setup_timer(env: SetupTimerEnv, current_time: f64) {
    let timeout_time = current_time + env.rtt * 2.5;

    let timer_fut: BoxFuture<'static, ()> = Box::pin({
        let env = env.clone();

        async move {
            let mut retransmitted = false;

            {
                let sender = env.sender.lock().await;

                if let Some(data) = sender.get_frame_for_timeout(env.seq) {
                    // Retransmit on forward channel
                    env.forward_channel
                        .send(timeout_time, Frame::Data(data))
                        .await;
                    debug!(seq=env.seq, "Retransmit frame");

                    retransmitted = true;
                }
            }

            if retransmitted {
                setup_timer(env, timeout_time).await;
            }
        }
    });

    let timer_id = env.event_loop.schedule(timeout_time, timer_fut).await;
    debug!(seq=env.seq, "Set retransmission timer");

    let mut sender = env.sender.lock().await;
    sender.timers.remove(&env.seq);
    sender.timers.insert(env.seq, timer_id);
}

#[cfg(test)]
mod tests {
    use std::time::Duration;

    use super::*;
    use crate::common::*;

    #[tokio::test]
    #[test_log::test]
    async fn test_timer() {
        let event_loop = Arc::new(EventLoop::default());
        let forward_channel = Arc::new(SimplexChannel::new(Arc::clone(&event_loop), FORWARD_PATH));
        let reverse_channel = Arc::new(SimplexChannel::new(Arc::clone(&event_loop), REVERSE_PATH));

        let link = SimplexLink::new(forward_channel, reverse_channel, Arc::clone(&event_loop), 4);

        tokio::spawn({
            let event_loop = Arc::clone(&event_loop);

            async move {
                loop {
                    while event_loop.pending_count().await > 0 {
                        event_loop.advance().await;
                    }
                    tokio::time::sleep(Duration::from_millis(1)).await;
                }
            }
        });

        link.send_data(0.0, vec![0; 10000]).await;
        link.send_data(1.0, vec![0; 10001]).await;
        link.send_data(2.0, vec![0; 10002]).await;
        link.send_data(3.0, vec![0; 10003]).await;

        tokio::time::sleep(Duration::from_secs(4)).await;
        link.handle_ack(0).await;
        link.send_data(4.0, vec![0; 10004]).await;
        tokio::time::sleep(Duration::from_secs(1)).await;
        link.handle_ack(1).await;
        tokio::time::sleep(Duration::from_secs(1)).await;
        link.handle_ack(2).await;
        tokio::time::sleep(Duration::from_secs(1)).await;
        link.handle_ack(3).await;
        tokio::time::sleep(Duration::from_secs(1)).await;
        link.handle_ack(4).await;
        tokio::time::sleep(Duration::from_secs(1)).await;
    }
}
