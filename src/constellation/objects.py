"""Domain objects for the Landscape Map v2 pipeline.

This module implements the four core objects from ARCHITECTURE.md:
1. Paper – semilattice coordinate + argument DAG
2. Claim – directed relation with scope (claimed vs evidenced) + evidence
3. Sheaf – corpus-level: stalks, restriction maps, MAP section, frustration
4. Idea – ε-state: consolidated knowledge unit from MAP section

Plus supporting objects (Variant, Stalk, RestrictionEdge, etc.) and their
validators. Each class has .from_dict() (load from JSON) and .to_dict()
(serialize to JSON) methods, plus validation methods to enforce invariants.

Every class has docstrings referencing ARCHITECTURE.md sections.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from abc import ABC, abstractmethod


# ============================================================================
# VARIANT & STALK (Stage 4 concepts)
# ============================================================================

@dataclass
class Variant:
    """One reading of a claim in the hypothesis space.

    A claim's stalk contains the original variant plus any evidence-faithful
    alternatives generated to resolve contradictions with neighboring claims.
    See ARCHITECTURE.md Stage 4: Generate hypothesis-space stalks.
    """
    variant_id: str
    text: str
    rewrite_distance: float  # 0 for #original; 0-1 scale for alternatives
    evidence_faithful: bool
    faithfulness_note: str = ""
    targets: list[str] = field(default_factory=list)  # claim_ids this variant targets
    evidence_strengths_invoked: list[str] = field(default_factory=list)
    evidence_weaknesses_invoked: list[str] = field(default_factory=list)
    extraction: dict[str, Any] = field(default_factory=dict)

    def is_original(self) -> bool:
        return self.variant_id.endswith("#original")

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "text": self.text,
            "rewrite_distance": self.rewrite_distance,
            "evidence_faithful": self.evidence_faithful,
            "faithfulness_note": self.faithfulness_note,
            "targets": self.targets,
            "evidence_strengths_invoked": self.evidence_strengths_invoked,
            "evidence_weaknesses_invoked": self.evidence_weaknesses_invoked,
            "extraction": self.extraction,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Variant:
        return Variant(
            variant_id=d["variant_id"],
            text=d["text"],
            rewrite_distance=d["rewrite_distance"],
            evidence_faithful=d["evidence_faithful"],
            faithfulness_note=d.get("faithfulness_note", ""),
            targets=d.get("targets", []),
            evidence_strengths_invoked=d.get("evidence_strengths_invoked", []),
            evidence_weaknesses_invoked=d.get("evidence_weaknesses_invoked", []),
            extraction=d.get("extraction", {}),
        )


@dataclass
class Stalk:
    """Hypothesis space for one claim.

    Contains the original variant plus any evidence-faithful alternatives.
    See ARCHITECTURE.md Stage 4: Generate hypothesis-space stalks.
    """
    claim_id: str
    variants: list[Variant]

    def validate(self) -> None:
        """Verify stalk invariants."""
        if not self.variants:
            raise ValueError(f"Stalk {self.claim_id} has no variants")
        if not any(v.is_original() for v in self.variants):
            raise ValueError(f"Stalk {self.claim_id} has no #original variant")
        if not self.variants[0].is_original():
            raise ValueError(f"Original variant must be first in {self.claim_id} stalk")
        if not self.variants[0].evidence_faithful:
            raise ValueError(f"Original variant of {self.claim_id} must be evidence_faithful")

    def original_variant(self) -> Variant:
        return self.variants[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "variants": [v.to_dict() for v in self.variants],
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Stalk:
        stalk = Stalk(
            claim_id=d["claim_id"],
            variants=[Variant.from_dict(v) for v in d.get("variants", [])],
        )
        stalk.validate()
        return stalk


# ============================================================================
# CORE OBJECTS: PAPER, CLAIM, SHEAF, IDEA
# ============================================================================

@dataclass
class Paper:
    """A paper as semilattice element + argument DAG.

    The semilattice coordinate describes what the paper studied (physical
    system, phenomena, parameter regime, framework, geometry, measurements,
    model level). The argument DAG records all claims (primary and supporting)
    and their dependencies within the paper.

    See ARCHITECTURE.md Core Objects section.
    """
    paper_id: str
    bibliographic: dict[str, Any]
    observational_ground: dict[str, Any]
    model_level: str
    paper_type: str
    scope_exclusions: list[str] = field(default_factory=list)
    claims_dag: list[dict[str, Any]] = field(default_factory=list)
    extraction: dict[str, Any] = field(default_factory=dict)

    def validate_dag_acyclic(self) -> None:
        """Verify argument DAG is acyclic."""
        deps = {e["claim_id"]: list(e.get("depends_on", [])) for e in self.claims_dag}
        color: dict[str, int] = {cid: 0 for cid in deps}  # 0=white, 1=gray, 2=black

        def visit(cid: str, stack: list[str]) -> None:
            if color[cid] == 2:
                return
            if color[cid] == 1:
                raise ValueError(f"argument DAG has a cycle: {' -> '.join([*stack, cid])}")
            color[cid] = 1
            for dep in deps.get(cid, []):
                if dep not in deps:
                    raise ValueError(f"depends_on references unknown claim_id: {cid} -> {dep}")
                visit(dep, [*stack, cid])
            color[cid] = 2

        for cid in deps:
            visit(cid, [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "bibliographic": self.bibliographic,
            "observational_ground": self.observational_ground,
            "model_level": self.model_level,
            "paper_type": self.paper_type,
            "scope_exclusions": self.scope_exclusions,
            "claims": self.claims_dag,
            "extraction": self.extraction,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Paper:
        paper = Paper(
            paper_id=d["paper_id"],
            bibliographic=d["bibliographic"],
            observational_ground=d["observational_ground"],
            model_level=d["model_level"],
            paper_type=d["paper_type"],
            scope_exclusions=d.get("scope_exclusions", []),
            claims_dag=d.get("claims", []),
            extraction=d.get("extraction", {}),
        )
        paper.validate_dag_acyclic()
        return paper


@dataclass
class Claim:
    """A simple directed relation extracted from a paper.

    Every claim has two scopes (claimed vs evidenced) and an evidence object
    recording type, description, strengths, weaknesses, and optional
    quantitative content. Weaknesses are load-bearing for the alternative-
    generation step.

    See ARCHITECTURE.md Core Objects section.
    """
    claim_id: str
    paper_id: str
    cause: str
    effect: str
    direction: str
    strength: str
    credibility_score: float
    claim_type: str = ""
    scope: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)
    extraction: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, Any] = field(default_factory=dict)  # Added by stage 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "paper_id": self.paper_id,
            "cause": self.cause,
            "effect": self.effect,
            "direction": self.direction,
            "strength": self.strength,
            "credibility_score": self.credibility_score,
            "claim_type": self.claim_type,
            "scope": self.scope,
            "evidence": self.evidence,
            "embedding": self.embedding,
            "extraction": self.extraction,
            "_tags": self.tags,  # Stage 2 adds tags; use _tags key in JSON
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Claim:
        return Claim(
            claim_id=d["claim_id"],
            paper_id=d["paper_id"],
            cause=d["cause"],
            effect=d["effect"],
            direction=d["direction"],
            strength=d["strength"],
            credibility_score=d["credibility_score"],
            claim_type=d.get("claim_type", ""),
            scope=d.get("scope", {}),
            evidence=d.get("evidence", {}),
            embedding=d.get("embedding", []),
            extraction=d.get("extraction", {}),
            tags=d.get("_tags", d.get("tags", {})),  # Try both _tags and tags
        )


# ============================================================================
# RESTRICTION & COMPARABILITY (Stage 3-5 concepts)
# ============================================================================

@dataclass
class VariantPairScore:
    """Compatibility score for a pair of claim variants.

    See ARCHITECTURE.md Stage 5: Score the full compatibility cube.
    """
    variant_a_id: str
    variant_b_id: str
    score: float  # [-1, +1]
    kind: str  # agreement, extension, refinement, qualification, boundary, contradiction
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant_a_id": self.variant_a_id,
            "variant_b_id": self.variant_b_id,
            "score": self.score,
            "kind": self.kind,
            "explanation": self.explanation,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> VariantPairScore:
        return VariantPairScore(
            variant_a_id=d["variant_a_id"],
            variant_b_id=d["variant_b_id"],
            score=d["score"],
            kind=d["kind"],
            explanation=d.get("explanation", ""),
        )


@dataclass
class RestrictionEdge:
    """One edge in the comparability complex.

    Two claims are comparable iff their semilattice coordinates meet
    (regime compatibility) AND their SNAG node lists overlap (mechanism
    compatibility). Each edge records the meet structure and overlap.

    See ARCHITECTURE.md Stage 3: Build the comparability complex.
    """
    edge_id: str
    claim_a: str
    claim_b: str
    semilattice_meet: dict[str, Any]
    snag_overlap: float
    is_comparable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "claim_a": self.claim_a,
            "claim_b": self.claim_b,
            "semilattice_meet": self.semilattice_meet,
            "snag_overlap": self.snag_overlap,
            "is_comparable": self.is_comparable,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> RestrictionEdge:
        return RestrictionEdge(
            edge_id=d["edge_id"],
            claim_a=d["claim_a"],
            claim_b=d["claim_b"],
            semilattice_meet=d.get("semilattice_meet", {}),
            snag_overlap=d.get("snag_overlap", 0),
            is_comparable=d.get("is_comparable", True),
        )


@dataclass
class ComparabilityComplex:
    """The comparability complex: 0-cells are claims, 1-cells are edges.

    This is the nerve of the sheaf. Replaces v1's cosine-similarity
    clustering with a graph that respects semilattice + SNAG structure.

    See ARCHITECTURE.md Stage 3: Build the comparability complex.
    """
    base: list[str]  # claim_ids
    edges: list[RestrictionEdge]

    def validate(self) -> None:
        """Verify complex invariants."""
        base_set = set(self.base)
        for edge in self.edges:
            if edge.claim_a not in base_set or edge.claim_b not in base_set:
                raise ValueError(f"Edge {edge.edge_id} references claims not in base")

    def to_dict(self) -> dict[str, Any]:
        return {
            "base": self.base,
            "edges": [e.to_dict() for e in self.edges],
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> ComparabilityComplex:
        complex_obj = ComparabilityComplex(
            base=d.get("base", []),
            edges=[RestrictionEdge.from_dict(e) for e in d.get("edges", [])],
        )
        complex_obj.validate()
        return complex_obj


@dataclass
class RestrictionMap:
    """A restriction map between two comparable claims.

    Records the semilattice meet, SNAG overlap, and FULL compatibility
    matrix over the two stalks' variants. Storing all variant pairs (not
    just MAP-selected) enables replaying the section at different λ.

    See ARCHITECTURE.md Stage 5: Score the full compatibility cube.
    """
    edge_id: str
    claim_a: str
    claim_b: str
    semilattice_meet: dict[str, Any]
    snag_overlap: float
    restriction_kind: str
    compatibility_scores: list[VariantPairScore]
    extraction: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Verify all expected variant pairs are scored."""
        score_pairs = {(s.variant_a_id, s.variant_b_id) for s in self.compatibility_scores}
        if not score_pairs:
            raise ValueError(f"RestrictionMap {self.edge_id} has no compatibility scores")

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "claim_a": self.claim_a,
            "claim_b": self.claim_b,
            "semilattice_meet": self.semilattice_meet,
            "snag_overlap": self.snag_overlap,
            "restriction_kind": self.restriction_kind,
            "compatibility_scores": [s.to_dict() for s in self.compatibility_scores],
            "extraction": self.extraction,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> RestrictionMap:
        rm = RestrictionMap(
            edge_id=d["edge_id"],
            claim_a=d["claim_a"],
            claim_b=d["claim_b"],
            semilattice_meet=d.get("semilattice_meet", {}),
            snag_overlap=d.get("snag_overlap", 0),
            restriction_kind=d.get("restriction_kind", "symmetric_compatibility"),
            compatibility_scores=[VariantPairScore.from_dict(s) for s in d.get("compatibility_scores", [])],
            extraction=d.get("extraction", {}),
        )
        rm.validate()
        return rm


