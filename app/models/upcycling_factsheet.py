from sqlalchemy import Column, Integer, String, Text
from pgvector.sqlalchemy import Vector
from app.config.database import Base


class UpcyclingFactsheet(Base):
    __tablename__ = "upcycling_factsheets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    input_materials = Column(Text, nullable=False)
    target_object = Column(String(255), nullable=False)
    difficulty = Column(String(50))
    tools_required = Column(Text)
    description = Column(Text, nullable=False)
    steps = Column(Text, nullable=False)
    practical_notes = Column(Text)
    source = Column(String(255))
    retrieval_text = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=False)
