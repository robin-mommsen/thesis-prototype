from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP, JSON
from sqlalchemy.sql import func
from app.config.database import Base


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(TIMESTAMP, server_default=func.current_timestamp(), index=True)
    user_id = Column(String(255), index=True)
    user_goal = Column(Text, nullable=False)
    factsheets_retrieved = Column(JSON)
    factsheet_count = Column(Integer)
    llm_response = Column(Text)
    response_time_ms = Column(Integer)
    error_message = Column(Text)
    success = Column(Boolean, default=True)
    used_rag = Column(Boolean, default=True, index=True)
    prompt_sent = Column(Text)
