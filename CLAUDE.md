# Development Rules

## Test-Driven Development

All new code must follow a strict red-green-refactor cycle:

1. **Write a failing test first.** Before implementing any new function, tool, endpoint, or component, write a test that specifies the expected behavior. Confirm it fails for the right reason before proceeding.
2. **Write only enough code to make the test pass.** Do not add logic not covered by a test.
3. **Refactor with the tests green.** Clean up only after tests pass; tests must remain green throughout.

Never write implementation code without a corresponding test written first. If asked to implement something without a test, write the test first and ask for confirmation before continuing.

**Exception — presentation-only changes:** Skip TDD for changes that are purely cosmetic and contain no logic (e.g. Tailwind class tweaks, color/spacing adjustments, copy changes, reordering existing elements). These do not need tests written first.

### What to test

- **Backend tools** (`backend/agent/tools/`): unit test each tool function in isolation. Mock all external HTTP calls (homeharvest, RentCast, Census, BART, FEMA, etc.) — do not make real network calls in tests.
- **Pricing and risk logic** (`pricing.py`, `risk.py`, `investment.py`): pure functions with no I/O — test exhaustively with representative Bay Area inputs (high overbid market, slow market, hazard zone combos, Prop 13 edge cases).
- **API routes** (`backend/api/routes.py`): integration-test each endpoint using the FastAPI test client against a real SQLite test DB (not mocked) — this is the system boundary where real DB behavior matters.
- **Orchestrator** (`orchestrator.py`): test that tools are registered, the agent prompt contains required steps, and SSE events are emitted in the correct order. Mock the Anthropic API call.
- **Frontend components**: test rendering and user interaction with Vitest + React Testing Library. Do not test implementation details (internal state, class names) — test what the user sees and can do.

### Test file locations

- Backend: `backend/tests/` mirroring the source tree (e.g. `backend/tests/tools/test_property_lookup.py`)
- Frontend: colocated with components (`src/components/AnalysisForm.test.tsx` next to `AnalysisForm.tsx`)

### Running tests

**Backend** (from `backend/`):
```bash
python3 -m pytest tests/ -v
```

**Frontend** (from `frontend/`):
```bash
npm test          # single run
npm run test:watch  # watch mode
```
