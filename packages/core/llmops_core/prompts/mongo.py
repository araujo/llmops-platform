"""MongoDB implementation of :class:`~llmops_core.prompts.repository.PromptRepository`."""

from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection

from llmops_core.prompts.models import PromptStatus, PromptVersionRecord, utcnow


class MongoPromptRepository:
    """Stores one BSON document per prompt version; keys are ``agent_id`` + ``name`` + ``version``."""

    def __init__(
        self,
        client: MongoClient,
        database: str,
        *,
        collection: str = "llmops_prompt_versions",
    ) -> None:
        self._coll: Collection[dict[str, Any]] = client[database][collection]

    def ensure_indexes(self) -> None:
        """Create idempotent indexes (call once at startup)."""
        self._coll.create_index(
            [("agent_id", ASCENDING), ("name", ASCENDING), ("version", ASCENDING)],
            unique=True,
            name="agent_name_version_unique",
        )
        self._coll.create_index(
            [("agent_id", ASCENDING), ("name", ASCENDING), ("status", ASCENDING), ("version", DESCENDING)],
            name="agent_name_status_version",
        )

    def upsert_version(self, record: PromptVersionRecord) -> PromptVersionRecord:
        """Replace or insert the document for this triple."""
        doc = _to_bson(record)
        filt: dict[str, Any] = {
            "agent_id": record.agent_id,
            "name": record.name,
            "version": record.version,
        }
        self._coll.replace_one(filt, doc, upsert=True)
        out = self._coll.find_one(filt)
        assert out is not None
        return _from_bson(out)

    def get_version(self, agent_id: str, name: str, version: int) -> PromptVersionRecord | None:
        doc = self._coll.find_one({"agent_id": agent_id, "name": name, "version": version})
        return _from_bson(doc) if doc else None

    def get_active(self, agent_id: str, name: str) -> PromptVersionRecord | None:
        cur = (
            self._coll.find({"agent_id": agent_id, "name": name, "status": PromptStatus.ACTIVE.value})
            .sort("version", DESCENDING)
            .limit(1)
        )
        doc = next(cur, None)
        return _from_bson(doc) if doc else None

    def list_versions(self, agent_id: str, name: str) -> list[PromptVersionRecord]:
        cur = self._coll.find({"agent_id": agent_id, "name": name}).sort("version", ASCENDING)
        return [_from_bson(d) for d in cur]

    def activate_version(self, agent_id: str, name: str, version: int) -> None:
        target = self.get_version(agent_id, name, version)
        if target is None:
            msg = f"No prompt version {agent_id!r}/{name!r} v{version}"
            raise ValueError(msg)

        self._coll.update_many(
            {"agent_id": agent_id, "name": name},
            {"$set": {"status": PromptStatus.INACTIVE.value}},
        )
        self._coll.update_one(
            {"agent_id": agent_id, "name": name, "version": version},
            {"$set": {"status": PromptStatus.ACTIVE.value}},
        )

    def deactivate_all(self, agent_id: str, name: str) -> None:
        self._coll.update_many(
            {"agent_id": agent_id, "name": name},
            {"$set": {"status": PromptStatus.INACTIVE.value}},
        )


def _to_bson(record: PromptVersionRecord) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "agent_id": record.agent_id,
        "name": record.name,
        "version": record.version,
        "status": record.status.value,
        "template": record.template,
        "metadata": dict(record.metadata),
        "model_defaults": dict(record.model_defaults),
        "labels": list(record.labels),
        "created_at": record.created_at,
    }
    return doc


def _from_bson(doc: dict[str, Any]) -> PromptVersionRecord:
    from bson import ObjectId

    oid = doc.get("_id")
    doc_id = str(oid) if isinstance(oid, ObjectId) else None

    status_raw = doc.get("status", PromptStatus.INACTIVE.value)
    status = PromptStatus(status_raw) if isinstance(status_raw, str) else PromptStatus.INACTIVE

    return PromptVersionRecord(
        agent_id=str(doc["agent_id"]),
        name=str(doc["name"]),
        version=int(doc["version"]),
        status=status,
        template=str(doc["template"]),
        metadata=dict(doc.get("metadata") or {}),
        model_defaults=dict(doc.get("model_defaults") or {}),
        labels=tuple(doc.get("labels") or ()),
        created_at=doc.get("created_at") or utcnow(),
        document_id=doc_id,
    )

