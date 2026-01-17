//! Main simulation worker.

use tracing::trace;
use crate::GilbertElliotChannel;
use std::cmp::Reverse;
use std::collections::{hash_map::Entry, BinaryHeap, HashMap};

static FILE_SIZE_BYTES: u64 = 1_000_000;

static FRAME_PROP_DELAY_FWD: f64 = 0.040;
static FRAME_PROP_DELAY_REV: f64 = 0.010;
static FRAME_PRCS_DELAY: f64 = 0.002;

static BIT_RATE: f64 = 1e7;

/// Transmission + link layer header's size, in bits.
static TOTAL_FRAME_OVERHEAD: u64 = 32;

/// Round-trip time
static RTT: f64 = FRAME_PROP_DELAY_REV + FRAME_PROP_DELAY_FWD + FRAME_PRCS_DELAY * 2.0;

/// Use minimum margin for timeouts
static TIMEOUT_MARGIN: f64 = 1.005;
static BASE_TIMEOUT: f64 = RTT * TIMEOUT_MARGIN;

#[derive(Debug)]
struct Frame {
    ack_receiving_time: f64,
    success: bool,
}

/// Runs the selective-repeat ARQ simulation.
///
/// This implementation does use timeout instead of NACKs since there is no
/// network jitter or congestion.
pub fn simulate_arq(w: u64, l: u64) {
    let frame_total_size = (l + TOTAL_FRAME_OVERHEAD) * 8;
    let trans_time_per_frame = frame_total_size as f64 / BIT_RATE;

    let timeout = BASE_TIMEOUT + trans_time_per_frame * TIMEOUT_MARGIN;

    let num_frames = FILE_SIZE_BYTES.div_ceil(l);

    let ack_size_bits = (l as f64).log2().ceil() as u64;
    let frame_size_bits = (TOTAL_FRAME_OVERHEAD + l) * 8;

    let mut send_base = 0;
    let mut send_time: HashMap<u64, Frame> = HashMap::new();

    let mut fwd_channel = GilbertElliotChannel::new();
    let mut rev_channel = GilbertElliotChannel::new();

    let mut transmitting_time = 0.0;

    let mut retransmissions = 0;
    let mut acked = BinaryHeap::new();

    trace!(num_frames, w, l, "Simulation initialized");

    while send_base < num_frames {
        let window_end = num_frames.min(send_base + w);
        let mut action_taken = false;

        // send new frames, or retransmit failed one
        for seq_num in send_base..window_end {
            if let Entry::Vacant(e) = send_time.entry(seq_num) {
                if acked.as_slice().contains(&Reverse(seq_num)) {
                    continue;
                }

                let success = fwd_channel.frame_success(frame_size_bits) && rev_channel.frame_success(ack_size_bits);
                e.insert(Frame {
                    ack_receiving_time: transmitting_time + timeout,
                    success,
                });
                transmitting_time += trans_time_per_frame;
                action_taken = true;
            }
        }

        let mut will_delete = Vec::new();
        for (&seq_num, frame) in send_time.iter() {
            if frame.ack_receiving_time >= transmitting_time {
                continue;
            }

            if frame.success {
                acked.push(Reverse(seq_num));
            } else {
                retransmissions += 1;
            }

            will_delete.push(seq_num);
        }

        while let Some(&Reverse(top)) = acked.peek() && top == send_base {
            acked.pop();
            send_base += 1;

            if send_base % l == 0 {
                trace!(send_base);
            }
        }

        for seq_num in will_delete {
            send_time.remove(&seq_num).unwrap();
        }

        if !action_taken {
            transmitting_time += 0.00001;
        }
    }

    let goodput = FILE_SIZE_BYTES as f64 / transmitting_time;
    trace!(goodput, retransmissions, transmitting_time, "Simulation stats")
}
