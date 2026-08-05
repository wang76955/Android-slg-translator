# Contributing

Thanks for your interest in contributing to the SLG Translator!

## Development Workflow

1. **Fork** the repository and create a feature branch
2. Make your changes
3. Add or update tests (red/green style: write a failing test first, then implement)
4. Run the full test suite
5. Submit a pull request

## Testing

```bash
cd apk-work/ui-redesign
python -m pytest test_fast_scanner.py test_workshop_patch.py test_translation_coverage.py
```

All 70+ tests must pass before merging. New behavior should come with a test that
fails before the fix and passes after.

## Code Style

- Java: 8 compatible, 4-space indent, documented public methods
- Python: PEP 8, type hints where helpful
- Keep changes focused and minimal; avoid unrelated refactors

## Reporting Issues

Include:

- App version (from Releases) or branch/commit you are testing
- Android device model and OS version
- Steps to reproduce
- Expected vs actual behavior
- Log output if available

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).
