use crate::GilbertElliotChannel;
use std::cmp::Reverse;
use std::collections::{BTreeMap, BinaryHeap, btree_map::Entry};
use tracing::{debug, info, trace};

static FILE_SIZE_BYTES: u64 = 100_000_000;

static FRAME_PROP_DELAY_FWD: f64 = 0.040;
static FRAME_PROP_DELAY_REV: f64 = 0.010;
static FRAME_PRCS_DELAY: f64 = 0.002;

static BIT_RATE: f64 = 1e7;

/// Link layer header's size, in bytes.
static TOTAL_FRAME_OVERHEAD: u64 = 24;

/// Round-trip time
static RTT: f64 = FRAME_PROP_DELAY_REV + FRAME_PROP_DELAY_FWD + FRAME_PRCS_DELAY * 2.0;

/// Use minimum margin for timeouts
static TIMEOUT_MARGIN: f64 = 1.0001;
static BASE_TIMEOUT: f64 = RTT * TIMEOUT_MARGIN;

#[derive(Debug)]
struct Frame {
    ack_receiving_time: f64,
    success: bool,
}

/// Simulation results.
pub struct SimulationStats {
    /// Primary goodput metric.
    pub goodput: f64,
    /// Total number of retransmissions.
    pub retransmissions: u64,
    /// Total time passed while transmission.
    pub time: f64,
}

/// Runs the selective-repeat ARQ simulation.
///
/// This implementation does use timeout instead of NACKs since there is no
/// network jitter or congestion.
pub fn simulate_arq(w: u64, l: u64) -> SimulationStats {
    // + 1 for trasport layer overhead
    let frame_total_size = (l + TOTAL_FRAME_OVERHEAD + 1) * 8;
    let trans_time_per_frame = frame_total_size as f64 / BIT_RATE;

    let timeout = BASE_TIMEOUT + trans_time_per_frame * TIMEOUT_MARGIN;

    let num_frames = FILE_SIZE_BYTES.div_ceil(l);

    let ack_size_bits = (l as f64).log2().ceil() as u64;
    let frame_size_bits = (TOTAL_FRAME_OVERHEAD + l) * 8;

    let mut send_base = 0;
    let mut window: BTreeMap<u64, Frame> = BTreeMap::new();

    let mut fwd_channel = GilbertElliotChannel::new();
    let mut rev_channel = GilbertElliotChannel::new();

    let mut current_time = 0.0;

    let mut retransmissions = 0;
    let mut acked = BinaryHeap::new();

    info!(num_frames, w, l, "Simulation initialized");

    while send_base < num_frames {
        let window_end = num_frames.min(send_base + w);
        let mut action_taken = false;

        // send new frames, or retransmit failed one
        for seq_num in send_base..window_end {
            if let Entry::Vacant(e) = window.entry(seq_num) {
                if acked.as_slice().contains(&Reverse(seq_num)) {
                    continue;
                }

                let success = fwd_channel.frame_success(frame_size_bits)
                    && rev_channel.frame_success(ack_size_bits);
                e.insert(Frame {
                    ack_receiving_time: current_time + timeout,
                    success,
                });
                current_time += trans_time_per_frame;
                action_taken = true;
            }
        }

        // ack successful frames
        let mut will_delete = Vec::new();
        for (&seq_num, frame) in window.iter() {
            if frame.ack_receiving_time >= current_time {
                break;
            }

            if frame.success {
                acked.push(Reverse(seq_num));
            } else {
                retransmissions += 1;
            }

            will_delete.push(seq_num);
        }

        for seq_num in will_delete {
            window.remove(&seq_num).unwrap();
        }

        // update base of sliding window
        while let Some(&Reverse(top)) = acked.peek()
            && top == send_base
        {
            acked.pop();
            send_base += 1;

            if send_base % w == 0 {
                let goodput = (send_base * l) as f64 * 8.0 / current_time;
                trace!(
                    send_base,
                    goodput,
                    "Simulation is {:.2}% complete",
                    (send_base as f64 / num_frames as f64) * 100.0
                );
            }
        }

        if !action_taken {
            current_time += 0.0001;
        }
    }

    let goodput = FILE_SIZE_BYTES as f64 * 8.0 / current_time;
    debug!(goodput, retransmissions, current_time, "Simulation stats");

    SimulationStats {
        goodput,
        retransmissions,
        time: current_time,
    }
}
