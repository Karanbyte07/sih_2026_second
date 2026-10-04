"""Audit service — persistent logging of user actions to the DB."""
from datetime import datetime

from sqlalchemy.orm import Session

from src.db.models import AuditLog, User


def log_action(
    db: Session,
    action: str,
    user: User | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Write an audit entry and commit immediately so it survives partial failures."""
    entry = AuditLog(
        timestamp=datetime.utcnow(),
        user_id=user.id if user else None,
        user_name=user.name if user else "system",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_=metadata,
    )
    db.add(entry)
    db.commit()
