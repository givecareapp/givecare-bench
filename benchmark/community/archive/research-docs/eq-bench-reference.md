# EQ-Bench Reference

SupportBench draws inspiration from EQ-Bench's multi-turn evaluation approach for emotional intelligence assessment.

## External Resources

- **Website**: https://eqbench.com
- **GitHub**: https://github.com/EQ-bench/EQ-Bench
- **Leaderboard**: https://eqbench.com/leaderboard.html
- **Paper**: [EQ-Bench: An Emotional Intelligence Benchmark for Large Language Models](https://arxiv.org/abs/2312.06281)

## Key Concepts Adapted for SupportBench

### Multi-Turn Conversation Evaluation
- EQ-Bench pioneered 3-turn conversation assessment
- SupportBench extends this to 3-20+ turns for caregiving relationships
- Focus shifts from general EQ to longitudinal safety in care contexts

### Emotional Intelligence Measurement
- EQ-Bench measures empathetic response quality and emotional understanding
- SupportBench adapts these principles to trauma-informed care evaluation
- Added dimensions: crisis safety, regulatory compliance, cultural fitness

### Pairwise Judging Methodology
- EQ-Bench uses Elo scoring with pairwise comparisons
- SupportBench uses tri-judge ensemble with dimension-specific rubrics
- Both approaches reduce single-judge bias

## Integration Notes

See `docs/eqbench.md` for detailed integration analysis and comparison methodology.

## Historical Context

Previous versions of this repository included full clones of:
- `EQ-bench-site-main/` (website source code)
- `eqbench3-main/` (benchmark implementation)

These have been removed to reduce repository size (2.6GB → <10MB). All content is available at the official EQ-Bench repository.
