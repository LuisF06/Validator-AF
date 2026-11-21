import src.constants as const
import src.utils as utils

from src.fileProcessor import process_files

if __name__ == "__main__":
    # Initial Cleanup
    print(const.DIVIDER)
    print("Cleaning up any unnecessary file.")
    for dir in const.CLEANUP_DIRS:
        utils.delete_directory(dir)
    print(const.DIVIDER)

    # Checking the files to check are available
    utils.validate_files(const.DATA_DIR, const.REQUIRED_FILES)
    print(const.DIVIDER)

    # Processing files to DataFrames
    processed_dfs = process_files(const.DATA_DIR, const.REQUIRED_FILES)
    print(const.DIVIDER)


    
