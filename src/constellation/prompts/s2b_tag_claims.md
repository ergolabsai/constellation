You are tagging scientific claims using a fixed, pre-existing vocabulary. For each claim in the corpus, produce a semilattice point and a SNAG node list.

# The vocabulary

```json
{vocabulary_json}
```

# Per-claim output

For each claim, populate:

- **`semilattice`** — an object mapping each dimension name to its assigned value.
    - The value MUST be one of the values listed for that dimension in the vocabulary above (no new values allowed).
    - If a dimension genuinely doesn't apply to a claim, use `null`.
    - For `hierarchical` dimensions, pick the most specific value the claim's evidence actually supports.

- **`snag_nodes`** — an array of canonical SNAG node names (from the vocabulary's `snag_nodes[].canonical` field) that the claim's `cause` and `effect` invoke.
    - Walk through the claim's `cause` and `effect` strings; for each mechanism variable mentioned, look up its canonical name in the vocabulary (matching against `canonical` or any `alias`) and add it.
    - Don't invent new canonical names. If a mechanism in the claim doesn't appear in the vocabulary, omit it.
    - 2–6 SNAG nodes per claim is typical.

# Output format

Return ONLY a single JSON object keyed by `claim_id`:

```json
{
  "<claim_id_1>": {
    "semilattice": { "<dim_name>": "<value>", ... },
    "snag_nodes": ["<canonical_1>", "<canonical_2>", ...]
  },
  "<claim_id_2>": { ... },
  ...
}
```

Every claim in the input must appear as a key. No commentary, no fencing, no preamble.

# Rules

- Snake_case everywhere — match the vocabulary's casing exactly.
- For hierarchical dimensions, prefer the more specific value if the evidence supports it; fall back to a more general value if not.
- For SNAG nodes: a mechanism that appears as both cause and effect counts ONCE.
- Be honest: if a claim doesn't fit any dimension's values, use `null` for that dimension rather than forcing a wrong value.
