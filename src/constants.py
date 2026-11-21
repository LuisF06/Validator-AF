
from pathlib import Path

# Dir constants for easy navigation
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "resources"
OUTPUT_DIR = BASE_DIR / "output"
VALIDATION_OUT_DIR = OUTPUT_DIR / "validation"
MODEL_EVAL_OUT_DIR = OUTPUT_DIR / "model_evaluation"
NETWORK_OUT_DIR = OUTPUT_DIR / "network_analysis"
REPEATED_KEYS_DIR = OUTPUT_DIR / "repeated_keys"
PYCACHE_DIR = BASE_DIR / "src/__pycache__"

CLEANUP_DIRS = [
    REPEATED_KEYS_DIR,
    PYCACHE_DIR
]

# File and primary key to file relation constants
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

# Constants for calculations
LATENCY_LIMIT_MS = 150.0

# Misc constants
DIVIDER = "------------------------------"
