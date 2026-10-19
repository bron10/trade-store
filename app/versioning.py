from app.domain import ApplyOutcome


def decide_version(stored_version: int | None, incoming_version: int) -> ApplyOutcome:
    """Choose insert, replace, or conflict for one trade id.

    A missing row is inserted. An equal or higher incoming version replaces the
    current row. A lower incoming version conflicts. Historical versions are not kept.
    """
    if stored_version is None:
        return ApplyOutcome.CREATED
    if incoming_version < stored_version:
        return ApplyOutcome.CONFLICT
    return ApplyOutcome.REPLACED
