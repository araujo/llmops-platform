"""Minimal in-memory :class:`PromptRepository` for tests (no Mongo)."""

from __future__ import annotations

from dataclasses import replace

from llmops_core.prompts.models import PromptStatus, PromptVersionRecord


class InMemoryPromptRepository:
    """Dict-backed store for :func:`seed_prompts_from_seeds` tests."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str, int], PromptVersionRecord] = {}

    def upsert_version(
        self, record: PromptVersionRecord
    ) -> PromptVersionRecord:
        key = (record.agent_id, record.name, record.version)
        self._by_key[key] = record
        return record

    def get_version(
        self, agent_id: str, name: str, version: int
    ) -> PromptVersionRecord | None:
        return self._by_key.get((agent_id, name, version))

    def get_active(self, agent_id: str, name: str) -> PromptVersionRecord | None:
        for key, rec in self._by_key.items():
            aid, pname, _ = key
            if (
                aid == agent_id
                and pname == name
                and rec.status == PromptStatus.ACTIVE
            ):
                return rec
        return None

    def list_versions(
        self, agent_id: str, name: str
    ) -> list[PromptVersionRecord]:
        rows = [
            r
            for k, r in self._by_key.items()
            if k[0] == agent_id and k[1] == name
        ]
        return sorted(rows, key=lambda r: r.version)

    def activate_version(
        self, agent_id: str, name: str, version: int
    ) -> None:
        target = self.get_version(agent_id, name, version)
        if target is None:
            msg = f"No prompt version {agent_id!r}/{name!r} v{version}"
            raise ValueError(msg)
        for key in list(self._by_key.keys()):
            aid, pname, ver = key
            if aid != agent_id or pname != name:
                continue
            rec = self._by_key[key]
            st = (
                PromptStatus.ACTIVE
                if ver == version
                else PromptStatus.INACTIVE
            )
            self._by_key[key] = replace(rec, status=st)

    def deactivate_all(self, agent_id: str, name: str) -> None:
        for key in list(self._by_key.keys()):
            aid, pname, _ = key
            if aid == agent_id and pname == name:
                rec = self._by_key[key]
                self._by_key[key] = replace(rec, status=PromptStatus.INACTIVE)
