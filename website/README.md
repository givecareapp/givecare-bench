# LongitudinalBench Website

**Live URL**: https://givecareapp.github.io/givecare-bench/

## Overview

Static website for LongitudinalBench, hosted on GitHub Pages.

## Structure

```
website/
├── index.html          # Homepage
├── about.html          # About page
├── leaderboard.html    # Leaderboard page
├── style.css           # Shared styles
├── gc.svg              # Logo
└── data/
    └── leaderboard.json # Leaderboard data
```

## Pages

### Homepage (index.html)
- Overview of LongitudinalBench
- Key features and dimensions
- Links to repository and documentation

### About (about.html)
- Detailed methodology
- Evaluation dimensions explained
- Research background

### Leaderboard (leaderboard.html)
- Model rankings across dimensions
- Interactive filtering and sorting
- Performance visualizations

## Updating the Leaderboard

The leaderboard data is synced from `data/leaderboard/leaderboard.json`:

```bash
# Generate new leaderboard data
python scripts/generate_leaderboard.py

# Data automatically copied to website/data/
# Commit and push to update live site
git add website/data/leaderboard.json
git commit -m "Update leaderboard data"
git push
```

## Local Development

```bash
# Serve locally (requires Python)
cd website
python -m http.server 8000

# Open http://localhost:8000
```

## Deployment

The website is automatically deployed via GitHub Pages when changes are pushed to the `main` branch.

## Configuration

- **Base URL**: https://givecareapp.github.io/givecare-bench/
- **Branch**: main
- **Directory**: /website
- **Custom domain**: None (using GitHub subdomain)

## SEO & Metadata

All pages include:
- Open Graph tags for social sharing
- Twitter Card metadata
- Canonical URLs
- Semantic HTML structure
- Accessibility attributes

## Design

- Responsive design (mobile-first)
- Clean, minimal aesthetic
- Accessible color contrast
- Fast loading (static HTML/CSS/JS)
