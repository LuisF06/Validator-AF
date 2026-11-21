import logging
import numpy as np
import pandas as pd

import src.constants as const
import src.utils as utils


def build_model_eval_df(
    predictions_df: pd.DataFrame,
    fleet_runs_df: pd.DataFrame,
    scenario_catalog_df: pd.DataFrame,
) -> pd.DataFrame:
    with_runs = predictions_df.merge(
        fleet_runs_df,
        on="fleet_run_id",
        how="left",
        suffixes=("", "_run"),
        validate="many_to_one",
    )

    joined = with_runs.merge(
        scenario_catalog_df,
        on="scenario_id",
        how="left",
        suffixes=("", "_scenario"),
        validate="many_to_one",
    )

    return joined


def compute_group_metrics(group: pd.DataFrame) -> pd.Series:
    valid = group.dropna(subset=["actual_pedestrian", "predicted_pedestrian"])
    actual = valid["actual_pedestrian"]
    pred = valid["predicted_pedestrian"]

    tp = int(((actual == 1) & (pred == 1)).sum())
    fp = int(((actual == 0) & (pred == 1)).sum())
    fn = int(((actual == 1) & (pred == 0)).sum())
    tn = int(((actual == 0) & (pred == 0)).sum())

    precision = tp / (tp + fp) if (tp + fp) > 0 else np.nan
    recall = tp / (tp + fn) if (tp + fn) > 0 else np.nan
    fnr = fn / (tp + fn) if (tp + fn) > 0 else np.nan

    latencies = group["inference_latency_ms"].dropna()
    p95_latency = float(latencies.quantile(0.95)) if not latencies.empty else np.nan
    exceeds_latency_gate = (
        bool(p95_latency > const.LATENCY_LIMIT_MS) if pd.notna(p95_latency) else False
    )

    return pd.Series(
        {
            "n_total": len(group),
            "n_labeled": len(valid),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": precision,
            "recall": recall,
            "fnr": fnr,
            "p95_latency_ms": p95_latency,
            "exceeds_150ms_gate": exceeds_latency_gate,
        }
    )


def display_model_metrics(eval_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    results: dict[str, pd.DataFrame] = {}

    if "model_version" not in eval_df.columns:
        print("  -> Skipping grouped metrics: 'model_version' column missing.")
        return results

    overall = eval_df.groupby("model_version", dropna=False).apply(
        compute_group_metrics, include_groups=False
    )
    results["overall"] = overall
    paths = utils.save_table_artifacts(overall, const.MODEL_EVAL_OUT_DIR, "overall", index=True)
    print(f"  -> Saved overall metrics to {paths['csv'].name} and {paths['md'].name}")

    if "annotation_status" in eval_df.columns:
        non_review_df = eval_df[eval_df["annotation_status"] != "review"]
        no_review = non_review_df.groupby("model_version", dropna=False).apply(
            compute_group_metrics, include_groups=False
        )
        results["excluding_review"] = no_review
        paths = utils.save_table_artifacts(
            no_review, const.MODEL_EVAL_OUT_DIR, "excluding_review", index=True
        )
        print(f"  -> Saved review-excluded metrics to {paths['csv'].name} and {paths['md'].name}")

    slice_cols = ["vehicle_variant", "visibility", "weather", "road_type"]
    for col in slice_cols:
        if col in eval_df.columns:
            sliced = eval_df.groupby(["model_version", col], dropna=False).apply(
                compute_group_metrics, include_groups=False
            )
            results[f"by_{col}"] = sliced
            paths = utils.save_table_artifacts(
                sliced, const.MODEL_EVAL_OUT_DIR, f"by_{col}", index=True
            )
            print(f"  -> Saved {col} slice metrics to {paths['csv'].name} and {paths['md'].name}")

    return results


def find_risk_priority_misses(eval_df: pd.DataFrame) -> pd.DataFrame:
    required_cols = {"actual_pedestrian", "predicted_pedestrian", "visibility", "object_distance_m"}
    if not required_cols.issubset(eval_df.columns):
        logging.warning(
            "[model_evaluator] Skipping risk-priority check; missing columns: %s",
            sorted(required_cols - set(eval_df.columns)),
        )
        return pd.DataFrame()

    distance_m = pd.to_numeric(eval_df["object_distance_m"], errors="coerce")
    low_vis = eval_df["visibility"].astype(str).str.strip().str.lower() == "low"
    close_obj = distance_m <= 20

    risk_cases = eval_df[(eval_df["actual_pedestrian"] == 1) & (low_vis | close_obj)]
    misses = risk_cases[risk_cases["predicted_pedestrian"] == 0].copy()

    return misses


def model_evaluator(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    print("Evaluating Model.")
    required = ["model_predictions.csv", "fleet_runs.csv", "scenario_catalog.csv"]
    missing = [name for name in required if name not in dfs]
    if missing:
        logging.error("[model_evaluator] Missing required DataFrames: %s", missing)
        return pd.DataFrame()

    preds_df = dfs["model_predictions.csv"].copy()
    runs_df = dfs["fleet_runs.csv"].copy()
    scenarios_df = dfs["scenario_catalog.csv"].copy()

    # Handle exact duplicates if they exist
    print("  -> Removing any rows that are exact duplicates")
    preds_df = preds_df.drop_duplicates()

    print("  -> Joining: predictions -> fleet_runs -> scenario_catalog")
    eval_df = build_model_eval_df(preds_df, runs_df, scenarios_df)

    # Audit join & review-label coverage
    print("  -> Checking for missing labels")
    unlabeled_count = (
        int(eval_df["actual_pedestrian"].isna().sum())
        if "actual_pedestrian" in eval_df.columns
        else 0
    )
    if unlabeled_count:
        logging.warning(
            "[model_evaluator] %d joined prediction row(s) have missing ground-truth labels.",
            unlabeled_count,
        )

    print("  -> Checking for annotation_status='review'")
    if "annotation_status" in eval_df.columns:
        review_count = int((eval_df["annotation_status"] == "review").sum())
        logging.info(
            "[model_evaluator] Joined rows with annotation_status='review': %d",
            review_count,
        )

    # Compute precision, recall, FNR, p95 latency (overall + slices)
    print("  -> Computing metrics across model versions and slices")
    display_model_metrics(eval_df)

    misses = find_risk_priority_misses(eval_df)
    if not misses.empty:
        miss_counts = misses.groupby("model_version", dropna=False).size()
        print("  -> Risk-priority misses by model_version:", miss_counts.to_dict())

        cols_to_show = [
            c
            for c in [
                "fleet_run_id",
                "scenario_id",
                "model_version",
                "vehicle_variant",
                "visibility",
                "object_distance_m",
                "weather",
                "confidence",
                "inference_latency_ms",
                "annotation_status",
            ]
            if c in misses.columns
        ]
        paths = utils.save_table_artifacts(
            misses[cols_to_show],
            const.MODEL_EVAL_OUT_DIR,
            "risk_priority_misses",
            index=False,
        )
        print(f"  -> Saved risk-priority misses to {paths['csv'].name} and {paths['md'].name}")
    else:
        print("  -> No risk-priority misses found.")


    return eval_df