# ============================================================================
# MAP SECTION & LAMBDA SENSITIVITY (Stage 6 concepts)
# ============================================================================

@dataclass
class MAPSection:
    """The MAP global section: one variant per claim, maximizing coherence - λ*rewrite_cost.

    This is the sheaf's answer – the maximally-consistent reading under
    the evidence-faithfulness constraint.

    See ARCHITECTURE.md Stage 6: MAP global section.
    """
    selected: dict[str, str]  # claim_id -> variant_id
    total_score: float
    coherence: float
    rewrite_cost: float
    lambda_rewrite_penalty: float
    alternative_sections: list[dict[str, Any]] = field(default_factory=list)
    residual_h1: list[dict[str, Any]] = field(default_factory=list)
    solver: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": self.selected,
            "total_score": self.total_score,
            "coherence": self.coherence,
            "rewrite_cost": self.rewrite_cost,
            "lambda_rewrite_penalty": self.lambda_rewrite_penalty,
            "alternative_sections": self.alternative_sections,
            "residual_h1": self.residual_h1,
            "solver": self.solver,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> MAPSection:
        return MAPSection(
            selected=d.get("selected", {}),
            total_score=d.get("total_score", 0),
            coherence=d.get("coherence", 0),
            rewrite_cost=d.get("rewrite_cost", 0),
            lambda_rewrite_penalty=d.get("lambda_rewrite_penalty", 0.4),
            alternative_sections=d.get("alternative_sections", []),
            residual_h1=d.get("residual_h1", []),
            solver=d.get("solver", {}),
        )


