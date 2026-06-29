from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import DESCENDING, ReturnDocument

from storage.job_store import Job, JobStatus


class MongoJobStore:
    """Async MongoDB-backed job store using Motor."""

    def __init__(self, url: str, db_name: str) -> None:
        self._url = url
        self._db_name = db_name
        self._client: Optional[AsyncIOMotorClient] = None

    async def connect(self) -> None:
        self._client = AsyncIOMotorClient(self._url)
        col = self._client[self._db_name].jobs
        await col.create_index("job_id", unique=True)
        await col.create_index("status")
        await col.create_index([("created_at", DESCENDING)])

    def close(self) -> None:
        if self._client:
            self._client.close()

    @property
    def _col(self):
        return self._client[self._db_name].jobs

    def _to_job(self, doc: dict) -> Job:
        ca = doc["created_at"]
        ua = doc["updated_at"]
        return Job(
            job_id=doc["job_id"],
            task=doc["task"],
            status=JobStatus(doc["status"]),
            result=doc.get("result"),
            error=doc.get("error"),
            filename=doc.get("filename"),
            question=doc.get("question"),
            created_at=ca.timestamp() if isinstance(ca, datetime) else float(ca),
            updated_at=ua.timestamp() if isinstance(ua, datetime) else float(ua),
        )

    async def create(self, task: str, filename: str = "", question: str = "") -> Job:
        job_id = str(uuid.uuid4())
        now = datetime.utcnow()
        await self._col.insert_one({
            "job_id": job_id,
            "task": task,
            "status": JobStatus.PENDING.value,
            "result": None,
            "error": None,
            "filename": filename or None,
            "question": question or None,
            "created_at": now,
            "updated_at": now,
        })
        return Job(
            job_id=job_id,
            task=task,
            filename=filename or None,
            question=question or None,
            created_at=now.timestamp(),
            updated_at=now.timestamp(),
        )

    async def get(self, job_id: str) -> Optional[Job]:
        doc = await self._col.find_one({"job_id": job_id})
        return self._to_job(doc) if doc else None

    async def update(self, job_id: str, **kwargs) -> Optional[Job]:
        if "status" in kwargs and isinstance(kwargs["status"], JobStatus):
            kwargs["status"] = kwargs["status"].value
        kwargs["updated_at"] = datetime.utcnow()
        doc = await self._col.find_one_and_update(
            {"job_id": job_id},
            {"$set": kwargs},
            return_document=ReturnDocument.AFTER,
        )
        return self._to_job(doc) if doc else None

    async def list_jobs(
        self,
        status: Optional[str] = None,
        task: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[Job]:
        query: dict = {}
        if status:
            query["status"] = status
        if task:
            query["task"] = task
        cursor = self._col.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [self._to_job(doc) for doc in docs]

    async def get_stats(self) -> dict:
        pipeline = [
            {"$group": {
                "_id": {"status": "$status", "task": "$task"},
                "count": {"$sum": 1},
            }}
        ]
        docs = await self._col.aggregate(pipeline).to_list(length=None)
        stats: dict = {"by_status": {}, "by_task": {}, "total": 0}
        for doc in docs:
            s = doc["_id"]["status"]
            t = doc["_id"]["task"]
            c = doc["count"]
            stats["by_status"][s] = stats["by_status"].get(s, 0) + c
            stats["by_task"][t] = stats["by_task"].get(t, 0) + c
            stats["total"] += c
        return stats

    async def delete(self, job_id: str) -> bool:
        result = await self._col.delete_one({"job_id": job_id})
        return result.deleted_count > 0
