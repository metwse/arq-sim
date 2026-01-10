use tokio::sync::Mutex;
use tracing::info;

use crate::{common::*, event_loop};
use crate::layers::physical::Frame;
use crate::{
    event_loop::EventLoop,
    layers::{link::SimplexLink, physical::SimplexChannel},
};
use std::sync::Arc;
use std::time::Duration;

/// Start the simulation
pub async fn run(window_size: u64, frame_size: usize, data: Vec<u8>) {
    let event_loop = Arc::new(EventLoop::default());
    let forward_channel = Arc::new(SimplexChannel::new(Arc::clone(&event_loop), FORWARD_PATH));
    let reverse_channel = Arc::new(SimplexChannel::new(Arc::clone(&event_loop), REVERSE_PATH));
    let last_sent_segment = Arc::new(Mutex::new(window_size));

    let link = Arc::new(SimplexLink::new(
        forward_channel.clone(),
        reverse_channel.clone(),
        Arc::clone(&event_loop),
        window_size,
    ));

    let segment_count = data.len().div_ceil(frame_size);
    let mut segments = Vec::with_capacity(segment_count);

    for i in 0..segment_count {
        segments.push(Vec::from(
            &data[i * frame_size..((i + 1) * frame_size).min(data.len())],
        ));
    }

    let mut time = 0.0;
    for segment in segments.iter().take(window_size as usize) {
        time += link.send_data(time, segment.clone()).await.unwrap();
    }

    event_loop.set_tick({
        let event_loop = Arc::clone(&event_loop);
        let link = Arc::clone(&link);
        let segments = Arc::new(segments);
        let last_sent_segment = Arc::clone(&last_sent_segment);

        Some(Box::new(move || {
            let event_loop = Arc::clone(&event_loop);
            let link = Arc::clone(&link);
            let segments = Arc::clone(&segments);
            let last_sent_segment = Arc::clone(&last_sent_segment);

            tokio::spawn(async move {
                let mut last_sent_segment = last_sent_segment.lock().await;

                if *last_sent_segment < segment_count as u64
                    && link
                        .send_data(event_loop.get_time(), segments[*last_sent_segment as usize].clone())
                        .await
                        .is_some()
                {
                    *last_sent_segment += 1;
                }
            });
        }))
    });

    // simulation task
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

    // receiver entity
    tokio::spawn({
        let forward_channel = Arc::clone(&forward_channel);
        let reverse_channel = Arc::clone(&reverse_channel);
        let link = Arc::clone(&link);

        async move {
            loop {
                let (time, frame) = forward_channel.receive().await;

                let (response, _) = link.receive_frame(frame).await;

                if let Some(response) = response {
                    reverse_channel.send(time, response).await;
                }
            }
        }
    });

    // handle acks from receiver
    tokio::spawn({
        let reverse_channel = Arc::clone(&reverse_channel);
        let link = Arc::clone(&link);

        async move {
            loop {
                let (time, frame) = reverse_channel.receive().await;

                match frame {
                    Frame::Rr(seq) => {
                        link.handle_ack(seq).await;
                    }
                    Frame::Srej(seq) => {
                        link.handle_nak(time, seq).await;
                    }
                    Frame::Corrupted => {}
                    _ => unreachable!("Unexcepted Data"),
                }
            }
        }
    });

    tokio::time::sleep(Duration::from_secs(100)).await;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    #[test_log::test]
    pub async fn test_simulation() {
        run(8, 2, vec![0; 10_000_000]).await;
    }
}
