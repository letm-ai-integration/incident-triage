# Shared constants for incident triage

MAX_INVESTIGATION_RETRIES = 3
VERIFICATION_LOOP_LIMIT = 2

# Staleness thresholds in days
RUNBOOK_STALENESS_THRESHOLD_DAYS = 180

# Default confidence scores
DEFAULT_CONFIDENCE_SCORE = 0.5

# SLA windows (minutes)
SLA_WINDOWS = {
    "P1": 15,
    "P2": 30,
    "P3": 60,
    "P4": 120,
}
