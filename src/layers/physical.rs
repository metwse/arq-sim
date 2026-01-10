use crate::common::*;

use rand::random;
use std::{sync::Mutex as StdMutex, time::Duration};
use tokio::{
    sync::mpsc::{self, UnboundedReceiver, UnboundedSender},
    time,
};

/// Pyhsical layer frame
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
    tx: UnboundedSender<Frame>,
    rx: Option<UnboundedReceiver<Frame>>,
    good: StdMutex<bool>,
}

impl Default for SimplexChannel {
    fn default() -> Self {
        let (tx, rx) = mpsc::unbounded_channel();

        Self {
            tx,
            rx: Some(rx),
            good: StdMutex::new(true),
        }
    }
}

impl SimplexChannel {
    /// Sends a frame.
    pub fn send(&self, frame: Frame) {
        let mut corrupted = false;

        {
            let mut state = self.good.lock().unwrap();

            for _ in 0..frame.size_bits() {
                let r: f64 = random();

                if *state {
                    if r < GOOD_STATE_BER {
                        corrupted = true;
                    }
                    if r < P_G_TO_B {
                        *state = false;
                    }
                } else {
                    if r < BAD_STATE_BER {
                        corrupted = true;
                    }
                    if r < P_G_TO_B {
                        *state = true;
                    }
                }
            }
        }

        let propagation_time: f64 = frame.size_bits() as f64 / BIT_RATE as f64;

        tokio::spawn({
            let tx = self.tx.clone();

            async move {
                time::sleep(Duration::from_secs_f64(propagation_time + PROCESSING_DELAY)).await;
                tx.send(if corrupted { Frame::Corrupted } else { frame })
                    .ok()
            }
        });
    }

    /// Gets the rx struct wrapped with the channel.
    pub fn take_receiver(&mut self) -> Option<UnboundedReceiver<Frame>> {
        self.rx.take()
    }
}
