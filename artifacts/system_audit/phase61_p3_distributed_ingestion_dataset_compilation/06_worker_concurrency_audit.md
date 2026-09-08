# 06 WORKER CONCURRENCY AUDIT

- Bounded Worker Limit: Max 4–8 workers based on CPU core availability. Zero unbounded process spawning.
- Thread Safety: Mutex locks (`threading.Lock`) safeguard task cache and novelty evaluation.
