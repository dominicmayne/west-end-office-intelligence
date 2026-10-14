# dominicmayne.com showcase upgrade

Approach: superpowers brainstorming → writing-plans, then build in small verified steps.

## What dom wants

Make the site "mindblowing" for the people who look at it (employers in commercial
property and proptech). Improve what is there, especially West End Office Intelligence,
and add Hold, Unearthed and 3D modelling.

## Review findings (live site + repo, 14 Oct 2026)

1. The homepage undersells: "Technology Enthusiast", three projects, and the stat
   "0 prior coding experience" appears twice while the strongest proof (Hold is a live
   product watching 510+ leisure centres) is missing.
2. /about contradicts the homepage: it says "every line of code was my own work" and
   "taught myself Python", while the homepage says the work was AI-directed. An
   interviewer will notice. One honest story everywhere: real estate judgement, AI-directed build.
3. The vacancy "forecast" is not a forecast. `LinearRegression` on year, quarter, rent and
   an ordinal area code is fitted and scored on the same rows, so it only redraws history.
   Anyone from a data team would spot it.
4. The £9/month tier is a password in page source (`login.html`). It hides the best
   features from the target audience and protects nothing. (Decision card asked of dom.)
5. Every Claude call hits the API each time with no cache, so a visitor refreshing runs up cost.
6. No Open Graph / social preview, so a LinkedIn share shows a bare link.
7. "Updated in real time" overclaims: the dataset is quarterly; live search is on demand.

## Plan

### 1. Real forecast (app.py, snapshot)
- Ridge model of next-quarter vacancy change from momentum (last quarter's change) and
  take-up relative to the submarket's own average, with submarket-free pooling.
- Walk-forward backtest (train on quarters before k, predict k). Prototype: MAE 0.30pp
  vs 0.37pp for "no change" naive baseline.
- `predicted` becomes the one-step-ahead model estimate; new `/forecast` gives the next
  four quarters per submarket plus backtest accuracy. Snapshot writes `forecast.json`.
- Known limit: four-quarter path assumes take-up at its average; documented in code.

### 2. Cost guard (app.py)
- In-memory TTL cache (12h) on commentary, live data and deals. Resets on deploy; fine.

### 3. Homepage
- One memorable element: an isometric model of the eight submarkets built from the
  real snapshot: tower height = prime rent, colour = vacancy. Four-tone shading,
  painter's order. Hover/focus reveals figures.
- New positioning line; projects grouped into Flagship, Products people use (Hold,
  Unearthed), Analysis (Talent, Spurs), Making (3D).
- Honest stats; "How I build" section; Open Graph + JSON-LD.

### 4. West End landing + dashboard
- Copy fixes, methodology section with backtest numbers, forecast chart with dashed
  four-quarter extension and accuracy note.
- Access model per dom's decision.

### 5. /about
- Covers every project, fixes the contradiction, keeps experience.

### 6. Verify
- Playwright screenshots at 1280 and 390, light and dark; check console errors;
  `build_snapshot.py` runs clean.

## Risks
- 3D details and Unearthed URL unknown: placeholders until dom supplies them.
- Vercel serves `frontend/` statically; new files must sit inside it.
