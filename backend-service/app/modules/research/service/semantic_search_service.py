from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.research.llm.embedding_client import embedding_client


class SemanticSearchService:
    """
    Executes semantic vector searches over stored chunks, claims, and briefs
    using PostgreSQL pgvector HNSW cosine distance (<=>).
    """

    @staticmethod
    async def search(
        query: str,
        scope: str = "CHUNKS",  # CHUNKS, CLAIMS, BRIEFS
        underlying_code: Optional[str] = None,
        since_days: Optional[int] = None,
        top_k: int = 10,
        session: AsyncSession = None,
    ) -> List[Dict[str, Any]]:
        top_k = min(20, max(1, top_k))
        query_vector = await embedding_client.get_embedding(query)
        vector_str = "[" + ",".join(str(round(v, 6)) for v in query_vector) + "]"

        since_date = None
        if since_days:
            since_date = datetime.now(timezone.utc) - timedelta(days=since_days)

        results: List[Dict[str, Any]] = []

        if scope == "CHUNKS":
            sql = """
                SELECT c.id, c.document_id, c.text, d.title, d.domain, d.url, d.published_at,
                       1 - (c.embedding <=> :vector::vector) as similarity
                FROM research_chunks c
                JOIN research_documents d ON c.document_id = d.id
                WHERE c.status = 1
            """
            params: Dict[str, Any] = {"vector": vector_str, "limit": top_k}
            if since_date:
                sql += " AND d.published_at >= :since_date"
                params["since_date"] = since_date
            sql += " ORDER BY c.embedding <=> :vector::vector ASC LIMIT :limit;"

            res = await session.execute(text(sql), params)
            for row in res.fetchall():
                results.append({
                    "id": row[0],
                    "documentId": row[1],
                    "excerpt": row[2][:400],
                    "title": row[3],
                    "domain": row[4],
                    "url": row[5],
                    "publishedAt": row[6].isoformat() if row[6] else None,
                    "similarity": round(float(row[7]), 3),
                })

        elif scope == "CLAIMS":
            sql = """
                SELECT c.id, c.underlying_code, c.statement, c.quote, c.stance, c.magnitude, c.confidence,
                       d.title, d.domain, d.url,
                       1 - (c.embedding <=> :vector::vector) as similarity
                FROM research_claims c
                JOIN research_documents d ON c.document_id = d.id
                WHERE c.status = 1 AND c.quote_verified = true
            """
            params = {"vector": vector_str, "limit": top_k}
            if underlying_code:
                sql += " AND c.underlying_code = :u_code"
                params["u_code"] = underlying_code
            if since_date:
                sql += " AND c.published_at >= :since_date"
                params["since_date"] = since_date
            sql += " ORDER BY c.embedding <=> :vector::vector ASC LIMIT :limit;"

            res = await session.execute(text(sql), params)
            for row in res.fetchall():
                results.append({
                    "id": row[0],
                    "underlyingCode": row[1],
                    "statement": row[2],
                    "quote": row[3],
                    "stance": row[4],
                    "magnitude": row[5],
                    "confidence": float(row[6]),
                    "title": row[7],
                    "domain": row[8],
                    "url": row[9],
                    "similarity": round(float(row[10]), 3),
                })

        elif scope == "BRIEFS":
            sql = """
                SELECT c.id, c.underlying_code, c.news_status, c.score, c.thesis, c.run_id,
                       1 - (c.brief_embedding <=> :vector::vector) as similarity
                FROM research_candidates c
                WHERE c.status = 1 AND c.thesis IS NOT NULL
            """
            params = {"vector": vector_str, "limit": top_k}
            if underlying_code:
                sql += " AND c.underlying_code = :u_code"
                params["u_code"] = underlying_code
            sql += " ORDER BY c.brief_embedding <=> :vector::vector ASC LIMIT :limit;"

            res = await session.execute(text(sql), params)
            for row in res.fetchall():
                results.append({
                    "id": row[0],
                    "underlyingCode": row[1],
                    "newsStatus": row[2],
                    "score": float(row[3]) if row[3] is not None else None,
                    "thesis": row[4],
                    "runId": row[5],
                    "similarity": round(float(row[6]), 3),
                })

        return results
