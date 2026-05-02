You are generating alternative readings of a contested scientific claim. The claim, as originally stated, contradicts (or fits poorly with) one or more neighbor claims in the corpus. Your job: produce 1–3 evidence-faithful rewrites of THIS claim that re-scope it to remove the conflict, by invoking specific weaknesses the paper itself acknowledges.

# What you'll receive

- **The claim being rewritten** — full record, including `cause`, `effect`, `direction`, `scope.claimed`, `scope.evidenced`, and the load-bearing `evidence.strengths` and `evidence.weaknesses` lists.
- **One or more contested neighbors** — for each, the neighbor's claim record plus the compatibility score and prose explanation of why the original conflicts with it.

# Hard constraints

Each alternative MUST satisfy ALL of these:

1. **Be evidence-faithful.** Do not invent new evidence. A rewrite narrows or qualifies the claim's scope; it does not change what the data shows.
2. **Invoke specific weaknesses from `evidence.weaknesses`.** Every rewrite that narrows scope must cite, by quoting verbatim into `evidence_weaknesses_invoked`, the entries it leans on. A rewrite without weakness-grounding is hand-waving — return `evidence_faithful: false` if you can't justify it from a stated weakness.
3. **Preserve strengths.** A rewrite must not silently discard a strength the paper actually established. List preserved strengths verbatim in `evidence_strengths_invoked`.
4. **Target specific failing neighbors.** Each alternative says which neighbor `claim_id`s it was generated to satisfy.

# Output format

Return ONLY a single JSON object. No prose preamble, no markdown fencing.

```json
{
  "alternatives": [
    {
      "variant_id": "<claim_id>#alt_<short_snake_case_descriptor>",
      "text": "<the rewritten claim, in cause/direction/effect form>",
      "rewrite_distance": <number in [0, 1]>,
      "targets": ["<neighbor_claim_id>", ...],
      "evidence_strengths_invoked": ["<verbatim strength entry>", ...],
      "evidence_weaknesses_invoked": ["<verbatim weakness entry>", ...],
      "evidence_faithful": <bool>,
      "faithfulness_note": "<2-3 sentences explaining why this rewrite is evidence-faithful, citing the specific weaknesses being invoked>"
    }
  ]
}
```

# Rewrite distance scale

- 0.0 — the original (do NOT return this; it's already in the stalk)
- 0.1 to 0.3 — minor scope narrowings, boundary qualifications, stylistic softenings
- 0.4 to 0.6 — replace or drop a quantitative commitment; reinterpret a single claim element
- 0.7 to 1.0 — reinterpret the claim's mechanism or demote a causal claim to correlational

# Strategy

- **Aim for the SOFTEST rewrite that resolves the conflict.** The downstream MAP optimizer penalizes rewrite distance, so over-rewriting wastes budget. A 0.2-distance rewrite that satisfies the neighbor beats a 0.6-distance one that satisfies it more thoroughly.
- **Consolidate alternatives across neighbors.** If a single rewrite satisfies multiple contested neighbors, list all of them in `targets` — don't generate near-duplicates.
- **Generate 1 alternative if a single softening suffices.** Generate 2-3 if there are genuinely different reasonable readings (e.g. "narrow scope to small-amplitude" vs "demote causal to correlational"). Never more than 3.
- **Don't use `"original"` as the descriptor.** `#original` is reserved for the unmodified statement.
- **The `text` field is the variant's restated claim** in natural-language cause/direction/effect form, narrowed to the regime the variant supports. E.g. "0.1 k V_A correlates with m=1 quiescence in the ZaP parameter window (uniform-shear idealization); not a general threshold."

# When NOT to generate

If the original ALREADY restricts compatibly into all contested neighbors when the meet regime is honored — i.e. if the contestation is a measurement quirk rather than a real disagreement — return `{"alternatives": []}`. The original stays as a singleton stalk. This is fine.
