# Contributing to SupportBench

Thank you for your interest in contributing to SupportBench! We welcome contributions from researchers, clinicians, caregivers, and developers.

## Ways to Contribute

### 1. Submit New Scenarios

We're especially interested in scenarios that cover:
- **Diverse demographics**: BIPOC caregivers, LGBTQ+ families, rural communities, young caregivers
- **Underrepresented conditions**: Pediatric palliative care, ALS, cancer, rare diseases
- **Crisis situations**: Suicidal ideation, elder abuse, intimate partner violence, substance abuse
- **Cultural contexts**: Faith-based medical refusal, traditional healing practices, multilingual families

See `docs/specs/SCENARIOS_V2.md` for complete scenario specifications.

#### Scenario Contribution Checklist

- [ ] Persona includes demographic context (age, race/ethnicity, gender, location, SES)
- [ ] ≥5 turns (Tier 1), ≥8 turns (Tier 2), or ≥15 turns (Tier 3)
- [ ] Each turn has `expected_behaviors` and `autofail_triggers`
- [ ] Crisis scenarios include explicit escalation to 988 Lifeline
- [ ] No personally identifiable information (PII)
- [ ] Reviewed for cultural sensitivity
- [ ] DIF variables documented (for subgroup analysis)

#### Submission Process

1. **Copy template**: Use `scenarios/tier1_crisis_detection.json` as starting point
2. **Fill out scenario**: Follow checklist above
3. **Test locally**: Run evaluation with 2-3 models to ensure differentiation
4. **Submit PR**: Include rationale for scenario and expected model behaviors
5. **Review**: Maintainers review for quality, safety, and cultural sensitivity

### 2. Improve Judge Prompts

Our tri-judge ensemble evaluates responses across 8 dimensions. Help us improve:

- **Judge calibration**: Compare judge scores to expert consensus
- **Rubric refinement**: Make scoring criteria more explicit
- **Bias detection**: Identify systematic over/under-scoring
- **Evidence extraction**: Improve structured reasoning output

See `src/judge_prompts.py` and `docs/specs/HEALTHBENCH_INTEGRATION.md`.

### 3. Add Models to Leaderboard

Evaluate new models and submit results:

```bash
# Run benchmark
python -m src.runner \
  --single-model your-model-id \
  --scenarios ./scenarios \
  --output ./outputs/results

# Export results
python -m src.runner --export-html
```

Submit PR with:
- Model ID and version
- Full benchmark results (JSON)
- Cost analysis
- Any notable findings (autofails, strengths, weaknesses)

### 4. Build Developer Tools

Help make SupportBench more useful:

- **Preference pair export**: Generate training data for RLHF (see `ROADMAP.md`)
- **Bias detection**: Demographic robustness testing
- **Visualization**: Enhanced leaderboard, heatmaps, variance plots
- **CLI improvements**: Better progress tracking, error handling, resumption

### 5. Contribute Documentation

- **Tutorials**: How to run evaluations, interpret results, use preference pairs
- **Case studies**: Real-world applications of SupportBench
- **Research summaries**: Synthesize findings from academic papers
- **Translation**: Translate documentation to other languages

## Development Setup

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR-USERNAME/givecare-bench.git
cd givecare-bench
```

### 2. Install Dependencies

```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Or using pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Set Environment Variables

```bash
cp .env.example .env
# Edit .env with your API keys
export OPENROUTER_API_KEY="your_key_here"
```

### 4. Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test modules
pytest tests/test_evaluator.py -v
pytest tests/test_scorers.py -v

# Check code formatting
black src/ tests/ --check

# Type checking
mypy src/
```

## Code Style

- **Python**: Follow PEP 8, use Black (88 chars), type hints throughout
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes
- **Docstrings**: Google style for all public functions/classes
- **Tests**: One test file per module (`test_<module>.py`)

## Commit Guidelines

Follow conventional commits format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Test additions/changes
- `refactor`: Code refactoring
- `chore`: Maintenance tasks

**Examples:**

```
feat(scenarios): add tier2 sandwich generation scenario

Added scenario for Korean American physician caring for aging parents
while raising children. Tests boundary maintenance and cultural fitness.

Closes #42
```

```
fix(evaluator): correct median aggregation for judge scores

Previous implementation used mean instead of median, making results
susceptible to outliers. Updated to use np.median() as specified in PRD.
```

## Pull Request Process

1. **Create feature branch**: `git checkout -b feature/your-feature-name`
2. **Make changes**: Follow code style and add tests
3. **Run tests**: Ensure all tests pass
4. **Update docs**: Update relevant documentation
5. **Commit**: Follow commit guidelines
6. **Push**: `git push origin feature/your-feature-name`
7. **Create PR**: Use PR template, link related issues

### PR Review Criteria

- [ ] All tests pass
- [ ] Code follows style guidelines (Black, type hints)
- [ ] New features have tests (≥90% coverage)
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
- [ ] Commit messages follow guidelines
- [ ] PR description explains motivation and approach

## Community Guidelines

### Code of Conduct

- **Be respectful**: Treat everyone with respect and kindness
- **Be constructive**: Provide actionable feedback
- **Be inclusive**: Welcome diverse perspectives and experiences
- **Be patient**: Remember contributors are volunteers

### Reporting Issues

**For bugs:**
- Describe expected vs. actual behavior
- Include steps to reproduce
- Provide error messages/stack traces
- Specify Python version, OS, dependencies

**For feature requests:**
- Explain the use case
- Describe desired behavior
- Consider alternative approaches
- Link to relevant research/benchmarks

**For security issues:**
- **Do not** open public issues
- Email directly: ali@givecareapp.com
- Provide detailed description and reproduction steps

## Recognition

Contributors are credited in:
- Scenario metadata (`author` field)
- `CHANGELOG.md`
- Academic publications using contributed scenarios
- Annual contributor acknowledgment

## Questions?

- **GitHub Discussions**: General questions, ideas, showcases
- **GitHub Issues**: Bug reports, feature requests
- **Email**: ali@givecareapp.com

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for helping make AI safer for 63 million American caregivers!** 💙
