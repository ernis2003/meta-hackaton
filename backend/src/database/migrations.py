from pathlib import Path


def migrate(db):
    """Idempotent additive version 1 migration; no existing user data is replaced."""
    db.executescript((Path(__file__).with_name('migrations') / '001_analyses.sql').read_text())
    # Run once on application startup; use one worker for synchronous local jobs.
    db.execute("UPDATE analyses SET status='failed', error='Processing interrupted by server restart' "
               "WHERE status IN ('pending','processing')")
