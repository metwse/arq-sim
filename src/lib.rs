//! Selective-Repeat ARQ Simulation

#![forbid(unsafe_code, unused_must_use)]
#![warn(clippy::all, missing_docs)]

mod channel;

mod simulation;

pub use channel::GilbertElliotChannel;

pub use simulation::{SimulationStats, simulate_arq};
