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
