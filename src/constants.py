
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "resources"
OUTPUT_DIR = BASE_DIR / "output"
REPEATED_KEYS_DIR = OUTPUT_DIR / "repeated_keys"
PYCACHE_DIR = BASE_DIR / "src/__pycache__"

REQUIRED_FILES = [
        "scenario_catalog.csv",
        "network_events.csv",
        "model_predictions.csv",
        "fleet_runs.csv",
        "ecu_manifest.csv",
        "diagnostic_snapshots.csv"
    ]

JOIN_KEYS: dict[str, list[str]] = {
    "scenario_catalog.csv": ["scenario_id"],
    "fleet_runs.csv": ["fleet_run_id"],
    "model_predictions.csv": ["fleet_run_id", "model_version"],
    "network_events.csv": ["fleet_run_id"],
    "ecu_manifest.csv": ["vehicle_variant", "ecu"],
    "diagnostic_snapshots.csv": ["fleet_run_id", "ecu"],
}

CLEANUP_DIRS = [
    REPEATED_KEYS_DIR,
    PYCACHE_DIR
]

DIVIDER = "--------------------"
