use rand::prelude::*;

static GOOD_STATE_BER: f64 = 1e-6;
static BAD_STATE_BER: f64 = 5e-3;

static GOOD_TO_BAD_TANSITION_P: f64 = 0.002;
static BAD_TO_GOOD_TANSITION_P: f64 = 0.05;

static GOOD_STATE: bool = true;
static BAD_STATE: bool = false;

/// Gilbert-Elliot model using Jump-Ahead logic.
///
/// Calculates bit distances to state transitions to avoid bit-by-bit loops.
pub struct GilbertElliotChannel {
    state: bool,
    bits_until_next_state_change: i64,
}

impl Default for GilbertElliotChannel {
    fn default() -> Self {
        let mut channel = Self {
            state: GOOD_STATE,
            bits_until_next_state_change: 0,
        };

        channel.bits_until_next_state_change = channel.get_bits_to_transition();
        channel
    }
}

impl GilbertElliotChannel {
    /// Creates a new Gilbert-Elliot model channel.
    pub fn new() -> Self {
        Self::default()
    }

    fn get_bits_to_transition(&self) -> i64 {
        let p = if self.state == GOOD_STATE {
            GOOD_TO_BAD_TANSITION_P
        } else {
            BAD_TO_GOOD_TANSITION_P
        };

        let r: f64 = rand::rng().random();

        (r.ln() / (1.0 - p).ln()).floor() as i64 + 1
    }

    /// Wheter or not a frame with `num_bits` can successfully transmitted.
    pub fn frame_success(&mut self, num_bits: u64) -> bool {
        let mut bits_processed = 0;
        let mut frame_corrupted = false;

        let num_bits = num_bits as i64;

        while bits_processed < num_bits {
            let bits_in_chunk = (num_bits - bits_processed).min(self.bits_until_next_state_change);

            let ber = if self.state == GOOD_STATE {
                GOOD_STATE_BER
            } else {
                BAD_STATE_BER
            };

            if !frame_corrupted {
                let r: f64 = rand::rng().random();

                if r > (1.0 - ber).powf(bits_in_chunk as f64) {
                    frame_corrupted = true;
                }
            }

            bits_processed += bits_in_chunk;
            self.bits_until_next_state_change -= bits_in_chunk;

            if self.bits_until_next_state_change <= 0 {
                self.state = if self.state == GOOD_STATE {
                    BAD_STATE
                } else {
                    GOOD_STATE
                };
                self.bits_until_next_state_change = self.get_bits_to_transition();
            }
        }

        !frame_corrupted
    }
}
