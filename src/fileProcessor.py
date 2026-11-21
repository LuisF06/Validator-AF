from pathlib import Path
import logging
import pandas as pd

import src.constants as const
import src.utils as utils


def check_key_repeats(df: pd.DataFrame, filename: str) -> None:
    clean_name = Path(filename).name
    keys = const.JOIN_KEYS.get(clean_name)
    if not keys:
        logging.warning("[%s] No join keys configured; skipping key check.", clean_name)
        return

    missing_cols = [col for col in keys if col not in df.columns]
    if missing_cols:
        logging.warning("[%s] Missing expected key columns: %s", clean_name, missing_cols)
        return

    null_mask = df[keys].isna().any(axis=1)
    if null_mask.any():
        logging.warning(
            "[%s] Null join keys (%s): %d rows",
            clean_name,
            ", ".join(keys),
            int(null_mask.sum()),
        )

    dup_mask = df.duplicated(subset=keys, keep=False)
    if dup_mask.any():
        dups = df[dup_mask]
        group_count = dups.groupby(keys, dropna=False).ngroups

        const.REPEATED_KEYS_DIR.mkdir(parents=True, exist_ok=True)
        dump_path = const.REPEATED_KEYS_DIR / f"{Path(clean_name).stem}_key_repeats.csv"
        dups.to_csv(dump_path, index=True)

        logging.warning(
            "[%s] Repeated join key (%s): %d rows across %d groups -> full dump saved to %s",
            clean_name,
            ", ".join(keys),
            len(dups),
            group_count,
            dump_path,
        )

def process_files(
    data_dir: str | Path, required_files: list[str]
) -> dict[str, pd.DataFrame]:
  """ Imports CSV files into Data Frames, 
  checks for duplicates and removes data that can be ommited.

  Returns a dictionary of filename, DataFrame
  """
  folder = Path(data_dir)
  loaded_dfs = {}

  for filename in required_files:
    file_path = folder / filename  
    print(f"Opening {filename}...")
      
    df = pd.read_csv(file_path)
    print(f"  -> Loaded {len(df)} rows and {len(df.columns)} columns.")
    # Check if there are Exact Row Duplicates
    if df.duplicated().any():
        dups = df[df.duplicated(keep=False)]
        stem = f"{Path(filename).stem}_exact_duplicates"
        paths = utils.save_table_artifacts(dups, const.VALIDATION_OUT_DIR, stem, index=True)
        logging.warning(
            "[%s] Found %d exact duplicate row(s) -> saved to %s and %s",
            filename,
            len(dups),
            paths["csv"],
            paths["md"],
        )
    check_key_repeats(df,filename)

    loaded_dfs[filename] = df   

  return loaded_dfs