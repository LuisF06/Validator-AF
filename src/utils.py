import pandas as pd
import shutil
from pathlib import Path

def delete_directory(full_path: str | Path) -> bool:
    """Checks if a directory exists at full_path and deletes it with all contents."""
    
    dir_path = Path(full_path)
    
    if dir_path.exists() and dir_path.is_dir():
        print(f"  -> Deleting: {dir_path}")
        shutil.rmtree(dir_path)
        return True
        
    return False


def validate_files(directory_path: str, required_files: list[str]) -> None:
    """Checks if the csv files to be used are available."""
    
    target_dir = Path(directory_path)
    print("Checking if Resource files are available.")

    # Verify that the resource directory exists
    if not target_dir.is_dir():
        raise FileNotFoundError(f"Error: Resource directory not available -> {target_dir}")

    # Check if there is any data file missing
    missing_files = [
        filename for filename in required_files 
        if not (target_dir / filename).is_file()
    ]

    # If there are missing files, stop and report
    if missing_files:
        missing_list = ", ".join(missing_files)
        raise FileNotFoundError(
            f"  -> FAILED - Missing data file(s) in '{target_dir}': {missing_list}"
        )

    print("  -> PASS - Resource files available.")


def save_table_artifacts(
    df: pd.DataFrame,
    out_dir: Path,
    stem: str,
    index: bool = True,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{stem}.csv"
    md_path = out_dir / f"{stem}.md"

    df.to_csv(csv_path, index=index)

    # to_markdown() works cleanly when 'tabulate' is installed; fall back to plain text if not
    try:
        md_content = df.to_markdown(index=index)
    except ImportError:
        md_content = f"```\n{df.to_string(index=index)}\n```"

    md_path.write_text(md_content, encoding="utf-8")
    return {"csv": csv_path, "md": md_path}