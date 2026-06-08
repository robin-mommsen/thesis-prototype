import time
from typing import List, AsyncIterator, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.services.embedding_service import embedding_service
from app.services.claude_service import claude_service
from app.models.upcycling_factsheet import UpcyclingFactsheet
from app.models.query_log import QueryLog
from app.config.config import settings

SYSTEM_PROMPT = """Du bist ein Assistent zur Generierung von Upcycling-Ideen im DIY-Kontext.

Erstelle kreative, konkrete und umsetzbare Lösungen basierend auf den gegebenen Materialien.

Eine vollständige Lösung besteht aus:
1. Einer klar formulierten Projektidee
2. Einer strukturierten Schritt-für-Schritt-Anleitung

Nutze relevante Informationen aus bereitgestellten Factsheets, sofern sie zur Nutzereingabe passen.
Übernimm sie nicht ungeprüft, sondern erstelle eine zur Nutzereingabe passende Lösung.
Wenn in der Nutzereingabe Materialien genannt werden, nutze diese als zentrale Bestandteile der Lösung.
Falls keine konkreten Materialien genannt werden, schlage geeignete wiederverwendbare Materialien vor.
Auch bei unvollständigen oder vagen Nutzereingaben soll eine möglichst hilfreiche Upcycling-Idee erstellt werden.
Zusätzliche Materialien dürfen nur verwendet werden, wenn sie für die Umsetzung notwendig sind.

Achte besonders auf:
- sinnvolle Nutzung der genannten Materialien
- Umsetzbarkeit mit den genannten Materialien
- Klarheit der Schritte
- kreative, aber realistische Ideen

Antworte immer in folgendem Format:

Idee:
<Kurze Beschreibung des Projekts>

Materialien:
- ...
- ...

Anleitung:
1. ...
2. ...
3. ..."""


