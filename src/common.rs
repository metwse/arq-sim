/// 10Mbps channel
pub static BIT_RATE: i64 = 10_000_000;

/// Bit error rate in good state
pub static GOOD_STATE_BER: f64 = 1e-6;

/// Bit error rate in bad state
pub static BAD_STATE_BER: f64 = 5e-3;

/// Good to bad state transition probability
pub static P_G_TO_B: f64 = 0.002;

/// Bad to good state transition probability
pub static P_B_TO_G: f64 = 0.05;

/// Frame header size
pub static FRAME_OVERHEAD: u64 = 24 * 8;

/// Forward propagation delay
pub static FORWARD_PATH: f64 = 0.040;

/// Reverse (ACK) propagation delay
pub static REVERSE_PATH: f64 = 0.010;

/// Processing delay per frame
pub static PROCESSING_DELAY: f64 = 0.002;
