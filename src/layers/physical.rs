use std::sync::Arc;

use crate::{common::*, event_loop::EventLoop};

use rand::random;
use tokio::{
    sync::{
        Mutex,
        mpsc::{self, UnboundedReceiver, UnboundedSender},
    },
    task,
};
use tracing::{debug, instrument};

/// Pyhsical layer frame
#[derive(Clone, Debug)]
pub enum Frame {
    /// Request ready
    Rr(i64),
    /// Negative ACK
    Srej(i64),
    /// Underlying data array
    Data(Vec<u8>),
    /// Unit type represent a corrupted frame. Ignored by the rx.
    Corrupted,
}

impl Frame {
    /// Returns size of a frame in bits.
    pub fn size_bits(&self) -> u64 {
        match self {
            Self::Rr(_) => FRAME_OVERHEAD,
            Self::Srej(_) => FRAME_OVERHEAD,
            Self::Data(data) => data.len() as u64 * 8 + FRAME_OVERHEAD,
            _ => unreachable!("unexcepted send of a corrupted frame"),
        }
    }
}

/// Physical transmission medium
pub struct SimplexChannel {
    tx: UnboundedSender<(f64, Frame)>,
    rx: Mutex<UnboundedReceiver<(f64, Frame)>>,
    event_loop: Arc<EventLoop>,
    propagation_delay: f64,
    is_good: Mutex<bool>,
}

impl SimplexChannel {
    /// Creates a new simplex channel.
    pub fn new(event_loop: Arc<EventLoop>, propagation_delay: f64) -> Self {
        let (tx, rx) = mpsc::unbounded_channel();

        Self {
            tx,
            rx: Mutex::new(rx),
            event_loop,
            propagation_delay,
            is_good: Mutex::new(true),
        }
    }

    /// Sends a frame.
    #[instrument(skip(self, frame))]
    pub async fn send(&self, time: f64, frame: Frame) -> (f64, f64) {
        let mut is_good = self.is_good.lock().await;
        let corrupted;

        (corrupted, *is_good) = task::spawn_blocking({
            let mut next_state = *is_good;
            let size_bits = frame.size_bits();

            move || {
                let mut corrupted = false;

                for _ in 0..size_bits {
                    let r: f64 = random();

                    if next_state {
                        if r < GOOD_STATE_BER {
                            corrupted = true;
                        }
                        if r < P_G_TO_B {
                            next_state = false;
                        }
                    } else {
                        if r < BAD_STATE_BER {
                            corrupted = true;
                        }
                        if r < P_B_TO_G {
                            next_state = true;
                        }
                    }
                }

                (corrupted, next_state)
            }
        })
        .await
        .unwrap();

        let propagation_duration: f64 = frame.size_bits() as f64 / BIT_RATE as f64;

        let rtt = propagation_duration + self.propagation_delay + PROCESSING_DELAY;

        self.event_loop
            .schedule(
                time + rtt,
                Box::pin({
                    let tx = self.tx.clone();

                    async move {
                        tx.send((time + rtt, if corrupted { Frame::Corrupted } else { frame }))
                            .ok();
                    }
                }),
            )
            .await;
        debug!(propagation_duration, rtt, corrupted, "Schedule for send");

        (propagation_duration, rtt)
    }