class RagService:
    async def _prepare_context(self, user_goal: str, use_rag: bool, db: Session) -> tuple[str, list]:
        if not use_rag:
            return self._build_prompt(user_goal, []), []

        query_embedding = await embedding_service.create_embedding(user_goal)
        factsheets_with_scores = self._search_factsheets(db, query_embedding)
        factsheets = [f for f, _ in factsheets_with_scores]
        prompt = self._build_prompt(user_goal, factsheets)
        return prompt, factsheets_with_scores

    async def ask(self, user_goal: str, user_id: str, db: Session, use_rag: bool = True) -> str:
        start_time = time.time()
        prompt = None
        factsheets_with_scores = []

        try:
            prompt, factsheets_with_scores = await self._prepare_context(user_goal, use_rag, db)
            llm_response = await claude_service.ask_claude(prompt, system_prompt=SYSTEM_PROMPT)

            response_time_ms = int((time.time() - start_time) * 1000)
            self._log_query(
                db=db,
                user_id=user_id,
                user_goal=user_goal,
                prompt_sent=prompt,
                factsheets_with_scores=factsheets_with_scores,
                llm_response=llm_response,
                response_time_ms=response_time_ms,
                success=True,
                used_rag=use_rag,
            )

            return llm_response

        except Exception as e:
            db.rollback()
            response_time_ms = int((time.time() - start_time) * 1000)
            self._log_query(
                db=db,
                user_id=user_id,
                user_goal=user_goal,
                prompt_sent=prompt,
                factsheets_with_scores=factsheets_with_scores,
                llm_response=None,
                response_time_ms=response_time_ms,
                success=False,
                error_message=str(e),
                used_rag=use_rag,
            )
            raise

    async def ask_stream(self, user_goal: str, user_id: str, db: Session, use_rag: bool = True) -> AsyncIterator[str]:
        start_time = time.time()
        full_response = ""
        prompt = None
        factsheets_with_scores = []

        try:
            prompt, factsheets_with_scores = await self._prepare_context(user_goal, use_rag, db)

            async for chunk in claude_service.ask_claude_stream(prompt, system_prompt=SYSTEM_PROMPT):
                full_response += chunk
                yield chunk

            response_time_ms = int((time.time() - start_time) * 1000)
            self._log_query(
                db=db,
                user_id=user_id,
                user_goal=user_goal,
                prompt_sent=prompt,
                factsheets_with_scores=factsheets_with_scores,
                llm_response=full_response,
                response_time_ms=response_time_ms,
                success=True,
                used_rag=use_rag,
            )

        except Exception as e:
            db.rollback()
            response_time_ms = int((time.time() - start_time) * 1000)
            self._log_query(
                db=db,
                user_id=user_id,
                user_goal=user_goal,
                prompt_sent=prompt,
                factsheets_with_scores=factsheets_with_scores,
                llm_response=None,
                response_time_ms=response_time_ms,
                success=False,
                error_message=str(e),
                used_rag=use_rag,
            )
            raise

    def _search_factsheets(self, db: Session, embedding: List[float]) -> List[tuple]:
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"

        limit = settings.rag_factsheet_limit

        query = text(f"""
            SELECT id, title, category, input_materials, target_object, difficulty,
                   tools_required, description, steps, practical_notes, source,
                   1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM upcycling_factsheets
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT {limit}
        """)

        result = db.execute(query, {"embedding": embedding_str})
        rows = result.fetchall()

        factsheets_with_scores = []
        for row in rows:
            factsheet = UpcyclingFactsheet(
                id=row[0],
                title=row[1],
                category=row[2],
                input_materials=row[3],
                target_object=row[4],
                difficulty=row[5],
                tools_required=row[6],
                description=row[7],
                steps=row[8],
                practical_notes=row[9],
                source=row[10]
            )
            similarity = float(row[11])
            factsheets_with_scores.append((factsheet, similarity))

        return factsheets_with_scores

    def _build_prompt(self, user_goal: str, factsheets: List[UpcyclingFactsheet]) -> str:
        context_entries = []

        for idx, factsheet in enumerate(factsheets, start=1):
            entry = (
                f"Factsheet {idx}: {factsheet.title}\n"
                f"Kategorie: {factsheet.category}\n"
                f"Ausgangsmaterialien: {factsheet.input_materials}\n"
                f"Zielobjekt: {factsheet.target_object}"
            )
            if factsheet.difficulty:
                entry += f"\nSchwierigkeit: {factsheet.difficulty}"
            if factsheet.tools_required:
                entry += f"\nWerkzeuge: {factsheet.tools_required}"
            if factsheet.description:
                entry += f"\nBeschreibung: {factsheet.description}"
            if factsheet.steps:
                entry += f"\nVorgehen: {factsheet.steps}"
            if factsheet.practical_notes:
                entry += f"\nHinweise: {factsheet.practical_notes}"
            context_entries.append(entry)

        context_block = "\n\n".join(context_entries) if context_entries else ""

        return f"Kontext-Factsheets:\n{context_block}\n\nUser:\n{user_goal}"

    def _log_query(
            self,
            db: Session,
            user_id: str,
            user_goal: str,
            factsheets_with_scores: List[tuple],
            llm_response: str,
            response_time_ms: int,
            success: bool,
            prompt_sent: Optional[str] = None,
            error_message: str = None,
            used_rag: bool = True,
    ):
        factsheets_json = [
            {
                "id": factsheet.id,
                "title": factsheet.title,
                "category": factsheet.category,
                "target_object": factsheet.target_object,
                "similarity": round(score, 4)
            }
            for factsheet, score in factsheets_with_scores
        ]

        log_entry = QueryLog(
            user_id=user_id,
            user_goal=user_goal,
            prompt_sent=prompt_sent,
            factsheets_retrieved=factsheets_json,
            factsheet_count=len(factsheets_with_scores),
            llm_response=llm_response,
            response_time_ms=response_time_ms,
            success=success,
            error_message=error_message,
            used_rag=used_rag
        )

        db.add(log_entry)
        db.commit()


rag_service = RagService()
