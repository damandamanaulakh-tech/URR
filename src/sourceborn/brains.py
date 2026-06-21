"""Per-node local brains and their settings.

Principle 6 (Local Brain Per Node) + Principle 7 (Pyramid Filtering at Every
Node): every one of the 70 SB + 25 URR nodes owns a configurable local brain.
This module defines the **settings of each node brain** and a registry that
materialises, loads, edits, and weekly-updates all 95 of them on disk.

Each ``NodeConfig`` is the full setting-set for one node:
  * pyramid capacities (Node -> Main -> Sub -> Micro)
  * write policy (when it writes to memory)
  * URR gate (is it followed by a verification pass)
  * human-review flag (Risk Gate is non-bypassable — Principle 19)
  * weekly auto-update (Principle 12)
  * new-parameter generation (Principle 11)
  * which of the 64-parameter groups it tracks
  * risk level, immutability, interconnection
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict

from .models import _now
from .nodes import SB_NODES, URR_NODES, SB_PYRAMID, URR_PYRAMID, STAGES

# 64-parameter groups each stage's brains focus on (see parameters.PARAMETER_BANK).
STAGE_GROUPS: dict[int, list[str]] = {
    1: ["Intent", "Signal", "Integrity"],
    2: ["Affect", "Human Shadow", "Identity", "Pressure"],
    3: ["Doubt", "Gap"],
    4: ["Evidence", "Reading"],
    5: ["Memory", "Loop", "Symbol", "Transformation"],
    6: ["Evidence", "Loop"],
    7: ["Risk", "Boundary", "Cost", "Score"],
    8: ["Memory", "Score", "Integrity"],
}
STAGE_WRITE = {1: "every_visit", 8: "checkpoint"}        # others -> on_finding
STAGE_RISK = {2: "medium", 6: "medium", 7: "high"}        # others -> low

# Node-specific overrides (human review, immutability, URR gates, generators).
HUMAN_REVIEW = {"SB-11", "SB-53", "SB-55", "SB-68",
                "URR-11", "URR-12", "URR-13", "URR-14", "URR-15", "URR-24"}
IMMUTABLE_SOURCE = {"SB-01", "SB-04"}
URR_GATE_AFTER = {"SB-08", "SB-18", "SB-28", "SB-36", "SB-44", "SB-52", "SB-60", "SB-70"}
PARAM_GENERATORS = {"SB-02", "SB-05", "SB-22", "SB-43", "SB-51"}


@dataclass
class NodeConfig:
    node_id: str
    name: str
    kind: str                       # "SB" | "URR"
    stage: int                      # 1..8 for SB, 0 for URR
    role: str
    pyramid: dict                   # capacities per level
    write_policy: str = "on_finding"   # every_visit | on_finding | checkpoint
    urr_gate: bool = False          # a URR verification pass follows this node
    human_review: bool = False      # forces human review (non-bypassable)
    weekly_update: bool = True      # auto Monday refresh (Principle 12)
    can_generate_parameters: bool = True  # Principle 11
    risk_level: str = "low"         # low | medium | high
    tracked_groups: list[str] = field(default_factory=list)
    immutable_source: bool = False  # raw source never changes (Principle 14)
    interconnect: str = "any"       # may feed-forward to any node (Principle 8)
    status: str = "active"
    updated_at: str = field(default_factory=_now)


def _sb_config(node) -> NodeConfig:
    return NodeConfig(
        node_id=node.sb_id, name=node.name, kind="SB", stage=node.stage,
        role=node.purpose, pyramid=dict(SB_PYRAMID),
        write_policy=STAGE_WRITE.get(node.stage, "on_finding"),
        urr_gate=node.sb_id in URR_GATE_AFTER,
        human_review=node.sb_id in HUMAN_REVIEW,
        can_generate_parameters=node.sb_id in PARAM_GENERATORS or node.stage in (5, 6),
        risk_level=STAGE_RISK.get(node.stage, "low"),
        tracked_groups=list(STAGE_GROUPS.get(node.stage, [])),
        immutable_source=node.sb_id in IMMUTABLE_SOURCE,
    )


def _urr_config(node) -> NodeConfig:
    return NodeConfig(
        node_id=node.urr_id, name=node.name, kind="URR", stage=0,
        role=node.triggers, pyramid=dict(URR_PYRAMID),
        write_policy="on_finding", urr_gate=False,
        human_review=node.urr_id in HUMAN_REVIEW, risk_level="medium",
        tracked_groups=["Evidence", "Risk", "Score", "Boundary"],
    )


def build_default_configs() -> dict[str, NodeConfig]:
    """All 95 node-brain configs, from the canonical node map."""
    cfgs: dict[str, NodeConfig] = {}
    for n in SB_NODES:
        cfgs[n.sb_id] = _sb_config(n)
    for n in URR_NODES:
        cfgs[n.urr_id] = _urr_config(n)
    return cfgs


class BrainRegistry:
    """Materialises, loads, edits and updates the settings of all node brains.

    Configs persist as ``<root>/brains/<node_id>/_config.json`` (next to the
    node's memory in ``_brain.json``), so settings survive and stay editable.
    """

    def __init__(self, root: str = ".sourceborn") -> None:
        self.root = root
        self.configs: dict[str, NodeConfig] = {}
        self.init_all()

    def _path(self, node_id: str) -> str:
        d = os.path.join(self.root, "brains", node_id)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "_config.json")

    def init_all(self) -> None:
        """Create any missing node brains with defaults; keep edited ones."""
        defaults = build_default_configs()
        for node_id, cfg in defaults.items():
            path = self._path(node_id)
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    self.configs[node_id] = NodeConfig(**json.load(f))
            else:
                self.configs[node_id] = cfg
                self._save(cfg)

    def _save(self, cfg: NodeConfig) -> None:
        with open(self._path(cfg.node_id), "w", encoding="utf-8") as f:
            json.dump(asdict(cfg), f, indent=2, ensure_ascii=False)

    def get(self, node_id: str) -> NodeConfig | None:
        return self.configs.get(node_id)

    def all(self) -> list[NodeConfig]:
        return list(self.configs.values())

    def by_stage(self) -> dict[str, list[NodeConfig]]:
        out: dict[str, list[NodeConfig]] = {}
        for s in STAGES:
            out[f"SB stage {s.number}: {s.name}"] = [
                c for c in self.configs.values() if c.kind == "SB" and c.stage == s.number]
        out["URR (verification)"] = [c for c in self.configs.values() if c.kind == "URR"]
        return out

    EDITABLE = {
        "write_policy", "urr_gate", "human_review", "weekly_update",
        "can_generate_parameters", "risk_level", "tracked_groups",
        "status", "interconnect",
    }

    def update(self, node_id: str, **settings) -> NodeConfig:
        cfg = self.configs.get(node_id)
        if cfg is None:
            raise KeyError(node_id)
        for k, v in settings.items():
            if k in self.EDITABLE:
                setattr(cfg, k, v)
        cfg.updated_at = _now()
        self._save(cfg)
        return cfg

    def weekly_update(self) -> dict:
        """Principle 12: refresh every local brain that has weekly_update on."""
        n = 0
        for cfg in self.configs.values():
            if cfg.weekly_update:
                cfg.updated_at = _now()
                self._save(cfg)
                n += 1
        return {"updated": n, "total": len(self.configs), "at": _now()}
