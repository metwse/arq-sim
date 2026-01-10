use std::{
    cmp::Ordering,
    collections::{BTreeSet, BinaryHeap},
    future::Future,
    pin::Pin,
};
use tokio::sync::Mutex;

/// A future type that can be scheculed.
pub type EventFuture = Pin<Box<dyn Future<Output = ()> + Send>>;

struct Event {
    time: f64,
    id: i64,
    event: EventFuture,
}

impl PartialEq for Event {
    fn eq(&self, other: &Self) -> bool {
        other.time == self.time
    }
}

impl Eq for Event {}

impl Ord for Event {
    fn cmp(&self, other: &Self) -> Ordering {
        other.time.total_cmp(&self.time)
    }
}

impl PartialOrd for Event {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

/// An event loop implementation for discrete time simulation.
pub struct EventLoop {
    events: Mutex<BinaryHeap<Event>>,
    cancelled_events: Mutex<BTreeSet<i64>>,
    event_id: Mutex<i64>,
}

impl Default for EventLoop {
    fn default() -> Self {
        Self {
            events: Mutex::new(BinaryHeap::new()),
            cancelled_events: Mutex::new(BTreeSet::new()),
            event_id: Mutex::new(0),
        }
    }
}

impl EventLoop {
    /// Run next event in the loop
    pub async fn advance(&self) {
        let has_been_cancelled;
        let event;

        {
            let mut events = self.events.lock().await;
            let mut cancelled_events = self.cancelled_events.lock().await;

            event = if let Some(event) = events.pop() {
                event
            } else {
                return;
            };

            has_been_cancelled = cancelled_events.remove(&event.id);
        }

        if !has_been_cancelled {
            event.event.await
        }
    }

    /// Cancels event with given id
    pub async fn cancel(&mut self, event_id: i64) {
        self.cancelled_events.lock().await.insert(event_id);
    }

    /// Schedules a new event
    pub async fn schedule(&mut self, event: EventFuture, time: f64) -> i64 {
        let mut events = self.events.lock().await;
        let mut event_id = self.event_id.lock().await;

        let id = *event_id;
        events.push(Event { time, id, event });

        *event_id += 1;
        id
    }

    /// Returns number of pending events
    pub async fn pending_count(&self) -> usize {
        self.events.lock().await.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use tokio::sync::Mutex as TokioMutex;

    #[tokio::test]
    #[test_log::test]
    async fn test_schedule_and_advance() {
        let mut event_loop = EventLoop::default();
        let executed = Arc::new(TokioMutex::new(false));

        let executed_clone = executed.clone();
        event_loop
            .schedule(
                Box::pin(async move {
                    *executed_clone.lock().await = true;
                }),
                1.0,
            )
            .await;

        assert!(*executed.lock().await);

        event_loop.advance().await;

        assert!(*executed.lock().await);
    }

    #[tokio::test]
    #[test_log::test]
    async fn test_event_ordering() {
        let mut event_loop = EventLoop::default();
        let order = Arc::new(TokioMutex::new(Vec::new()));

        // Schedule events out of order
        let order_clone = order.clone();
        event_loop
            .schedule(
                Box::pin(async move {
                    order_clone.lock().await.push(3);
                }),
                3.0,
            )
            .await;

        let order_clone = order.clone();
        event_loop
            .schedule(
                Box::pin(async move {
                    order_clone.lock().await.push(1);
                }),
                1.0,
            )
            .await;

        let order_clone = order.clone();
        event_loop
            .schedule(
                Box::pin(async move {
                    order_clone.lock().await.push(2);
                }),
                2.0,
            )
            .await;

        // Advance all events
        event_loop.advance().await;
        event_loop.advance().await;
        event_loop.advance().await;

        let result = order.lock().await;
        assert_eq!(*result, vec![1, 2, 3]);
    }

    #[tokio::test]
    #[test_log::test]
    async fn test_event_cancellation() {
        let mut event_loop = EventLoop::default();
        let executed = Arc::new(TokioMutex::new(Vec::new()));

        let executed_clone = executed.clone();
        let id1 = event_loop
            .schedule(
                Box::pin(async move {
                    executed_clone.lock().await.push(1);
                }),
                1.0,
            )
            .await;

        let executed_clone = executed.clone();
        event_loop
            .schedule(
                Box::pin(async move {
                    executed_clone.lock().await.push(2);
                }),
                2.0,
            )
            .await;

        // Cancel first event
        event_loop.cancel(id1).await;

        // Advance both
        event_loop.advance().await;
        event_loop.advance().await;

        let result = executed.lock().await;
        assert_eq!(*result, vec![2]); // Only second event executed
    }

    #[tokio::test]
    #[test_log::test]
    async fn test_multiple_events_same_time() {
        let mut event_loop = EventLoop::default();
        let executed = Arc::new(TokioMutex::new(Vec::new()));

        // Schedule multiple events at same time
        for i in 0..3 {
            let executed_clone = executed.clone();
            event_loop
                .schedule(
                    Box::pin(async move {
                        executed_clone.lock().await.push(i);
                    }),
                    1.0,
                )
                .await;
        }

        event_loop.advance().await;
        event_loop.advance().await;
        event_loop.advance().await;

        let result = executed.lock().await;
        assert_eq!(result.len(), 3);
    }

    #[tokio::test]
    #[test_log::test]
    async fn test_pending_count() {
        let mut event_loop = EventLoop::default();

        assert_eq!(event_loop.pending_count().await, 0);

        event_loop.schedule(Box::pin(async {}), 1.0).await;
        event_loop.schedule(Box::pin(async {}), 2.0).await;

        assert_eq!(event_loop.pending_count().await, 2);

        event_loop.advance().await;

        assert_eq!(event_loop.pending_count().await, 1);

        event_loop.advance().await;

        assert_eq!(event_loop.pending_count().await, 0);
    }

    #[tokio::test]
    #[test_log::test]
    async fn test_empty_advance() {
        let event_loop = EventLoop::default();

        // Should not panic on empty queue
        event_loop.advance().await;

        assert_eq!(event_loop.pending_count().await, 0);
    }
}
