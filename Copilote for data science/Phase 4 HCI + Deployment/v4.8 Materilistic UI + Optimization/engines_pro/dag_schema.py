# engines_pro/dag_schema.py — Structured DAG schema definitions
# All DAG plan, node, condition, and output types are defined here.
# NO raw string eval — conditions use structured operator schemas only.
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════

class NodeType(str, Enum):
    """Expanded node types for UI clarity and semantic grouping."""
    OPERATION       = "operation"        # Generic compute operation
    CONDITIONAL     = "conditional"      # Branch based on structured condition
    ANALYSIS        = "analysis"         # Read-only analysis / insight extraction
    TRANSFORMATION  = "transformation"   # Mutates the DataFrame
    VISUALIZATION   = "visualization"    # Produces a chart / plot artifact
    SUMMARY         = "summary"          # Generates textual summary / report


class OperatorType(str, Enum):
    """Supported operators for structured conditions (NO raw eval)."""
    GT        = ">"
    LT        = "<"
    GTE       = ">="
    LTE       = "<="
    EQ        = "=="
    NEQ       = "!="
    IN        = "in"
    NOT_IN    = "not_in"
    CONTAINS  = "contains"
    IS_NULL   = "is_null"
    NOT_NULL  = "not_null"


class NodeStatus(str, Enum):
    """Runtime status of a DAG node during execution."""
    PENDING   = "pending"
    RUNNING   = "running"
    SUCCESS   = "success"
    FAILED    = "failed"
    SKIPPED   = "skipped"
    RETRYING  = "retrying"
    ABORTED   = "aborted"


class OutputType(str, Enum):
    """Standardized node output type contract."""
    SCALAR    = "scalar"
    DATAFRAME = "dataframe"
    ARTIFACT  = "artifact"     # chart base64, report text, etc.
    DICT      = "dict"
    NONE      = "none"


class OperandKind(str, Enum):
    """How to resolve an operand in a StructuredCondition."""
    LITERAL    = "literal"     # Use the value as-is (number, string, bool)
    VARIABLE   = "variable"    # Resolve from ExecutionContext.variables[value]
    STEP_REF   = "step_ref"    # Resolve from ExecutionContext.step_outputs[value]


# ═══════════════════════════════════════════════════════════════════════
# OPERAND — typed value reference with explicit resolution rules
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Operand:
    """A typed value reference used in conditions.

    Resolution rules:
      - LITERAL:  value is used directly (e.g. 0.5, "yes", True)
      - VARIABLE: value is a key into ExecutionContext.variables
      - STEP_REF: value is a node_id, resolved from ExecutionContext.step_outputs
    """
    kind: OperandKind = OperandKind.LITERAL
    value: Any = None

    def to_dict(self) -> dict:
        return {"kind": self.kind.value if isinstance(self.kind, OperandKind) else self.kind,
                "value": self.value}

    @classmethod
    def from_dict(cls, d: dict) -> "Operand":
        return cls(
            kind=OperandKind(d.get("kind", "literal")),
            value=d.get("value"),
        )


# ═══════════════════════════════════════════════════════════════════════
# STRUCTURED CONDITION — safe, typed, no eval()
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class StructuredCondition:
    """A condition evaluated without raw eval().

    Operands are resolved via the Operand.kind rules above.
    Operators are whitelisted in OperatorType.
    """
    left: Operand = field(default_factory=Operand)
    operator: OperatorType = OperatorType.EQ
    right: Operand = field(default_factory=Operand)

    def to_dict(self) -> dict:
        return {
            "left": self.left.to_dict(),
            "operator": self.operator.value if isinstance(self.operator, OperatorType) else self.operator,
            "right": self.right.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StructuredCondition":
        return cls(
            left=Operand.from_dict(d.get("left", {})),
            operator=OperatorType(d.get("operator", "==")),
            right=Operand.from_dict(d.get("right", {})),
        )


# ═══════════════════════════════════════════════════════════════════════
# NODE OUTPUT CONTRACT — standardized output shape
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class NodeOutput:
    """Standardized output from DAG node execution.

    Every node must produce a NodeOutput so the executor can:
      - Validate output type
      - Store it consistently in ExecutionContext
      - Pass it to downstream nodes
    """
    output_type: OutputType = OutputType.NONE
    value: Any = None
    summary: str = ""    # Brief human-readable summary of what was produced

    def to_dict(self) -> dict:
        return {
            "output_type": self.output_type.value if isinstance(self.output_type, OutputType) else self.output_type,
            "summary": self.summary,
        }


# ═══════════════════════════════════════════════════════════════════════
# EXECUTION METADATA — per-node tracking
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ExecutionMetadata:
    """Runtime metadata tracked per node during execution."""
    node_id: str = ""
    status: NodeStatus = NodeStatus.PENDING
    model_used: str = ""
    execution_time_ms: float = 0.0
    retry_count: int = 0
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
    output_type: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "status": self.status.value if isinstance(self.status, NodeStatus) else self.status,
            "model_used": self.model_used,
            "execution_time_ms": round(self.execution_time_ms, 1),
            "retry_count": self.retry_count,
            "warnings": self.warnings,
            "error": self.error,
            "output_type": self.output_type,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


# ═══════════════════════════════════════════════════════════════════════
# DAG NODE
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class DAGNode:
    """A single node in the execution DAG.

    For operation-type nodes (operation/analysis/transformation/visualization/summary):
      - operation:   what to do (e.g. "compute_correlation", "plot_histogram")
      - inputs:      named inputs (keys → Operand references)
      - output_var:  name under which output is stored in ExecutionContext.variables
      - expected_output_type: what type of output this node should produce

    For conditional nodes:
      - condition:    StructuredCondition to evaluate
      - true_branch:  list of node_ids to execute if True
      - false_branch: list of node_ids to execute if False
    """
    id: str = ""
    type: NodeType = NodeType.OPERATION
    description: str = ""

    # --- Operation fields ---
    operation: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    output_var: str = ""
    expected_output_type: OutputType = OutputType.SCALAR

    # --- Conditional fields ---
    condition: Optional[StructuredCondition] = None
    true_branch: List[str] = field(default_factory=list)
    false_branch: List[str] = field(default_factory=list)

    # --- Graph ---
    depends_on: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, NodeType) else self.type,
            "description": self.description,
            "depends_on": self.depends_on,
        }
        if self.type == NodeType.CONDITIONAL:
            d["condition"] = self.condition.to_dict() if self.condition else None
            d["true_branch"] = self.true_branch
            d["false_branch"] = self.false_branch
        else:
            d["operation"] = self.operation
            d["inputs"] = self.inputs
            d["output_var"] = self.output_var
            d["expected_output_type"] = (
                self.expected_output_type.value
                if isinstance(self.expected_output_type, OutputType)
                else self.expected_output_type
            )
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "DAGNode":
        node_type = NodeType(d.get("type", "operation"))
        node = cls(
            id=d.get("id", f"node_{uuid.uuid4().hex[:8]}"),
            type=node_type,
            description=d.get("description", ""),
            depends_on=d.get("depends_on", []),
        )
        if node_type == NodeType.CONDITIONAL:
            cond_data = d.get("condition")
            node.condition = StructuredCondition.from_dict(cond_data) if cond_data else None
            node.true_branch = d.get("true_branch", [])
            node.false_branch = d.get("false_branch", [])
        else:
            node.operation = d.get("operation", "")
            node.inputs = d.get("inputs", {})
            node.output_var = d.get("output_var", "")
            node.expected_output_type = OutputType(d.get("expected_output_type", "scalar"))
        return node


