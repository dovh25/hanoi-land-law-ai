"""Chat API endpoint with authentication and message persistence."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage

from backend.api.deps import get_db, get_current_user
from backend.db.models.user import User
from backend.models.chat import ChatRequest, ChatResponse
from backend.services.chat_service import ChatService
from backend.services.session_service import session_service
from backend.services.llm import LLMUnavailable

logger = logging.getLogger(__name__)

router = APIRouter()


def get_chat_service(request: Request) -> ChatService:
    """Dependency to get the shared chat service instance."""
    return request.app.state.chat_service


@router.post("/chat", response_model=ChatResponse, status_code=status.HTTP_200_OK)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """
    Send a message to Gemini and return its reply.
    Requires authentication. Messages are persisted to the database.

    Args:
        payload: Chat request with message and optional session_id
        db: Database session
        current_user: Authenticated user
        service: Chat service instance

    Returns:
        ChatResponse with reply, sources, and session_id
    """
    session_id = payload.session_id

    # Create new session if not provided
    if not session_id:
        logger.info(f"Creating new session for user {current_user.id}")
        chat_session = session_service.create_session(
            db=db,
            user_id=current_user.id,
            title="New Chat",
        )
        session_id = chat_session.id
        is_new_session = True
    else:
        # Verify session ownership
        chat_session = session_service.get_session(
            db=db,
            session_id=session_id,
            user_id=current_user.id,
        )
        if chat_session is None:
            logger.warning(
                f"Session {session_id} not found for user {current_user.id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )
        is_new_session = False

    logger.info(
        f"Chat request: user={current_user.id}, session={session_id}, new={is_new_session}"
    )

    # Load existing messages from database into LangChain history
    # This ensures continuity even if the server restarted
    existing_messages = session_service.get_recent_messages(
        db, session_id, service.settings.MAX_HISTORY_MESSAGES
    )

    # Reconstruct bounded request-local history; SQLite remains the source of truth.
    history = []
    for msg in existing_messages:
        if msg.role == "user":
            history.append(HumanMessage(content=msg.content))
        elif msg.role == "ai":
            history.append(AIMessage(content=msg.content))

    try:
        # Call the RAG pipeline
        response_data = service.respond(payload.message, history=history)
    except LLMUnavailable:
        raise
    except Exception:
        logger.exception("Failed to handle chat request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate response",
        )

    # Save user message to database
    session_service.add_message(
        db=db,
        session_id=session_id,
        role="user",
        content=payload.message,
        sources=None,
        commit=False,
    )

    # Save AI response to database with sources
    sources = response_data.get("sources", [])
    session_service.add_message(
        db=db,
        session_id=session_id,
        role="ai",
        content=response_data["answer"],
        sources=sources,
        commit=False,
    )

    # Update session timestamp
    session_service.update_session_timestamp(db=db, session_id=session_id)

    # Auto-title session from first message if it's a new session
    if is_new_session:
        session_service.auto_title_session(
            db=db,
            session_id=session_id,
            user_id=current_user.id,
            first_message=payload.message,
        )

    return ChatResponse(
        reply=response_data["answer"],
        sources=sources,
        session_id=session_id,
    )
