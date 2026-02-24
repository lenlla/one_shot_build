# Coding Standards

## Python / PySpark

### Style
- Follow PEP 8
- Use type hints for function signatures
- Maximum line length: 120 characters
- Use f-strings for string formatting

### Structure
- One module per logical concern
- Shared utilities go in `src/utils/` — do NOT hand-roll helpers
- Validate data shapes at module boundaries with explicit schema checks
- Use descriptive variable names (no single-letter variables except loop counters)

### Testing
- Tests live in `tests/` mirroring `src/` structure
- Test file names: `test_<module_name>.py`
- Use pytest fixtures for shared setup
- Each test tests ONE behavior
- Tests are written during planning phase and are IMMUTABLE during build

### PySpark Specific
- Use DataFrame API over SQL strings where possible
- Define schemas explicitly (StructType) for data validation
- Cache DataFrames only when reused multiple times
- Use `.explain()` to verify query plans during development

### Commits
- One logical change per commit
- Message format: `<type>: <description>` (feat, fix, test, refactor, docs)
- Include the step name in the message when relevant
