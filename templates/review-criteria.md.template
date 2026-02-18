# Review Criteria

The review agent checks each step against these criteria.

## Must Pass (blocking)
1. **Acceptance criteria met** — Does the implementation satisfy the step spec?
2. **Tests pass** — Full test suite, not just the new tests for this step
3. **Test immutability** — No test files modified during build phase
4. **No regressions** — Existing functionality still works
5. **Coding standards** — Follows project conventions (see coding-standards.md)

## Should Pass (flag but don't block)
6. **Shared utilities** — Uses centralized utilities instead of hand-rolled helpers
7. **Typed boundaries** — Data shapes validated at module boundaries
8. **Commit quality** — Descriptive message, focused diff, no unrelated changes
9. **Production quality** — No TODOs, debug prints, commented-out code

## Anti-Pattern Detection
- Test-only loops (running tests repeatedly without code changes)
- Feature creep (implementing beyond the step spec)
- Refactoring working code outside the current step scope
