# Quality and E2E contract

## Definition of Done

A feature is not complete because a unit test passes. For any user-visible vertical slice, VerityGraph must prove the journey from the browser through the API and relevant processing/storage layers and back to the browser.

## Quality pyramid

1. **Static checks** — formatting/lint/type/build failures stop early.
2. **Unit tests** — pure parsers, NLP helpers, graph algorithms and policies.
3. **Integration tests** — file -> spans -> NLP -> evidence -> graph.
4. **API contract tests** — success, validation, and failure semantics.
5. **Golden NLP regression** — measured entity/relation/resolution metrics.
6. **Provenance integrity** — every relation references valid evidence and source spans.
7. **Browser E2E** — real user workflows through the running stack.
8. **Optional live-network smoke tests** — never used for deterministic PR gating.

## Phase 0 gate

The browser must:

1. load the React application;
2. call `/api/v1/health` through the frontend reverse proxy;
3. receive the FastAPI health contract;
4. render `API healthy` and the backend version.

This is intentionally small but establishes a real full-stack test before feature complexity grows.

## Future mandatory E2E journeys

- PDF -> analyse -> graph -> edge -> correct page evidence.
- Wikipedia search -> section selection -> analyse -> evidence.
- permitted URL -> preview -> analyse -> URL provenance.
- multi-source workspace -> entity resolution -> unified evidence graph.
- rate answer -> explain weakness -> improve using same evidence -> compare -> keep version.
- copy/download an insight and export graph/entity/relation data.
- Ask VerityGraph -> answer -> inspect supporting evidence.

External web responses will be fixture-backed/mocked in deterministic CI. Live tests are separated so third-party availability cannot make pull requests flaky.
