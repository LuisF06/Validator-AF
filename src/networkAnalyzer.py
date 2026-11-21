import logging
import numpy as np
import pandas as pd

import src.constants as const
import src.utils as utils


def flag_gap_exceedances(network_df: pd.DataFrame) -> pd.DataFrame:
    df = network_df.copy()
    observed = pd.to_numeric(df.get("observed_gap_ms"), errors="coerce")
    expected = pd.to_numeric(df.get("expected_max_gap_ms"), errors="coerce")

    df["observed_gap_num"] = observed
    df["expected_max_gap_num"] = expected
    df["gap_exceeded"] = (observed > expected) & observed.notna() & expected.notna()
    df["gap_excess_ms"] = np.where(df["gap_exceeded"], observed - expected, 0.0)
    return df


def build_network_context_df(
    network_df: pd.DataFrame,
    fleet_runs_df: pd.DataFrame,
    ecu_manifest_df: pd.DataFrame,
    diag_df: pd.DataFrame,
) -> pd.DataFrame:
    
    ctx = network_df.merge(
        fleet_runs_df,
        on="fleet_run_id",
        how="left",
        suffixes=("", "_run"),
        validate="many_to_one",
    )

    # If network_events has an 'ecu' column, join ECU manifest & diagnostic snapshots on (vehicle_variant, ecu) and (fleet_run_id, ecu).
    # Otherwise, keep diagnostic snapshots summarized per fleet_run_id first so rows don't multiply unexpectedly.
    if "ecu" in ctx.columns and "vehicle_variant" in ctx.columns:
        if {"vehicle_variant", "ecu"}.issubset(ecu_manifest_df.columns):
            ctx = ctx.merge(
                ecu_manifest_df,
                on=["vehicle_variant", "ecu"],
                how="left",
                suffixes=("", "_ecu_manifest"),
            )
        if {"fleet_run_id", "ecu"}.issubset(diag_df.columns):
            ctx = ctx.merge(
                diag_df,
                on=["fleet_run_id", "ecu"],
                how="left",
                suffixes=("", "_diag"),
            )
    else:
        logging.info(
            "[network_analyzer] 'ecu' not directly on network_events; attaching per-run diagnostic summary."
        )
        if "fleet_run_id" in diag_df.columns:
            run_diag_counts = (
                diag_df.groupby("fleet_run_id", dropna=False)
                .size()
                .rename("diag_snapshot_count")
                .reset_index()
            )
            ctx = ctx.merge(run_diag_counts, on="fleet_run_id", how="left")

    return ctx