    /// Receives the next frame
    #[instrument(skip(self))]
    pub async fn receive(&self) -> (f64, Frame) {
        let (time, frame) = self.rx.lock().await.recv().await.unwrap();
        debug!(time, frame=?frame, "Received frame");

        (time, frame)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    #[test_log::test]
    async fn test_frame_size_bits() {
        // Test ACK/NAK frames (just header)
        let rr = Frame::Rr(42);
        assert_eq!(rr.size_bits(), FRAME_OVERHEAD);

        let srej = Frame::Srej(42);
        assert_eq!(srej.size_bits(), FRAME_OVERHEAD);

        // Test data frame (header + payload)
        let data = Frame::Data(vec![0u8; 100]);
        assert_eq!(data.size_bits(), 100 * 8 + FRAME_OVERHEAD);
    }

    #[tokio::test]
    #[test_log::test]
    async fn test_channel_send_receive() {
        let event_loop = Arc::new(EventLoop::default());
        let channel = SimplexChannel::new(event_loop.clone(), FORWARD_PATH);

        // Send a frame
        let data = Frame::Data(vec![1, 2, 3]);
        channel.send(0.0, data.clone()).await;

        // The frame should be scheduled in event loop
        assert_eq!(event_loop.pending_count().await, 1);

        // Process the event
        event_loop.advance().await;

        // Receive the frame
        let (recv_time, recv_frame) = channel.receive().await;

        // Check timing
        let expected_time =
            (3 * 8 + FRAME_OVERHEAD) as f64 / BIT_RATE as f64 + FORWARD_PATH + PROCESSING_DELAY;
        assert!((recv_time - expected_time).abs() < 1e-6);

        // Check frame (might be corrupted or data)
        match recv_frame {
            Frame::Data(d) => assert_eq!(d, vec![1, 2, 3]),
            Frame::Corrupted => {} // Can happen randomly
            _ => panic!("Unexpected frame type"),
        }
    }

    #[tokio::test]
    #[test_log::test]
    async fn test_multiple_frames() {
        let event_loop = Arc::new(EventLoop::default());
        let channel = SimplexChannel::new(event_loop.clone(), FORWARD_PATH);

        // Send 3 frames at different times
        channel.send(0.0, Frame::Rr(1)).await;
        channel.send(0.1, Frame::Srej(2)).await;
        channel.send(0.2, Frame::Data(vec![1, 2, 3])).await;

        assert_eq!(event_loop.pending_count().await, 3);

        // Process all events
        event_loop.advance().await;
        event_loop.advance().await;
        event_loop.advance().await;

        // Receive all frames
        let (time1, _frame1) = channel.receive().await;
        let (time2, _frame2) = channel.receive().await;
        let (time3, _frame3) = channel.receive().await;

        // Check they arrive in time order
        assert!(time1 < time2);
        assert!(time2 < time3);
    }

    #[tokio::test]
    #[test_log::test]
    async fn test_propagation_delay() {
        let event_loop = Arc::new(EventLoop::default());
        let propagation_delay = 0.05; // 50ms
        let channel = SimplexChannel::new(event_loop.clone(), propagation_delay);

        let send_time = 1.0;
        channel.send(send_time, Frame::Rr(1)).await;

        event_loop.advance().await;

        let (recv_time, _) = channel.receive().await;

        // Expected: send_time + transmission_time + propagation + processing
        let transmission_time = FRAME_OVERHEAD as f64 / BIT_RATE as f64;
        let expected = send_time + transmission_time + propagation_delay + PROCESSING_DELAY;

        assert!((recv_time - expected).abs() < 1e-6);
    }

    #[tokio::test]
    #[test_log::test]
    async fn test_different_frame_sizes() {
        let event_loop = Arc::new(EventLoop::default());
        let channel = SimplexChannel::new(event_loop.clone(), FORWARD_PATH);

        // Small frame
        channel.send(0.0, Frame::Data(vec![0u8; 10])).await;

        // Large frame
        channel.send(0.0, Frame::Data(vec![0u8; 1000])).await;

        event_loop.advance().await;
        event_loop.advance().await;

        let (time1, _) = channel.receive().await;
        let (time2, _) = channel.receive().await;

        // Larger frame should have longer transmission time
        assert!(time2 > time1);
    }

    #[tokio::test]
    #[test_log::test]
    async fn test_ack_nak_frames() {
        let event_loop = Arc::new(EventLoop::default());
        let channel = SimplexChannel::new(event_loop.clone(), REVERSE_PATH);

        // Send ACK
        channel.send(0.0, Frame::Rr(42)).await;
        event_loop.advance().await;

        let (_, frame) = channel.receive().await;
        match frame {
            Frame::Rr(seq) => assert_eq!(seq, 42),
            Frame::Corrupted => {} // Can happen
            _ => panic!("Expected Rr frame"),
        }
    }
}
