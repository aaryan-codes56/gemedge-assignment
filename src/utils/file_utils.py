import json
from pathlib import Path
from typing import Any, List, Union, Dict
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger("file_utils")


def ensure_path_exists(path: Union[str, Path]) -> Path:
    """
    Ensures that the directory or the parent directory of a file path exists.
    Returns the resolved Path object.
    """
    path_obj = Path(path).resolve()
    
    # If the path has a suffix, assume it's a file, and ensure its parent exists.
    if path_obj.suffix:
        directory = path_obj.parent
    else:
        directory = path_obj
        
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created directory structure: {directory}")
        
    return path_obj


def create_directories(paths: List[Union[str, Path]]) -> None:
    """
    Creates a list of directories if they do not exist.
    """
    for p in paths:
        ensure_path_exists(p)
    logger.info(f"Verified / Created {len(paths)} core system directories.")


def save_json(data: Any, filepath: Union[str, Path], indent: int = 4) -> None:
    """
    Saves serializable Python objects to a JSON file. Automatically handles directory creation.
    """
    dest_path = ensure_path_exists(filepath)
    try:
        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        logger.info(f"Successfully saved JSON to: {dest_path}")
    except IOError as e:
        logger.error(f"IOError occurred while saving JSON to {dest_path}: {e}")
        raise
    except TypeError as e:
        logger.error(f"Serialization error occurred while saving JSON: {e}")
        raise


def save_csv(data: Union[pd.DataFrame, List[Dict[str, Any]]], filepath: Union[str, Path]) -> None:
    """
    Saves a Pandas DataFrame or a list of dictionaries to a CSV file.
    Automatically handles directory creation and validation checks.
    """
    dest_path = ensure_path_exists(filepath)
    try:
        if isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, list):
            if not data:
                logger.warning(f"Attempted to save an empty list as CSV to {dest_path}. Creating empty file.")
                df = pd.DataFrame()
            else:
                df = pd.DataFrame(data)
        else:
            raise TypeError("Data must be either a pandas DataFrame or a list of dictionaries.")

        df.to_csv(dest_path, index=False, encoding="utf-8-sig")
        logger.info(f"Successfully saved CSV ({len(df)} rows) to: {dest_path}")
    except Exception as e:
        logger.error(f"Failed to save CSV to {dest_path}: {e}")
        raise
