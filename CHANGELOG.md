# Changelog

All notable changes to the Mammouth AI Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- No changes pending

---

## [1.1.0] - 2025-08-18

### Added
- Systematic code quality checks in development workflow
- Flake8 configuration file (setup.cfg) with 88-character line length
- Quality standards documentation in CLAUDE.md
- CHANGELOG.md for tracking project changes

### Changed
- Updated CLAUDE.md with systematic quality check procedures
- Code formatting standardized to 88-character line length (Black + Flake8 compatible)
- Import sorting standardized with isort
- Version bumped from 1.0.2 to 1.1.0

### Fixed
- Fixed type annotations in config_flow.py (FlowResult → ConfigFlowResult)
- Fixed whitespace before ':' in coordinator.py (E203 error)
- Fixed long docstring in coordinator.py for flake8 compliance

### Technical
- Pylint score: 9.97/10
- MyPy: No type errors
- Flake8: No linting errors
- Black: All files formatted
- isort: All imports sorted

---

## Previous Changes

*Note: This changelog was created on 2025-08-18. Previous changes were not tracked systematically.*

---

## How to Update This File

When developing features, always update this changelog:

1. **[Unreleased]** section for work in progress
2. Create a new version section when releasing
3. Use these categories:
   - **Added** for new features
   - **Changed** for changes in existing functionality  
   - **Deprecated** for soon-to-be removed features
   - **Removed** for now removed features
   - **Fixed** for any bug fixes
   - **Security** for vulnerability fixes
   - **Technical** for code quality, refactoring, etc.

4. Always run quality checks before updating changelog
5. Include relevant technical metrics when applicable