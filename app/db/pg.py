from sqlalchemy.exc import SQLAlchemyError


def sqlstate(exc: BaseException) -> str | None:
    orig = getattr(exc, "orig", None)
    if orig is None:
        return None
    state = getattr(orig, "sqlstate", None)
    return str(state) if state is not None else None


def is_version_conflict(exc: BaseException) -> bool:
    return isinstance(exc, SQLAlchemyError) and sqlstate(exc) == "P0001"


def is_unique_violation(exc: BaseException) -> bool:
    return isinstance(exc, SQLAlchemyError) and sqlstate(exc) == "23505"
