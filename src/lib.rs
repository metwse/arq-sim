//! Selective-Repeat ARQ Simulation

#![forbid(unsafe_code, unused_must_use)]
#![warn(clippy::all, missing_docs)]

mod channel;

pub use channel::GilbertElliotChannel;

pub mod simulation;
