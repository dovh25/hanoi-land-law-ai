"""Legal vocabulary and UTC persistence; no authoritative inference."""
from datetime import timezone
from enum import StrEnum
from sqlalchemy import DateTime, Enum
from sqlalchemy.types import TypeDecorator


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class ValidityStatus(StrEnum):
    UNKNOWN = "unknown"
    IN_FORCE = "in_force"
    PARTIALLY_EXPIRED = "partially_expired"
    EXPIRED = "expired"
    REPEALED = "repealed"
    SUSPENDED = "suspended"
    NOT_YET_EFFECTIVE = "not_yet_effective"


class ProvisionKind(StrEnum):
    PART = "part"
    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"
    ARTICLE = "article"
    CLAUSE = "clause"
    POINT = "point"
    ANNEX = "annex"
    TABLE = "table"
    UNSTRUCTURED = "unstructured"


class RelationshipKind(StrEnum):
    AMENDS = "amends"
    REPEALS = "repeals"
    REPLACES = "replaces"
    IMPLEMENTS = "implements"
    CONSOLIDATES = "consolidates"


def enum_type(kind):
    return Enum(kind, values_callable=lambda values: [v.value for v in values],
                native_enum=False, create_constraint=True, validate_strings=True)


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("An explicit timezone is required")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None