@dataclass
class LambdaSensitivity:
    """Lambda sensitivity analysis: how MAP selection varies across λ sweep.

    Identifies claims whose selected variant is stable vs λ-sensitive,
    informing confidence in the selections.

    See ARCHITECTURE.md Stage 6: MAP global section.
    """
    primary_lambda: float
    lambdas: list[float]
    sections: list[dict[str, Any]]
    n_stable_claims: int
    n_sensitive_claims: int
    stable_claims: list[str]
    sensitive_claims: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_lambda": self.primary_lambda,
            "lambdas": self.lambdas,
            "sections": self.sections,
            "n_stable_claims": self.n_stable_claims,
            "n_sensitive_claims": self.n_sensitive_claims,
            "stable_claims": self.stable_claims,
            "sensitive_claims": self.sensitive_claims,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> LambdaSensitivity:
        return LambdaSensitivity(
            primary_lambda=d.get("primary_lambda", 0.4),
            lambdas=d.get("lambdas", []),
            sections=d.get("sections", []),
            n_stable_claims=d.get("n_stable_claims", 0),
            n_sensitive_claims=d.get("n_sensitive_claims", 0),
            stable_claims=d.get("stable_claims", []),
            sensitive_claims=d.get("sensitive_claims", []),
        )


# ============================================================================
# FRUSTRATION (Stage 7 concepts)
# ============================================================================

