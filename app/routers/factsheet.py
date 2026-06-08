from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional, List
from app.config.database import get_db
from app.models.upcycling_factsheet import UpcyclingFactsheet
from app.services.embedding_service import embedding_service

router = APIRouter()


class FactsheetRequest(BaseModel):
    title: str
    category: str
    input_materials: str
    target_object: str
    difficulty: Optional[str] = None
    tools_required: Optional[str] = None
    description: str
    steps: str
    practical_notes: Optional[str] = None
    source: Optional[str] = None

    @field_validator("title", "target_object")
    @classmethod
    def validate_varchar255(cls, value):
        if not value or not value.strip():
            raise ValueError("field cannot be empty")
        if len(value) > 255:
            raise ValueError("field cannot exceed 255 characters")
        return value.strip()

    @field_validator("category")
    @classmethod
    def validate_varchar100(cls, value):
        if not value or not value.strip():
            raise ValueError("field cannot be empty")
        if len(value) > 100:
            raise ValueError("field cannot exceed 100 characters")
        return value.strip()

    @field_validator("input_materials", "description", "steps")
    @classmethod
    def validate_required_text(cls, value):
        if not value or not value.strip():
            raise ValueError("field cannot be empty")
        return value.strip()

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, value):
        if value is not None and len(value) > 50:
            raise ValueError("difficulty cannot exceed 50 characters")
        return value.strip() if value else None

    @field_validator("tools_required", "practical_notes")
    @classmethod
    def validate_optional_text(cls, value):
        return value.strip() if value else None

    @field_validator("source")
    @classmethod
    def validate_source(cls, value):
        if value is not None and len(value) > 255:
            raise ValueError("source cannot exceed 255 characters")
        return value.strip() if value else None


class FactsheetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    category: str
    input_materials: str
    target_object: str
    difficulty: Optional[str]
    tools_required: Optional[str]
    description: Optional[str]
    steps: Optional[str]
    practical_notes: Optional[str]
    source: Optional[str]


def build_embedding_text(data: FactsheetRequest) -> str:
    return "\n".join([
        f"Titel: {data.title}",
        f"Kategorie: {data.category}",
        f"Ausgangsmaterialien: {data.input_materials}",
        f"Zielobjekt: {data.target_object}",
        f"Schwierigkeit: {data.difficulty}",
        f"Werkzeuge: {data.tools_required}",
        f"Beschreibung: {data.description}",
        f"Schritte: {data.steps}",
        f"Hinweise: {data.practical_notes}",
    ])


def get_or_404(db: Session, factsheet_id: int) -> UpcyclingFactsheet:
    factsheet = db.query(UpcyclingFactsheet).filter(UpcyclingFactsheet.id == factsheet_id).first()
    if not factsheet:
        raise HTTPException(status_code=404, detail="Factsheet not found")
    return factsheet


@router.get("/factsheets", response_model=List[FactsheetResponse])
def get_factsheets(db: Session = Depends(get_db)):
    return db.query(UpcyclingFactsheet).order_by(
        UpcyclingFactsheet.category,
        UpcyclingFactsheet.title
    ).all()


@router.get("/factsheet/{factsheet_id}", response_model=FactsheetResponse)
def get_factsheet(factsheet_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, factsheet_id)


@router.post("/factsheet", response_model=FactsheetResponse, status_code=201)
async def add_factsheet(request: FactsheetRequest, db: Session = Depends(get_db)):
    retrieval_text = build_embedding_text(request)
    embedding = await embedding_service.create_embedding(retrieval_text)

    factsheet = UpcyclingFactsheet(
        title=request.title,
        category=request.category,
        input_materials=request.input_materials,
        target_object=request.target_object,
        difficulty=request.difficulty,
        tools_required=request.tools_required,
        description=request.description,
        steps=request.steps,
        practical_notes=request.practical_notes,
        source=request.source,
        retrieval_text=retrieval_text,
        embedding=embedding
    )

    db.add(factsheet)
    db.commit()
    db.refresh(factsheet)
    return factsheet


@router.put("/factsheet/{factsheet_id}", response_model=FactsheetResponse)
async def update_factsheet(factsheet_id: int, request: FactsheetRequest, db: Session = Depends(get_db)):
    factsheet = get_or_404(db, factsheet_id)

    factsheet.title = request.title
    factsheet.category = request.category
    factsheet.input_materials = request.input_materials
    factsheet.target_object = request.target_object
    factsheet.difficulty = request.difficulty
    factsheet.tools_required = request.tools_required
    factsheet.description = request.description
    factsheet.steps = request.steps
    factsheet.practical_notes = request.practical_notes
    factsheet.source = request.source
    factsheet.retrieval_text = build_embedding_text(request)
    factsheet.embedding = await embedding_service.create_embedding(factsheet.retrieval_text)

    db.commit()
    db.refresh(factsheet)
    return factsheet


@router.delete("/factsheet/{factsheet_id}", status_code=204)
def delete_factsheet(factsheet_id: int, db: Session = Depends(get_db)):
    factsheet = get_or_404(db, factsheet_id)
    db.delete(factsheet)
    db.commit()
