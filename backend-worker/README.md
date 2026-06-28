# CoinTwin Backend Worker

Session 0 only verifies that the worker can start as a separate process.

```powershell
python backend-worker/worker.py --once
```

Later sessions will add APScheduler, watchlist polling, Postgres advisory lock, and signal deduplication.
