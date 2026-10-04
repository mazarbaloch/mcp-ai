def error_message(error: BaseException) -> str:
    """AnyIO can wrap the useful error in nested task-group exceptions."""
    if isinstance(error, BaseExceptionGroup):
        return "; ".join(error_message(item) for item in error.exceptions)
    if isinstance(error, TimeoutError):
        return "Operation timed out. Check the local model/server or try a narrower task."
    return str(error) or type(error).__name__