def summarize_gap_by_slice(ctx_df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    available = [c for c in group_cols if c in ctx_df.columns]
    if not available:
        return pd.DataFrame()

    def _agg(g: pd.DataFrame) -> pd.Series:
        out: dict[str, object] = {
            "n_events": len(g),
            "n_gap_exceeded": int(g["gap_exceeded"].sum()),
            "gap_exceed_rate": float(g["gap_exceeded"].mean()) if len(g) else np.nan,
        }
        for col in ["counter_gap", "error_frames", "packet_loss_pct", "time_sync_offset_ms"]:
            if col in g.columns:
                vals = pd.to_numeric(g[col], errors="coerce").dropna()
                out[f"{col}_mean"] = float(vals.mean()) if not vals.empty else np.nan
                out[f"{col}_max"] = float(vals.max()) if not vals.empty else np.nan
        if "bus_off" in g.columns:
            bus_off_num = pd.to_numeric(g["bus_off"], errors="coerce")
            out["bus_off_count"] = int((bus_off_num > 0).sum())
        return pd.Series(out)

    return ctx_df.groupby(available, dropna=False).apply(_agg, include_groups=False)

def summarize_diagnostics_by_variant(
    diag_df: pd.DataFrame,
    fleet_runs_df: pd.DataFrame,
    exceeded_run_ids: set,
) -> pd.DataFrame:
    if diag_df.empty or "fleet_run_id" not in diag_df.columns:
        return pd.DataFrame()

    merged = diag_df.merge(
        fleet_runs_df,
        on="fleet_run_id",
        how="left",
        suffixes=("", "_run"),
        validate="many_to_one",
    )
    merged["in_gap_exceeded_run"] = merged["fleet_run_id"].isin(exceeded_run_ids)

    group_cols = [c for c in ["vehicle_variant", "ecu", "in_gap_exceeded_run"] if c in merged.columns]
    if not group_cols:
        return merged

    return (
        merged.groupby(group_cols, dropna=False)
        .size()
        .rename("snapshot_count")
        .reset_index()
    )


def summarize_snapshot_details(
    diag_df: pd.DataFrame,
    fleet_runs_df: pd.DataFrame,
    exceeded_run_ids: set,
) -> pd.DataFrame:
    if diag_df.empty or "fleet_run_id" not in diag_df.columns:
        return pd.DataFrame()

    merged = diag_df.merge(
        fleet_runs_df,
        on="fleet_run_id",
        how="left",
        suffixes=("", "_run"),
        validate="many_to_one",
    )
    merged["in_gap_exceeded_run"] = merged["fleet_run_id"].isin(exceeded_run_ids)

    group_cols = [
        c for c in ["vehicle_variant", "ecu", "in_gap_exceeded_run"] if c in merged.columns
    ]
    if not group_cols:
        return pd.DataFrame()

    # Summarize numeric snapshot columns (excluding IDs/flags)
    skip_cols = {"fleet_run_id", "scenario_id", "vehicle_variant", "ecu", "in_gap_exceeded_run"}
    num_cols = [
        c
        for c in merged.columns
        if c not in skip_cols and pd.api.types.is_numeric_dtype(merged[c])
    ]

    agg_dict: dict[str, tuple[str, str]] = {"snapshot_count": ("fleet_run_id", "count")}
    for col in num_cols:
        agg_dict[f"{col}_mean"] = (col, "mean")
        agg_dict[f"{col}_max"] = (col, "max")

    summary = merged.groupby(group_cols, dropna=False).agg(**agg_dict).reset_index()
    return summary


def summarize_run_overlap_with_model(
    exceeded_run_ids: set,
    eval_df: pd.DataFrame | None,
    model_version: str = "2.5.0",
) -> pd.DataFrame:
    if eval_df is None or eval_df.empty or "fleet_run_id" not in eval_df.columns:
        return pd.DataFrame()

    sub = eval_df.copy()
    if "model_version" in sub.columns:
        sub = sub[sub["model_version"].astype(str) == model_version]

    distance_m = pd.to_numeric(sub.get("object_distance_m"), errors="coerce")
    low_vis = sub.get("visibility", pd.Series(dtype=str)).astype(str).str.strip().str.lower() == "low"
    is_risk_miss = (
        (sub.get("actual_pedestrian") == 1)
        & (low_vis | (distance_m <= 20))
        & (sub.get("predicted_pedestrian") == 0)
    )
    latency = pd.to_numeric(sub.get("inference_latency_ms"), errors="coerce")
    is_slow = latency > const.LATENCY_LIMIT_MS

    run_summary = (
        sub.groupby("fleet_run_id", dropna=False)
        .agg(
            vehicle_variant=("vehicle_variant", "first"),
            risk_priority_miss=("fleet_run_id", lambda s: bool(is_risk_miss.loc[s.index].any())),
            exceeds_latency_gate=("fleet_run_id", lambda s: bool(is_slow.loc[s.index].any())),
        )
        .reset_index()
    )
    run_summary["in_gap_exceeded_run"] = run_summary["fleet_run_id"].isin(exceeded_run_ids)

    return (
        run_summary.groupby(["vehicle_variant", "in_gap_exceeded_run"], dropna=False)
        .agg(
            n_runs=("fleet_run_id", "count"),
            runs_with_risk_miss=("risk_priority_miss", "sum"),
            runs_exceeding_150ms=("exceeds_latency_gate", "sum"),
        )
        .reset_index()
    )


def network_analyzer(
    dfs: dict[str, pd.DataFrame],
    eval_df: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    print("Analyzing Network & Vehicle Context.")
    required = [
        "network_events.csv",
        "fleet_runs.csv",
        "ecu_manifest.csv",
        "diagnostic_snapshots.csv",
    ]
    missing = [name for name in required if name not in dfs]
    if missing:
        logging.error("[network_analyzer] Missing required DataFrames: %s", missing)
        return {}

    net_df = flag_gap_exceedances(dfs["network_events.csv"])
    runs_df = dfs["fleet_runs.csv"].copy()
    ecu_df = dfs["ecu_manifest.csv"].copy()
    diag_df = dfs["diagnostic_snapshots.csv"].copy()

    ctx_df = build_network_context_df(net_df, runs_df, ecu_df, diag_df)

    exceedances = ctx_df[ctx_df["gap_exceeded"]].copy()
    print(f"  -> Gap exceedances (observed_gap_ms > expected_max_gap_ms): {len(exceedances)} / {len(ctx_df)}")

    if not exceedances.empty:
        paths = utils.save_table_artifacts(
            exceedances, const.NETWORK_OUT_DIR, "gap_exceedances", index=False
        )
        print(f"  -> Saved gap exceedances to {paths['csv'].name} and {paths['md'].name}")

    for slice_name, cols in [
        ("by_vehicle_variant", ["vehicle_variant"]),
        ("by_link_state", ["link_state"]),
        ("by_service_state", ["service_state"]),
    ]:
        summary = summarize_gap_by_slice(ctx_df, cols)
        if not summary.empty:
            paths = utils.save_table_artifacts(
                summary, const.NETWORK_OUT_DIR, slice_name, index=True
            )
            print(f"  -> Saved {slice_name} summary to {paths['csv'].name} and {paths['md'].name}")

    # Also save a compact snapshot/ECU overview so you can inspect faults alongside runs
    if not diag_df.empty:
        paths = utils.save_table_artifacts(
            diag_df, const.NETWORK_OUT_DIR, "diagnostic_snapshots_raw", index=False
        )
        print(f"  -> Saved diagnostic snapshots copy to {paths['csv'].name} and {paths['md'].name}")

    exceeded_run_ids = set(exceedances["fleet_run_id"].dropna()) if not exceedances.empty else set()

    diag_summary = summarize_diagnostics_by_variant(diag_df, runs_df, exceeded_run_ids)
    if not diag_summary.empty:
        paths = utils.save_table_artifacts(
            diag_summary, const.NETWORK_OUT_DIR, "diagnostics_by_variant_ecu", index=False
        )
        print(f"  -> Saved diagnostic summary to {paths['csv'].name} and {paths['md'].name}")

    if not ecu_df.empty:
        paths = utils.save_table_artifacts(
            ecu_df, const.NETWORK_OUT_DIR, "ecu_manifest_overview", index=False
        )
        print(f"  -> Saved ECU manifest overview to {paths['csv'].name} and {paths['md'].name}")

    snap_details = summarize_snapshot_details(diag_df, runs_df, exceeded_run_ids)
    if not snap_details.empty:
        paths = utils.save_table_artifacts(
            snap_details, const.NETWORK_OUT_DIR, "diagnostic_snapshot_metrics", index=False
        )
        print(f"  -> Saved diagnostic snapshot metrics to {paths['csv'].name} and {paths['md'].name}")
    
    overlap = summarize_run_overlap_with_model(exceeded_run_ids, eval_df, model_version="2.5.0")
    if not overlap.empty:
        paths = utils.save_table_artifacts(
            overlap, const.NETWORK_OUT_DIR, "overlap_2_5_0_with_gap_exceeded", index=False
        )
        print(f"  -> Saved 2.5.0 run overlap summary to {paths['csv'].name} and {paths['md'].name}")

    return {"context": ctx_df, "exceedances": exceedances}