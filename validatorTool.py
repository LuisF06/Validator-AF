import src.constants as const
import src.utils as utils

from src.fileProcessor import process_files
from src.modelAnalyzer import model_evaluator

if __name__ == "__main__":
    # Initial Cleanup
    print(const.DIVIDER)
    print("Clean-Up any unnecessary file.")
    for dir in const.CLEANUP_DIRS:
        utils.delete_directory(dir)
    print(const.DIVIDER)

    # Checking the files to check are available
    utils.validate_files(const.DATA_DIR, const.REQUIRED_FILES)
    print(const.DIVIDER)

    # Processing files to DataFrames
    processed_dfs = process_files(const.DATA_DIR, const.REQUIRED_FILES)
    print(const.DIVIDER)

    # Start Joining process
    model = model_evaluator(processed_dfs)
    print(const.DIVIDER)


    
