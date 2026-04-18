# DESIGN.md — general reference and usage standard

## Why this page exists

This page treats `DESIGN.md` as a **general, reusable spec format** for
AI-assisted product and UI work.

It is not specific to GiveCare.
It is meant to capture the standard itself:

- what `DESIGN.md` is
- what problem it solves
- how it should relate to `AGENTS.md`
- what a strong `DESIGN.md` should contain
- how teams should use it as a living design spec

## Primary references

### Official concept / format
- Stitch overview: `https://stitch.withgoogle.com/docs/design-md/overview`
- Stitch format docs: `https://stitch.withgoogle.com/docs/design-md/format`

### Practical example catalog
- `VoltAgent/awesome-design-md`
- especially the README and example files as a practical catalog of structure and usage patterns

## What DESIGN.md is

`DESIGN.md` is a markdown-based design system spec for humans and LLMs.

Its purpose is to define:

- the visual language of a product
- the rules for color, typography, spacing, and depth
- the preferred styling of common components
- the responsive and interaction behavior that should remain consistent
- the design guardrails an agent should follow while generating UI

The core idea is simple:

> just as `AGENTS.md` tells an agent how to work in a repo,
> `DESIGN.md` tells an agent how the product should look and feel.

## The problem DESIGN.md solves

Without a usable text spec, teams often have a gap between:

- high-level aesthetic intent
- actual implementation detail
- AI-generated UI quality

That usually creates one of two failures:

1. the design guidance is too vague
   - "modern"
   - "premium"
   - "clean"
   - "Apple-like"

2. the design guidance exists only in tools or artifacts that are awkward for LLMs to use directly
   - screenshots
   - Figma-only context
   - scattered comments
   - inconsistent tickets

`DESIGN.md` solves this by turning the visual system into a **plain-text,
versionable, prompt-friendly source of truth**.

## DESIGN.md vs AGENTS.md

These files are complementary.

| File | Purpose |
|---|---|
| `AGENTS.md` | implementation/process spec |
| `DESIGN.md` | visual/design spec |

A good rule of thumb:

- `AGENTS.md` answers: **How should work happen?**
- `DESIGN.md` answers: **What should the product look like?**

### AGENTS.md typically covers
- architecture
- commands
- testing rules
- deployment or workflow expectations
- coding conventions
- repo guardrails

### DESIGN.md typically covers
- visual mood
- color system
- typography system
- component styling
- spacing and layout
- responsive behavior
- design do's and don'ts

Neither file should try to absorb the whole job of the other.

## Why markdown works well here

The Stitch idea and the `awesome-design-md` examples both reinforce a key point:
markdown is an effective format because it is:

- human-readable
- diffable in git
- easy to keep near code
- easy for LLMs to consume directly
- flexible enough to hold both principles and concrete implementation guidance

A strong `DESIGN.md` should feel like a design system document, not a vague
brand mood board.

## Recommended standard structure

A practical default structure, strongly reinforced by the
`awesome-design-md` examples, is this nine-part layout.

### 1. Visual Theme & Atmosphere
Describe the overall feel.

Include things like:
- mood
- density
- visual philosophy
- temperament words
- whether the UI is calm, bold, editorial, cinematic, technical, playful, etc.

### 2. Color Palette & Roles
List semantic color roles and concrete values.

Include things like:
- primary
- secondary
- accent
- background / surface
- border
- text
- success / warning / error
- CTA usage

### 3. Typography Rules
Define the typographic system explicitly.

Include things like:
- font families
- type hierarchy
- weights
- sizes
- line heights
- letter spacing
- when to use serif, sans, or monospace

### 4. Component Stylings
Describe how common UI elements should look and behave.

Include things like:
- buttons
- links
- inputs
- cards
- modals
- tables
- navigation
- empty states
- hover / active / focus / disabled states

### 5. Layout Principles
Define layout rhythm and spacing behavior.

