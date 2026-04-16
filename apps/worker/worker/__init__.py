"""RQ worker consumer (API-13).

Entry point: ``python -m worker.main``. Le `API_REDIS_URL`,
`API_QUEUE_NAME` e delega para `worker_core.jobs.run_execution`.
"""

__version__ = "0.1.0"
