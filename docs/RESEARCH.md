# Research grounding

Why the design looks the way it does. Each cluster below ends with the design implication it
produced. This is a curated set, not exhaustive. The full reference list lives in the uploaded
Consensus report and Patrick's Consensus search thread.

Treat the recency of much of this evidence as a caveat: a lot of the AI-specific work is from
2025 and 2026, and several items are single studies or preprints. The direction is trustworthy
because many independent lines converge, but hold any single claim loosely.

---

## 1. Process beats participants

The strongest and most repeated finding across the small-group discourse literature: outcomes
depend less on who is in the group than on how ideas are introduced, taken up, challenged, and
coordinated.

- Barron, "When Smart Groups Fail" (2003). Neither prior achievement nor even generating the
  correct idea predicted success. What predicted it was partner responsiveness and whether
  proposals connected to what came before. Weak groups ignored or rejected correct proposals
  and ran incoherent conversations. https://consensus.app/papers/details/d5e029a59a195c2c8a5652485588d68e/
- Cavagnetto et al. (2022). Group performance tracked the immediate accuracy of the actual
  conversation, not the group's overall ability. https://consensus.app/papers/details/87e9cc36deba5865874d5504ff08e044/
- Barron, "Achieving Coordination" (2000). Good groups showed mutuality of exchange, joint
  attention, and goal alignment. https://consensus.app/papers/details/8e9c3f8c4ffd502ea74e7b5452c29579/

**Design implication:** the value is in the interaction, so the engine's job is to enforce good
interaction. This is the origin of the uptake rule.

---

## 2. Uptake is the highest-leverage lever

The consistent separator of strong from weak discussion is uptake: whether a point gets engaged,
connected to, and built on, versus ignored or waved through.

- Soter et al. (2008). The richest reasoning appeared with open-ended, authentic questions, a
  high degree of uptake, and a critical-analytic rather than merely expressive stance.
  https://consensus.app/papers/details/dde241c92ade5cfc8bd3d943f345e619/

**Design implication:** every turn must take up a specific prior point and steelman, extend, or
rebut it. This is the single rule the whole protocol is built around, and it doubles as the
defense against sycophancy and mode collapse.

---

## 3. A non-contributing facilitator improves reasoning

- Hogan et al. (1999). A facilitator acting as a catalyst, prompting people to expand and clarify
  without supplying content, produced higher-level reasoning. But guided discussion, while higher
  in reasoning, was less generative and exploratory than unguided peer discussion.
  https://consensus.app/papers/details/616d70f4000559e285202615397691bf/
- Kuhn et al. (2020). Talk about the group's process, not about individuals, correlated with better
  outcomes. https://consensus.app/papers/details/80acee8253e252438e07a252d7d69243/
- Cohen, "Restructuring the Classroom" (1994). Structure that helps routine tasks can constrain the
  open discussion needed for ill-structured, conceptual ones.
  https://consensus.app/papers/details/b4283cbfe9405d6db0a09ef84cdccc17/

**Design implication:** the conductor contributes no content (so it cannot anchor) and manages
process, but its touch varies by phase, light during divergence, firm during critique.

---

## 4. Do not force consensus, and do not rigidly defer all evaluation

- Harvey and Kou, "Collective Engagement in Creative Tasks" (2013). Groups that began by evaluating
  a small set of ideas were not less creative; evaluation itself acted as a generative force.
  This challenges the strict "generate everything first, judge later" orthodoxy.
  https://consensus.app/papers/details/35ec3593a9be590ab24a3316c19a62b5/
- Viduchinsky et al. (2026). An AI that debated and challenged users' rankings raised creative
  self-efficacy and led users to reconsider without blindly deferring. https://doi.org/10.1145/3816046.3816266
- Miron-Spektor et al. (2022). Teams became more creative when they reconciled competing demands
  through elaboration rather than settling on compromise too early. https://doi.org/10.1016/j.obhdp.2022.104153

**Design implication:** independent takes first (to prevent anchoring), but interleaving critique
with generation is allowed rather than forbidden. The terminal output is a disagreement map, never
a synthesized verdict.

---

## 5. Role differentiation and distinct dispositions

- Belbin, Management Teams (1981). Empirically derived team roles, grouped into thinking, action,
  and people functions. High-performing teams cover all functions; role collisions (two of the same
  type) are predictable. Validity of the specific taxonomy is mixed, so use it as a vocabulary of
  function, not proven fact.
- de Bono, Six Thinking Hats (1985). A depersonalized set of thinking modes (facts, benefits, risks,
  creativity, feeling, and process control) that a group wears one at a time. Designed as functions,
  not personalities, which is why it maps cleanly onto assignable model roles. The "blue hat"
  (process control) is the conductor.
- Siemon (2022). Team roles for AI teammates, for example coordinator, creator, perfectionist, doer.
  https://doi.org/10.1007/s10726-022-09792-z
