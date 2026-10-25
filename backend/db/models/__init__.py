"""SQLAlchemy models package."""

from backend.db.models.user import User
from backend.db.models.chat_session import ChatSession
from backend.db.models.message import Message
from backend.db.models.message_source import MessageSource
from backend.db.models.legal import (
    LegalDocument, AcquisitionManifest, SourceArtifact, DocumentVersion,
    LegalProvision, ProvisionVersion, LegalRelationship, TerritorialApplicability,
    CorpusRelease, CorpusReleaseDocument, CorpusReleaseRelationship,
)

__all__ = ["User", "ChatSession", "Message", "MessageSource"]
