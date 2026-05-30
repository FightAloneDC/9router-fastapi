"""RequestDetail model — stores full request/response payloads for each proxy request."""

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, func

from app.models.base import Base


class RequestDetail(Base):
    __tablename__ = "request_details"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(100), nullable=True, index=True)
    model = Column(String(255), nullable=True)
    connection_id = Column(String(255), nullable=True)
    timestamp = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status = Column(String(50), nullable=False, server_default="ok")

    # Latency in milliseconds
    latency_ttft = Column(Integer, nullable=True)
    latency_total = Column(Integer, nullable=True)

    # Token counts
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)

    # Full request/response payloads (stored as JSON text)
    request = Column(Text, nullable=True)           # Client's original request
    provider_request = Column(Text, nullable=True)   # Translated request sent to provider
    provider_response = Column(Text, nullable=True)  # Raw response from provider
    response = Column(Text, nullable=True)           # Final response returned to client
