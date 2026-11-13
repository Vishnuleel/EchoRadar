# Innovation methodology

## What is different

Most recommenders connect companies that look alike. NEXUS looks for companies whose capabilities are
**different and fit together**, then bridges the combination to research, funding and test environments and
writes it up as a hypothesis with its evidence.

Capability discovery → complementarity → opportunity bridge → Innovation Blueprint.

## 1. Capability normalisation

`taxonomy.py` defines 37 capabilities, each with a value-chain role, application domains, and Swedish and English
keyword stems. Free text is mapped by keyword first; user-entered text with no keyword hit falls back to the
nearest capability description in embedding space, and is left un-normalised if nothing is close enough. The
original evidence sentence is always kept.

## 2. Similarity (the baseline)

Cosine similarity between profile embeddings (multilingual MiniLM). Used for the SIMILAR_TO graph edges and as
the baseline in the evaluation. Not used in the recommendation score.

## 3. Complementarity

For companies A and B, every pair of *different* capabilities is checked against:

- 77 explicit capability relations with a written rationale (for example hydroacoustics + subsea cable
  operations: "acoustic survey locates cables and faults before and after installation or repair"), or
- 18 generic role relations (for example sensing → data/AI), weighted at 60% of an explicit relation.

No relation defined means no link: different is not assumed to be complementary. Link strength =
relation weight × shared-application factor (1.0 if the capabilities share an application domain, else 0.4)
× overlap discount (lower when both companies already hold both capabilities) × the weaker evidence
confidence × 1.2 if the domain is a stated priority. A stated interest ("we are looking for X") matched by a
partner's evidenced X is a link of its own.

Pair complementarity = 100 × (0.5·s1 + 0.3·s2 + 0.2·s3) over the three strongest links, each capability used at
most twice. One relationship alone therefore cannot exceed 50.

## 4. Three-company combinations

Eleven application concepts each define capability slots (for example "Autonomous subsea cable inspection":
acoustic sensing, underwater vehicle, cable operations, automated interpretation, data link). For each concept
only the eight companies filling most slots are considered, giving at most 11 × 56 = 616 triples regardless of
membership size. A triad is kept only when every company fills a slot of its own, at least 60% of slots (and
at least three) are covered, and at least two of the three pairs have a complementary link. Uncovered slots are
reported as missing capabilities.

## 5. Opportunity bridge

A combination is represented by the mean embedding of the capabilities it uses (plus its concept). Relevance of
a research record or funding call = 100 × (0.7 × calibrated cosine + 0.3 × capability-tag overlap). Calibration
maps cosine 0.20–0.70 to 0–1 for the semantic model; the bounds were set by looking at the score range on the
stored corpus and are a judgement, not a fitted value. Only calls that are open or upcoming count.

## 6. Ranking

S = 0.35·C + 0.25·O + 0.20·R + 0.20·E, each 0–100.

- O and R take the best three matches (shares 0.6 / 0.25 / 0.15).
- E is the mean quality of the capability claims used: fact with two sources 1.0, one source 0.8,
  user-supplied 0.45, stale source × 0.6, fact without source 0.
- A component with no data counts as 0, is listed as missing, and lowers the displayed data coverage.
- Per company, a hypothesis that brings in a capability the company said it wants gets +8 in that company's own
  list, with the reason shown. The hypothesis score itself does not change.

## 7. Explainability

Each recommendation stores the links (with rationale, strength and the evidence sentence and URL on both sides),
the slot assignment, missing slots, the matched research and calls, the verification result and a list of
uncertainties. The Blueprint page renders all of it.

## 8. Measured comparison with the baseline

36 company pairs labelled 0–2 for complementarity (`data/eval/labelled_pairs.json`), 26 of them labelled
complementary. Measured on the shipped database:

| Metric | NEXUS complementarity | Similarity baseline |
|---|---|---|
| Precision@5 | 1.00 | 0.40 |
| Precision@10 | 0.90 | 0.60 |
| Recall@10 | 0.35 | 0.23 |
| nDCG@10 | 0.77 | 0.37 |
| Mean label of top 5 (0–2) | 1.6 | 0.6 |
| Spearman with labels | 0.72 | 0.04 |

**How much weight this carries:** the labels were written by the development team, who also wrote the relation
table, so the comparison favours NEXUS by construction. 36 pairs is too few for statistical conclusions. It
shows the engine does what it was designed to do, not that the design is right. Independent labels from Blue
Science Park staff are the next step. Visible errors: Knowit / HiQ (two similar consultancies, labelled 0) scores
48; two pairs labelled plausible score 0.
