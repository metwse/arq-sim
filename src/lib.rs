//! Selective-Repeat ARQ Simulation

#![forbid(unsafe_code, unused_must_use)]
#![warn(clippy::all, missing_docs)]

/// Common channel config.
pub mod common;

/// Network layers.
pub mod layers;

/// Frame/timer scheduler.
pub mod event_loop;