- Rezwana and Maher (2022), COFI framework. Distinguishes "pleasing" agents that follow the user from
  "provoking" agents that deliberately offer dissimilar contributions; both are useful.
  https://doi.org/10.1145/3519026

**Design implication:** distinct seats with stable functions, run on different underlying models,
plus a minimal role set of reframer, generator/explorer, and skeptic/evaluator.

---

## 6. Turn-taking, oscillation, and the balance of influence

- Woolley et al. (2010), collective intelligence. Group performance correlated with the average
  social sensitivity of members and the equality of conversational turn-taking, not with individual
  IQ. Caveat: Bates and Gupta (2017), "Smart groups of smart people," failed to reproduce the
  turn-taking effect and found individual ability explained most of the variance. So treat equal
  turn-taking as a sensible default, not a law.
- Lu et al. (2020). Turn-taking improved uniqueness and perspective-taking in group creativity tasks.
  https://doi.org/10.1016/j.neuroimage.2020.117025
- Korde and Paulus (2017). Alternating individual and group phases outperformed either alone.
  https://doi.org/10.1016/j.jesp.2016.11.002
- Wilson et al. (2020). Diverse teams became more creative by alternating divergence and integration
  rather than mixing both at once. https://doi.org/10.1177/0021886320960245

**Design implication:** sequential turns with visible role labels and explicit handoffs, an
oscillatory expand/stress-test rhythm, and anti-dominance balancing by the conductor.

---

## 7. The Goldilocks limit: too much AI backfires

- Huang (2025). A curvilinear effect: some AI input helps, too much reduces creativity gains.
  https://doi.org/10.1037/xge0001838
- Multiple studies report overreliance, fixation, narrowed divergence, premature convergence, and
  weakened intrinsic motivation when AI becomes too directive (Rahman et al. 2025; Wadinambiarachchi
  et al. 2024; Wu et al. 2025).
- McGuire et al. (2024). Co-creation preserves creativity and self-efficacy better than editing
  AI-produced drafts. https://doi.org/10.1038/s41598-024-69423-2

**Design implication:** keep the user in control and the human-element layer optional. This is also
why option (b) is the spine and option (a) is a switchable flavor.

---

## 8. The creativity technique library (for the intervention layer)

These are the executable methods to add as pluggable moves later.

- Gu et al. (2022). Random connection improved fluency and flexibility, schema violation improved
  flexibility, and SCAMPER improved originality, while simple ideation alone did not help much.
  https://doi.org/10.1002/jocb.531
- Chan et al. (2011). Far-field, less-common analogies improve novelty in ideation.
  https://doi.org/10.1115/1.4004396
- Wigert et al. (2022). Following divergent exploration with convergent problem construction produces
  more creative solutions than divergence alone. https://doi.org/10.1037/aca0000513
- Komura and Yamada (2026). A deepening strategy outperformed diversification in trust and adoption.
  https://doi.org/10.1371/journal.pone.0340449
- Wise and Kenett (2024). Word recommendations that pull a user out of a stuck semantic region change
  fluency and originality. https://doi.org/10.3758/s13428-024-02463-8

**Design implication:** these become the `moves` in section 6 of DESIGN.md, attached to seats or fired
by conductor hooks such as `on_user_stall` and `on_early_narrowing`.

---

## 9. Multi-agent framing and the shift to interaction design

- Lin et al. (2025). Survey of creativity in LLM-based multi-agent systems.
  https://doi.org/10.18653/v1/2025.emnlp-main.1403
- Lim et al. (2026). Human and multi-agent team formation; users deliberately diversify personas,
  sometimes inventing extreme ones, to broaden idea directions. https://doi.org/10.1145/3772318.3791166
- Rosenbaum et al. (2025). Divergent versus convergent LLM personas are best made explicit and
  switchable rather than hidden in one generic assistant. https://doi.org/10.48550/arxiv.2510.26490
- Heyman et al. (2024), Supermind Ideator. Structured scaffolds for creative problem-solving
  outperform plain ChatGPT and solo work. https://doi.org/10.1145/3643562.3672611

**The headline shift in the evidence:** creative support is moving from raw idea generation to
interaction design. How the system questions, challenges, sequences, and yields control matters at
least as much as raw model quality. That is the whole thesis of this project.

---

## Frameworks and article referenced in the design conversation

- Belbin, R. M. (1981). Management Teams: Why They Succeed or Fail.
- de Bono, E. (1985). Six Thinking Hats.
- Toegel, I. and Barsoux, J.-L. (2026). A New Way to Address Troubled Team Dynamics. MIT Sloan
  Management Review.
- Woolley, A. W. et al. (2010). Evidence for a Collective Intelligence Factor in the Performance of
  Human Groups. Science.
- Bates, T. C. and Gupta, S. (2017). Smart groups of smart people (the replication caveat). Intelligence.
