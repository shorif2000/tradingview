# CLAUDE.md

Guidance for Claude Code (claude.ai/code) and any other agent working in this
repository.

**See [AGENTS.md](AGENTS.md).** It is the single context document for this repo:
architecture, the 18 numbered invariants and the failure each one prevents, the
measured results, the approaches that were tested and failed, and the commands.

This file is deliberately a pointer rather than a copy. Two context documents
covering the same ground drift apart, and the one that drifts is the one that
misleads the next agent.

## The three things worth knowing before touching anything

1. **`pine/XAU_Regime_Scalper_INDICATOR.pine` is the only hand-edited Pine file.**
   The strategy and all four variants are generated from it. Edit a generated file
   and the edit is silently lost on the next `gen_strategy.py` / `gen_variants.py`
   run.

2. **`python3 backtester/validate.py` must pass (32/32) before any commit**, and
   `python3 backtester/final_report.py` must still reproduce
   `149 trades | 44.3% WR | +0.291R`. If those numbers move, behaviour changed.

3. **Justify any change against both real samples in `data/`, not one.** The bar
   used throughout this project is "opposite market direction, same sign of
   result" — a parameter that scores well in one period and inverts in the other
   is exactly what a spurious pattern looks like, and several plausible ideas here
   died that way.