# ═══════════════════════════════════════════════════════════════════════
# DAG EDGE
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class DAGEdge:
    """Explicit directed edge in the DAG graph."""
    source: str = ""
    target: str = ""
    edge_type: str = "dependency"    # "dependency" | "true_branch" | "false_branch"

    def to_dict(self) -> dict:
        return {"source": self.source, "target": self.target, "edge_type": self.edge_type}

    @classmethod
    def from_dict(cls, d: dict) -> "DAGEdge":
        return cls(source=d.get("source", ""), target=d.get("target", ""),
                   edge_type=d.get("edge_type", "dependency"))


# ═══════════════════════════════════════════════════════════════════════
# DAG PLAN — top-level plan object with versioning
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class DAGPlan:
    """A complete DAG execution plan with versioning and audit trail.

    Attributes:
        plan_id:       Unique plan identifier
        version:       Incremented on each re-plan
        replan_count:  Total number of re-plans that occurred
        user_goal:     Original user request
        nodes:         Ordered list of DAGNode
        edges:         Explicit edge list
        metadata:      Per-node ExecutionMetadata (populated during execution)
    """
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:12]}")
    version: int = 1
    replan_count: int = 0
    user_goal: str = ""
    nodes: List[DAGNode] = field(default_factory=list)
    edges: List[DAGEdge] = field(default_factory=list)
    metadata: Dict[str, ExecutionMetadata] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "planned"   # planned | approved | executing | completed | failed | replanned

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "version": self.version,
            "replan_count": self.replan_count,
            "user_goal": self.user_goal,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "metadata": {k: v.to_dict() for k, v in self.metadata.items()},
            "created_at": self.created_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DAGPlan":
        plan = cls(
            plan_id=d.get("plan_id", f"plan_{uuid.uuid4().hex[:12]}"),
            version=d.get("version", 1),
            replan_count=d.get("replan_count", 0),
            user_goal=d.get("user_goal", ""),
            created_at=d.get("created_at", datetime.now(timezone.utc).isoformat()),
            status=d.get("status", "planned"),
        )
        plan.nodes = [DAGNode.from_dict(n) for n in d.get("nodes", [])]
        plan.edges = [DAGEdge.from_dict(e) for e in d.get("edges", [])]
        return plan

    def get_node(self, node_id: str) -> Optional[DAGNode]:
        """Lookup a node by ID."""
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def get_node_ids(self) -> List[str]:
        """Return ordered list of node IDs."""
        return [n.id for n in self.nodes]

    def build_edges_from_nodes(self) -> None:
        """Auto-generate edges from node depends_on + conditional branches."""
        self.edges = []
        for node in self.nodes:
            for dep in node.depends_on:
                self.edges.append(DAGEdge(source=dep, target=node.id, edge_type="dependency"))
            if node.type == NodeType.CONDITIONAL:
                for tb in node.true_branch:
                    self.edges.append(DAGEdge(source=node.id, target=tb, edge_type="true_branch"))
                for fb in node.false_branch:
                    self.edges.append(DAGEdge(source=node.id, target=fb, edge_type="false_branch"))
