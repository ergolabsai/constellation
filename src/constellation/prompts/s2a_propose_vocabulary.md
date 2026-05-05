You are designing a tag vocabulary for a corpus of scientific claims. The vocabulary will be used by a downstream stage to compute "comparability" between claims — two claims are comparable if their tags overlap in specific ways. The vocabulary you produce here will be re-used as the controlled vocabulary for tagging every claim in this corpus.

# What the vocabulary contains

Two parts:

## 1. Semilattice dimensions

A small number (typically 4–8) of fixed dimensions. Each dimension is one axis along which claims can be compared. For each dimension, specify:

- `name` — short snake_case identifier, e.g. `"mode"`, `"physics_framework"`.
- `description` — one sentence explaining what this dimension captures.
- `values` — array of allowed string values (snake_case, lowercase, terse). 5–15 per dimension is typical. **Always include this field**, even for hierarchical dimensions where the values also appear as `hierarchy` keys.
- `ordering` — one of:
    - `"discrete"` — values are unrelated labels; meet exists only if both claims have the EXACT same value.
    - `"hierarchical"` — values form a partial order (chain or tree); meet is the more general (lower) value when one is an ancestor of the other. If you choose this, also include a `hierarchy` field — see below.
    - `"set_inclusion"` — value is itself a set (rare; use only if a single claim genuinely lives at multiple values).
- `hierarchy` (only when `ordering = "hierarchical"`) — a JSON object mapping each value to its DIRECT parent (or `null` for root values). Multiple roots OK.
- `wildcards` (optional, any ordering) — a list of values that are "compatible with all" — i.e. when computing the meet between this value and any other value, the meet exists and equals the other side. Use this for values that don't commit to a position in the hierarchy. **Critical example:** for a `physics_framework` dimension, `experimental` is a wildcard — an experimental observation does not commit to a particular model and should be comparable with claims at any model level. Similarly, `generic` profile values, or `unspecified`-style "doesn't commit" values, are usually wildcards. If you don't add wildcards where appropriate, downstream stages will fail to compare claims that should be compared.

Examples of dimensions that often appear (use as inspiration; tailor to THIS corpus):

- `mode` — which instability/wave/mode is studied. Discrete.
- `physics_framework` — modeling fidelity. Hierarchical, e.g. `ideal_mhd → resistive_mhd → two_fluid → gyrokinetic → fully_kinetic`. **`experimental` should be a `wildcards` entry** so it's comparable with any model level (an experiment doesn't commit to a model).
- `geometry` — spatial configuration. Discrete or hierarchical.
- `wavelength_regime` — discrete: `long_wavelength`, `intermediate`, `flr_scale`, `short_wavelength`.
- `scope` — generality: `universal`, `domain_specific`, `case_specific`. Hierarchical.

DO NOT just copy these — propose dimensions that the corpus you're given actually exhibits. If the corpus has no claims about geometry, don't include a geometry dimension.

## 2. SNAG node vocabulary

A list of canonical mechanism variables that appear in claims' cause/effect descriptions. SNAG nodes are the "vertices" of the implicit causal/structural network running through the corpus. For each entry:

- `canonical` — short snake_case canonical name, e.g. `"flow_shear"`, `"flr_cutoff"`, `"alfven_speed"`.
- `aliases` — array of alternate phrasings the claims actually use, e.g. `["dV_z/dr", "axial flow shear", "shear strength"]`.
- `description` (optional, ≤ 100 char) — one-line gloss when the canonical name isn't self-explanatory.

Aim for 15–40 SNAG nodes for a corpus of ~30–50 claims. Include any mechanism variable that appears in at least 2 claims; merge synonyms aggressively.

# Output

Return ONLY a single JSON object with this shape:

```json
{
  "domain": "<short prose description of the domain, ≤ 80 chars>",
  "rationale": "<2-3 sentence prose: why these dimensions / what corpus structure they capture>",
  "semilattice_dimensions": [ ... ],
  "snag_nodes": [ ... ]
}
```

No commentary, no markdown fencing, no preamble. The object must be valid JSON.

# Guidelines

- Don't over-fit. If a dimension would only apply to 1–2 claims, drop it.
- Prefer fewer, sharper dimensions over many fuzzy ones.
- For `physics_framework`-like hierarchical dimensions, the partial order matters: getting the chain right is what enables the meet computation downstream.
- Snake_case everywhere.
- The corpus content (papers + claims) is in the user message. Read it carefully before proposing.

# What dimensions to AVOID

- **Methodology / provenance dimensions** (e.g. "claim_character", "evidence_type", "extraction_method"). Comparability is about REGIME and MECHANISM — not about how a claim was established. Two claims about the same physics should be comparable whether one was derived analytically and the other measured experimentally. Provenance is already captured in `paper.paper_type` and `claim.evidence.type` and is NOT a comparability axis.
- **Free-text descriptive dimensions** with too many values to enumerate. If you can't list a closed set of 3–15 values, the dimension is the wrong shape.
- **Highly correlated dimensions** that essentially restate `instability_mode` or `physics_framework`. If two dimensions always co-vary, collapse them.
