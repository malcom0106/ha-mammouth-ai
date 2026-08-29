# Changelog

All notable changes to the Mammouth AI Home Assistant integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Critical**: the `conversation` and `coordinator` platform files were saved as `conversation_old.py` / `coordinator_old.py`, so the integration silently failed to load on every fresh install.
- Invalid default model (`mammouth-default` is not a recognized Mammouth API model id); now defaults to `mammouth-recommended`.
- `max_tokens` and `temperature` options configured in the UI were never actually sent to the API — they had no effect since the very first release. Now wired through.
- Invalid/expired API key errors were swallowed by a broad `except Exception` and reported as a generic "unknown error" instead of triggering Home Assistant's native reauthentication flow.
- Automations edited by the assistant could end up with both `trigger`/`triggers` (or `condition`/`conditions`, `action`/`actions`) on the same entry, which Home Assistant rejects outright ("Cannot specify both..."). Writes now always use the canonical plural schema and de-duplicate every entry in the file on each write, self-healing any legacy broken entries along the way.
- `translations/en.json` lived at the component root instead of `translations/`, so custom-component labels never displayed (Home Assistant doesn't read `strings.json`/root-level translations for custom integrations).
- Conversation history was rebuilt from scratch on every message, causing the assistant to contradict itself or "forget" what it had just said one turn earlier.
- No timeout on direct device control (`call_service`): an unresponsive device could block the whole conversation turn indefinitely. Now bounded (30s).
- Concurrent writes to `automations.yaml`/`scripts.yaml` (e.g. two users acting at once) could silently overwrite each other's changes. Now serialized with async locks.

### Added
- Full tool-calling (function calling) support for the conversation agent: read the instance (areas, devices, entities, states), control devices directly, and create/update/delete automations, scripts, and dashboards.
- Persistent memory across restarts: the agent can learn and recall facts (`remember_fact`) via Home Assistant's native `Store` helper, with bounded size and debounced writes to avoid disk I/O on every turn.
- Editable "base context" option (persona / stable house rules), similar to a Claude Project's custom instructions.
- Conversation continuity is now scoped per Home Assistant user rather than per browser window/session.
- Automations/scripts can now be looked up by config id, real `entity_id`, *or* alias (accent- and case-insensitive) — previously only an exact numeric id or alias worked, causing frequent false "not found" results.
- Read tools (`get_ha_overview`, `search_entities`) automatically widen their search across all domains when a domain filter returns nothing, instead of relying on the model to remember to do so.
- Structural validation of trigger/condition/action/sequence payloads before writing, to catch malformed data before it corrupts the config file rather than after Home Assistant fails to load it.
- `assign_entity_area` tool to move an entity (including automations/scripts) to a different area.
- Translations recreated for all 7 originally supported languages (en, fr, es, de, it, pt, nl).

### Changed
- Configuration-changing tool calls (create/update/delete automation or script, create dashboard, assign area) now require the model to describe the exact planned change and get explicit confirmation before acting — a "yes" to "should I look into it?" no longer authorizes a write.
- The model is now instructed to never claim an action succeeded without a real `success: true` result from the corresponding tool.

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
