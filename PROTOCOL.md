# Cognitive Contract Protocol (CCP) v1.0

## Specification

This is the **protocol specification**. It defines the rules for verifiable knowledge transfer between AI sessions. It does not prescribe any specific implementation language or platform.

Any system that implements these rules is a valid CCP node.

---

## 1. Token Format

A valid token is a logical record containing:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `protocol` | string | yes | Protocol version: `"cognicontract/v1"` |
| `token_id` | string | yes | Unique identifier for this token |
| `content` | string | yes | The knowledge claim being anchored |
| `axiom_transparency` | string[] | yes | Underlying assumptions this claim depends on |
| `counter_examples` | string[] | yes | Conditions under which this claim may fail |
| `derivation` | string[] | yes | Step-by-step reasoning chain |
| `confidence` | number | yes | Self-assessed reliability ∈ [0, 1] |
| `anchor_time` | string | yes | ISO 8601 timestamp of anchoring |

### Encoding

The canonical encoding is JSON with UTF-8. Implementations may use any encoding as long as field semantics are preserved. The JSON encoding specified here is the **reference encoding**, not a requirement.

---

## 2. Invariants

All token validators MUST enforce these rules. Violation = rejection.

| # | Rule | Description |
|---|------|-------------|
| I1 | `confidence ∈ [0, 1]` | Numeric range check |
| I2 | `axiom_transparency` non-empty | Every token must declare its assumptions |
| I3 | `counter_examples` non-empty | Every token must acknowledge its limits |
| I4 | `derivation` length ≥ 1 | Anchoring requires a reasoning path |
| I5 | No self-reference | Content must not be identical to any axiom |
| I6 | DAG cycle-free | Token dependency graph must be acyclic |

---

## 3. Derivation Chain Enforcement

Every step in `derivation` MUST anchor to one of:

| Anchor | Meaning | Detection |
|--------|---------|-----------|
| **ROOT** | References the token's own axioms | Step text contains terms from at least one axiom |
| **CHAIN** | References a previous step | Step text contains terms from an earlier derivation step |
| **SOURCE** | References external knowledge | Step contains a citation marker (URL, DOI, KB identifier, etc.) |

A step with zero anchors = invalid token. The detection method is implementation-defined; the reference implementation uses bilingual n-gram matching.

---

## 4. Arbitration Rules

When multiple tokens exist on related topics:

| Rule | Priority |
|------|----------|
| Human-anchored tokens take precedence over AI-derived tokens | Highest |
| Tokens with longer derivation chains are preferred | High |
| Tokens with higher confidence are preferred (after L3 adjustments) | Medium |
| Newer tokens may supersede older tokens (via `/supersede`) | Context-dependent |
| Contradictory tokens both retained with a warning, human review recommended | Default |

### Auto-weight adjustments

Implementations MAY apply automatic confidence adjustments:

| Condition | Adjustment |
|-----------|-----------|
| Derivation with ≤1 step and no human-anchor marker | × 0.7 |
| Counter-examples containing unverified markers | × 0.85 |
| Adjustments are cumulative where applicable | |

---

## 5. Consensus Protocol

Knowledge is anchored through a three-round confirmation:

```
Round 1: Proposer states a knowledge claim
Round 2: Second party confirms, challenges, or modifies
Round 3: Proposer confirms the final version
```

A token is **human-anchored** if at minimum one party uses a cryptographic identity (see Ratify protocol for recommended signature format).

---

## 6. Node Interface

A CCP-compatible node SHOULD expose:

| Endpoint | Purpose |
|----------|---------|
| `anchor(token)` | Submit a token for validation and storage |
| `retrieve(id)` | Fetch a specific token |
| `list()` | List all tokens (or an index) |
| `verify(claim)` | Check if a claim is consistent with anchored tokens |
| `export()` | Export all tokens as a portable context block |

The Python reference implementation at `token_server.py` exposes these via HTTP on port 8741.

---

## 7. Reference Implementation

This repository includes a Python/Flask reference implementation (`token_server.py`).

**Do not confuse the reference implementation with the protocol.**

Anyone may implement CCP in any language. The only requirement is adherence to Sections 1-5 of this specification.

---

## Version

v1.0, June 2026
