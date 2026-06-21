"""The pyramid-of-brains memory store.

Every node (SB or URR) owns a *local brain* — a folder on disk that accumulates
high-parameter memory entries and organises them with pyramid filtering
(Node -> Main -> Sub -> Micro). There is one shared *Master Log* that records
everything (Principle 13: Master Log is Sacred).

Storage is plain JSON files so the user fully owns and can read their brain with
no database and no vendor lock-in. A DB backend can implement the same interface
later without touching the engine.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any

from .models import MemoryEntry, _now


class NodeBrain:
    """One node's local, self-updating brain."""

    def __init__(self, root: str, node_id: str, name: str = "") -> None:
        self.node_id = node_id
        self.name = name
        self.dir = os.path.join(root, "brains", node_id)
        os.makedirs(self.dir, exist_ok=True)
        self._meta_path = os.path.join(self.dir, "_brain.json")
        self.meta = self._load_meta()

    def _load_meta(self) -> dict[str, Any]:
        if os.path.exists(self._meta_path):
            with open(self._meta_path, encoding="utf-8") as f:
                return json.load(f)
        return {
            "node_id": self.node_id,
            "name": self.name,
            "created_at": _now(),
            "last_update": _now(),
            "entry_count": 0,
            "pyramid": {"main": [], "sub": [], "micro": []},
            "parameters": {},
        }

    def _save_meta(self) -> None:
        self.meta["last_update"] = _now()
        with open(self._meta_path, "w", encoding="utf-8") as f:
            json.dump(self.meta, f, indent=2, ensure_ascii=False)

    def write(self, entry: MemoryEntry) -> str:
        """Automatic memory write (Principle 10)."""
        path = os.path.join(self.dir, f"{entry.entry_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f, indent=2, ensure_ascii=False)
        # roll the node's pyramid up from the entry's pyramid
        for level in ("main", "sub", "micro"):
            for item in entry.pyramid.get(level, []):
                if item not in self.meta["pyramid"][level]:
                    self.meta["pyramid"][level].append(item)
        for k, v in entry.parameters.items():
            self.meta["parameters"][k] = v
        self.meta["entry_count"] = self.meta.get("entry_count", 0) + 1
        self._save_meta()
        return entry.entry_id

    def read_all(self) -> list[MemoryEntry]:
        out: list[MemoryEntry] = []
        for fn in sorted(os.listdir(self.dir)):
            if fn.endswith(".json") and fn != "_brain.json":
                with open(os.path.join(self.dir, fn), encoding="utf-8") as f:
                    out.append(MemoryEntry(**json.load(f)))
        return out

    def search(self, query: str) -> list[MemoryEntry]:
        q = query.lower()
        return [e for e in self.read_all() if q in (e.content + " " + " ".join(e.tags)).lower()]


class Memory:
    """The whole brain: all node brains + the Master Log + cross-node search."""

    def __init__(self, root: str = ".sourceborn") -> None:
        self.root = root
        os.makedirs(root, exist_ok=True)
        self.master_log_path = os.path.join(root, "master_log.jsonl")
        self._brains: dict[str, NodeBrain] = {}

    def brain(self, node_id: str, name: str = "") -> NodeBrain:
        if node_id not in self._brains:
            self._brains[node_id] = NodeBrain(self.root, node_id, name)
        return self._brains[node_id]

    def write(self, node_id: str, entry: MemoryEntry, name: str = "") -> str:
        entry_id = self.brain(node_id, name).write(entry)
        self.master_log(
            {"event": "memory_write", "node": node_id, "entry": entry_id,
             "classification": entry.classification, "evidence_tag": entry.evidence_tag}
        )
        return entry_id

    def master_log(self, record: dict[str, Any]) -> None:
        """Append-only sacred log."""
        record = {"at": _now(), **record}
        with open(self.master_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def search(self, query: str) -> list[tuple[str, MemoryEntry]]:
        """Cross-node memory search — the basis of Dot Connection (SB-37)."""
        hits: list[tuple[str, MemoryEntry]] = []
        brains_dir = os.path.join(self.root, "brains")
        if not os.path.isdir(brains_dir):
            return hits
        for node_id in sorted(os.listdir(brains_dir)):
            for e in self.brain(node_id).search(query):
                hits.append((node_id, e))
        return hits

    def stats(self) -> dict[str, Any]:
        brains_dir = os.path.join(self.root, "brains")
        nodes = sorted(os.listdir(brains_dir)) if os.path.isdir(brains_dir) else []
        total = sum(self.brain(n).meta.get("entry_count", 0) for n in nodes)
        return {"nodes_with_brains": len(nodes), "total_memory_entries": total}