@dataclass
class Frustration:
    """Penrose-triangle frustration diagnostics on the MAP section.

    Counts triangles where sign(e_ab) × sign(e_ac) × sign(e_bc) < 0,
    indicating structurally inconsistent three-claim configurations.
    ρ = n_penrose / n_signed_triangles is a discrete-H¹ surrogate.

    See ARCHITECTURE.md Stage 7: Frustration diagnostics on the MAP section.
    """
    n_triangles: int
    n_signed_triangles: int
    n_penrose: int
    rho: float
    penrose_triangles: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_triangles": self.n_triangles,
            "n_signed_triangles": self.n_signed_triangles,
            "n_penrose": self.n_penrose,
            "rho": self.rho,
            "penrose_triangles": self.penrose_triangles,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Frustration:
        return Frustration(
            n_triangles=d.get("n_triangles", 0),
            n_signed_triangles=d.get("n_signed_triangles", 0),
            n_penrose=d.get("n_penrose", 0),
            rho=d.get("rho", 0),
            penrose_triangles=d.get("penrose_triangles", []),
        )


# ============================================================================
# SHEAF (Stages 4-7 output)
# ============================================================================

@dataclass
class Sheaf:
    """The sheaf over the corpus's claim base space.

    Records the hypothesis-space stalks per claim, restriction maps
    between comparable claims, the MAP global section, λ sensitivity,
    and frustration diagnostics. One sheaf per corpus; Ideas are
    derived from the MAP section.

    See ARCHITECTURE.md Core Objects section and Stages 4-7.
    """
    sheaf_id: str
    corpus: str
    pipeline_version: str = "v2_paper_as_stalk"
    created_at: str = ""
    base: list[str] = field(default_factory=list)
    stalks: dict[str, Stalk] = field(default_factory=dict)
    restriction_maps: list[RestrictionMap] = field(default_factory=list)
    map_section: MAPSection | None = None
    lambda_sensitivity: LambdaSensitivity | None = None
    frustration: Frustration | None = None
    extraction: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Verify sheaf invariants."""
        if not self.base:
            raise ValueError(f"Sheaf {self.sheaf_id} has empty base")
        if set(self.stalks.keys()) != set(self.base):
            raise ValueError(f"Sheaf {self.sheaf_id}: stalks keys don't match base")
        for stalk in self.stalks.values():
            stalk.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "sheaf_id": self.sheaf_id,
            "corpus": self.corpus,
            "pipeline_version": self.pipeline_version,
            "created_at": self.created_at,
            "base": self.base,
            "stalks": {cid: s.to_dict() for cid, s in self.stalks.items()},
            "restriction_maps": [rm.to_dict() for rm in self.restriction_maps],
            "map_section": self.map_section.to_dict() if self.map_section else None,
            "lambda_sensitivity": self.lambda_sensitivity.to_dict() if self.lambda_sensitivity else None,
            "frustration": self.frustration.to_dict() if self.frustration else None,
            "extraction": self.extraction,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Sheaf:
        sheaf = Sheaf(
            sheaf_id=d["sheaf_id"],
            corpus=d["corpus"],
            pipeline_version=d.get("pipeline_version", "v2_paper_as_stalk"),
            created_at=d.get("created_at", ""),
            base=d.get("base", []),
            stalks={cid: Stalk.from_dict(s) for cid, s in d.get("stalks", {}).items()},
            restriction_maps=[RestrictionMap.from_dict(rm) for rm in d.get("restriction_maps", [])],
            map_section=MAPSection.from_dict(d["map_section"]) if "map_section" in d and d["map_section"] else None,
            lambda_sensitivity=LambdaSensitivity.from_dict(d["lambda_sensitivity"]) if "lambda_sensitivity" in d and d["lambda_sensitivity"] else None,
            frustration=Frustration.from_dict(d["frustration"]) if "frustration" in d and d["frustration"] else None,
            extraction=d.get("extraction", {}),
        )
        sheaf.validate()
        return sheaf


# ============================================================================
# IDEA & EPSILON MACHINE (Stage 8-9 output)
# ============================================================================

@dataclass
class Idea:
    """A consolidated knowledge unit extracted from a sheaf's MAP section.

    An ε-state in the corpus's ε-machine: a set of claims (each with
    MAP-selected variants) that constitute one coherent piece of theory,
    with scope, consensus/frustration metrics, ε-transitions to other Ideas,
    and open questions tied to residual frustration.

    See ARCHITECTURE.md Core Objects section and Stage 8: Consolidate into Ideas.
    """
    idea_id: str
    label: str
    description: str
    sheaf_ref: dict[str, Any]
    contributing_claims: list[dict[str, Any]]
    scope: dict[str, Any]
    consensus: dict[str, Any] = field(default_factory=dict)
    frustration: dict[str, Any] = field(default_factory=dict)
    transitions_out: list[dict[str, Any]] = field(default_factory=list)
    transitions_in: list[dict[str, Any]] = field(default_factory=list)
    open_questions: list[dict[str, Any]] = field(default_factory=list)
    extraction: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Verify Idea invariants."""
        if not self.contributing_claims:
            raise ValueError(f"Idea {self.idea_id} has no contributing claims")
        if len(self.contributing_claims) < 2:
            raise ValueError(f"Idea {self.idea_id} has < 2 claims (min is 2)")

    def to_dict(self) -> dict[str, Any]:
        return {
            "idea_id": self.idea_id,
            "label": self.label,
            "description": self.description,
            "sheaf_ref": self.sheaf_ref,
            "contributing_claims": self.contributing_claims,
            "scope": self.scope,
            "consensus": self.consensus,
            "frustration": self.frustration,
            "transitions_out": self.transitions_out,
            "transitions_in": self.transitions_in,
            "open_questions": self.open_questions,
            "extraction": self.extraction,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Idea:
        idea = Idea(
            idea_id=d["idea_id"],
            label=d["label"],
            description=d["description"],
            sheaf_ref=d.get("sheaf_ref", {}),
            contributing_claims=d.get("contributing_claims", []),
            scope=d.get("scope", {}),
            consensus=d.get("consensus", {}),
            frustration=d.get("frustration", {}),
            transitions_out=d.get("transitions_out", []),
            transitions_in=d.get("transitions_in", []),
            open_questions=d.get("open_questions", []),
            extraction=d.get("extraction", {}),
        )
        idea.validate()
        return idea


@dataclass
class EpsilonMachine:
    """Corpus-level ε-machine metrics over the Idea partition.

    Records state occupancy distribution, statistical complexity Cμ,
    effective state count, and directed transition graph between Ideas.
    The partition is the minimal sufficient statistic of the corpus's
    theoretical content.

    See ARCHITECTURE.md Stage 8: Consolidate into Ideas (ε-machine partition).
    """
    n_states: int
    n_claims: int
    statistical_complexity_bits: float
    normalized_statistical_complexity: float
    effective_states: float
    state_distribution: list[dict[str, Any]]
    transition_graph: dict[str, Any]

    def validate(self) -> None:
        """Verify ε-machine invariants."""
        total_prob = sum(s.get("probability", 0) for s in self.state_distribution)
        if not (0.99 <= total_prob <= 1.01):
            raise ValueError(f"State distribution doesn't sum to 1.0 (sum={total_prob})")

    def to_dict(self) -> dict[str, Any]:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "n_states": self.n_states,
            "n_claims": self.n_claims,
            "statistical_complexity_bits": self.statistical_complexity_bits,
            "normalized_statistical_complexity": self.normalized_statistical_complexity,
            "effective_states": self.effective_states,
            "state_distribution": self.state_distribution,
            "transition_graph": self.transition_graph,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> EpsilonMachine:
        em = EpsilonMachine(
            n_states=d.get("n_states", 0),
            n_claims=d.get("n_claims", 0),
            statistical_complexity_bits=d.get("statistical_complexity_bits", 0),
            normalized_statistical_complexity=d.get("normalized_statistical_complexity", 0),
            effective_states=d.get("effective_states", 0),
            state_distribution=d.get("state_distribution", []),
            transition_graph=d.get("transition_graph", {}),
        )
        em.validate()
        return em
