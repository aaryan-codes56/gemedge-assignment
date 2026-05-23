import time
import functools
import logging
from typing import Callable, Any, Tuple, Type, Optional

from src.config import RETRY_CONFIG
from src.utils.logger import get_logger

logger = get_logger("retry_utils")


def retry(
    max_attempts: Optional[int] = None,
    delay: Optional[float] = None,
    backoff_factor: Optional[float] = None,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """
    A robust, exception-safe retry decorator with exponential backoff and logging support.
    
    Args:
        max_attempts: Total execution attempts (default: from RETRY_CONFIG).
        delay: Initial sleep delay in seconds (default: from RETRY_CONFIG).
        backoff_factor: Exponential multiplier applied to delay after each retry (default: from RETRY_CONFIG).
        exceptions: A tuple of exception classes that trigger a retry.
    """
    # Fetch defaults from configuration
    attempts = max_attempts if max_attempts is not None else RETRY_CONFIG.get("MAX_ATTEMPTS", 3)
    init_delay = delay if delay is not None else RETRY_CONFIG.get("DELAY_SECONDS", 2.0)
    backoff = backoff_factor if backoff_factor is not None else RETRY_CONFIG.get("BACKOFF_FACTOR", 2.0)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = init_delay
            
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == attempts:
                        logger.error(
                            f"Execution of '{func.__name__}' failed on final attempt ({attempt}/{attempts}). "
                            f"Error: {e}",
                            exc_info=True
                        )
                        raise e

                    logger.warning(
                        f"Attempt {attempt}/{attempts} of '{func.__name__}' failed with exception: {type(e).__name__} ({e}). "
                        f"Retrying in {current_delay:.2f} seconds..."
                    )
                    
                    time.sleep(current_delay)
                    current_delay *= backoff

            return None  # Defensive backup, should never be hit since we raise on the last attempt

        return wrapper

    return decorator
