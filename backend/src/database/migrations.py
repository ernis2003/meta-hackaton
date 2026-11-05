from pathlib import Path


def migrate(db):
    """Idempotent additive version 1 migration; no existing user data is replaced."""
    for script in sorted(Path(__file__).with_name('migrations').glob('[0-9][0-9][0-9]_*.sql')):
        db.executescript(script.read_text(encoding='utf-8'))
    # Run once on application startup; use one worker for synchronous local jobs.
    db.execute("UPDATE analyses SET status='failed', error='Processing interrupted by server restart' "
               "WHERE status IN ('pending','processing')")