Include things like:
- spacing scale
- section rhythm
- max widths
- container behavior
- whitespace philosophy
- grid assumptions

### 6. Depth & Elevation
Specify how the interface creates hierarchy.

Include things like:
- shadows
- borders
- blur
- flat vs layered surfaces
- how depth should be used sparingly or boldly

### 7. Do's and Don'ts
Add explicit visual guardrails.

This section is extremely important for agents.
It prevents attractive-but-wrong drift.

### 8. Responsive Behavior
Define what should happen across screen sizes.

Include things like:
- breakpoints
- stacking rules
- minimum touch targets
- what compresses vs what stays fixed
- mobile nav behavior

### 9. Agent Prompt Guide
Give the shortest viable summary for future agent sessions.

This should capture:
- essential design identity
- non-negotiable rules
- the minimal implementation cues needed after context compression

## What a good DESIGN.md looks like

A good `DESIGN.md` is specific enough that an agent can make real UI decisions
without guessing.

### Good examples
- "Primary CTA uses the brand blue, semibold text, medium radius, no heavy shadow."
- "Cards are quiet and flat: subtle border, no floating glass treatment."
- "Headlines are tight and high-contrast; body copy is restrained and highly readable."
- "On mobile, multi-column promo blocks collapse into stacked cards with 16px rhythm."

### Bad examples
- "Make it beautiful."
- "Use a premium vibe."
- "Add modern spacing."
- "Make it look like a top startup."

The point is to reduce ambiguity, not restate taste.

## What a strong DESIGN.md should optimize for

### 1. Specificity
Enough detail to guide actual implementation.

### 2. Reusability
General rules should survive across pages and components.

### 3. Constraint clarity
It should be obvious what is allowed and what is off-brand.

### 4. Prompt durability
A good agent should still produce aligned UI even after context compression.

### 5. Versionability
It should evolve cleanly in git as the product evolves.

## How teams should use DESIGN.md

Recommended workflow:

1. keep `DESIGN.md` at the repo root for UI-bearing projects
2. keep `AGENTS.md` at the repo root as the implementation/process companion
3. instruct agents to read both before generating UI
4. update `DESIGN.md` whenever the visual system changes materially
5. treat it as a living spec, not a one-time prompt artifact

## When a repo should have one

Strong fit:
- web apps
- product frontends
- docs sites with a distinct visual system
- design-heavy internal tools
- component libraries
- marketing / landing repos

Weak fit:
- pure runtime or backend repos
- CLI-only repos
- data-only repos
- infra repos with little or no UI surface

Not every repo needs a `DESIGN.md`.
But any repo with substantial UI generation or iteration probably benefits from one.

## Relationship to implementation

`DESIGN.md` should stay at the level of **visual system and component rules**.
It should not become a dumping ground for:

- engineering architecture
- build commands
- test policies
- deployment workflow
- repo housekeeping rules

Those belong in `AGENTS.md`, `README.md`, or other engineering docs.

## Suggested minimal template

```md
# DESIGN.md

## Visual Theme & Atmosphere
...

## Color Palette & Roles
...

## Typography Rules
...

## Component Stylings
...

## Layout Principles
...

## Depth & Elevation
...

## Do's and Don'ts
...

## Responsive Behavior
...

## Agent Prompt Guide
...
```

## Safe assumptions

- `DESIGN.md` is best understood as a general design-spec pattern
- it should sit beside `AGENTS.md`, not replace it
- markdown is a feature, not a limitation
- the nine-section structure is a strong practical default
- a strong `DESIGN.md` should be concrete enough to drive implementation

## Unsafe assumptions

- every repo automatically needs a `DESIGN.md`
- `DESIGN.md` should contain implementation workflow rules
- a brand mood alone is sufficient
- screenshots alone are an adequate substitute for a reusable text design spec

## Short standard

If a repo has a meaningful UI surface, the cleanest general pattern is:

- `AGENTS.md` = how work happens
- `DESIGN.md` = how the product should look

That split is the standard this page recommends.
