import logging
import json
from pathlib import Path
from sqlalchemy.orm import Session
from app.config.database import SessionLocal
from app.models.upcycling_factsheet import UpcyclingFactsheet
from app.services.embedding_service import embedding_service
from app.routers.factsheet import build_embedding_text, FactsheetRequest

logger = logging.getLogger(__name__)


async def initialize_data():
    db = SessionLocal()
    try:
        logger.info("Checking database for upcycling factsheets..")
        count = db.query(UpcyclingFactsheet).count()

        if count == 0:
            logger.info("Factsheet database is empty. Initializing with seed data..")
            await initialize_factsheets(db)
            final_count = db.query(UpcyclingFactsheet).count()
            logger.info(f"Seed data initialized successfully - {final_count} factsheets added")
        else:
            logger.info(f"Database already contains {count} factsheets. Skipping initialization")
    except Exception as e:
        logger.error(f"Failed to initialize seed data: {e}")
    finally:
        db.close()


async def initialize_factsheets(db: Session):
    factsheets_path = Path(__file__).parent / "factsheets.json"

    if not factsheets_path.exists():
        raise FileNotFoundError(f"Factsheets file not found: {factsheets_path}")

    with open(factsheets_path, encoding="utf-8") as f:
        factsheets_data = json.load(f)

    for factsheet_data in factsheets_data:
        try:
            await insert_factsheet(
                db=db,
                title=factsheet_data["title"],
                category=factsheet_data["category"],
                input_materials=factsheet_data["input_materials"],
                target_object=factsheet_data["target_object"],
                difficulty=factsheet_data["difficulty"],
                tools_required=factsheet_data["tools_required"],
                description=factsheet_data["description"],
                steps=factsheet_data["steps"],
                practical_notes=factsheet_data["practical_notes"],
                source=factsheet_data.get("source", "factsheets.json"),
            )
            logger.info(f"Inserted factsheet: {factsheet_data['title']}")
        except Exception as e:
            logger.error(f"Failed to insert factsheet {factsheet_data.get('title', '<unknown>')}: {e}")


async def insert_factsheet(
        db: Session,
        title: str,
        category: str,
        input_materials: str,
        target_object: str,
        difficulty: str,
        tools_required: str,
        description: str,
        steps: str,
        practical_notes: str,
        source: str
):
    request = FactsheetRequest(
        title=title,
        category=category,
        input_materials=input_materials,
        target_object=target_object,
        difficulty=difficulty,
        tools_required=tools_required,
        description=description,
        steps=steps,
        practical_notes=practical_notes,
        source=source,
    )
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
        embedding=embedding,
    )

    db.add(factsheet)
    db.commit()
