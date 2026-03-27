---
---
description: Always apply these instructions for all code, test, and documentation generation, review, and answering questions in this project.
applyTo: '*'
---
# Copilot Rule Set for LOTR SUT

This document defines the rules and guidance for GitHub Copilot usage in the Fellowship's Quest List (LOTR SUT) project. These rules ensure code, tests, and documentation are thematically consistent, technically robust, and aligned with project requirements.

## 1. Themed Guidance
- Always use Lord of the Rings (LOTR) terminology, names, and lore in code, UI, and documentation.
- Ensure all NPC dialogue and quest descriptions are in-character and lore-consistent.
- Apply LOTR-themed visual and UX elements (colors, icons, etc.) throughout the app.

## 2. User Experience
- Use modals for all quest mini-games and completion flows.
- Avoid disruptive popups; use in-app toast notifications for feedback.
- Ensure all interactive elements are visible without scrolling on common laptop and mobile viewports.
- Use subtle, non-distracting animations for modal transitions.
- Provide explicit, recoverable feedback for both success and failure states.

## 3. Main Features
- Always preserve and maintain: quest management, mini-games, NPC chat, bargaining market, and Middle-earth map.
- Update the walkthrough documentation with every new feature addition.

## 3a. Documentation Updates
- Always update REQUIREMENTS.md and TESTING.md to reflect any new feature implementation, changes to acceptance criteria, or modifications to test requirements.

## 4. Frontend Technical Guidance
- Use React functional components and hooks.
- Use TypeScript for all components.
- Follow standard industry best practices for structure, state management, and testing.
- Use the existing design system and theme variables.

## 5. Backend Technical Guidance
- Use Python 3.10+ and Flask for all backend services.
- Follow RESTful API design principles.
- Ensure consistent error handling and logging.
- Separate business logic from route handlers.
- Use environment variables for configuration.
- Use the currently adopted ORM/migration tool.

## 6. Testing Guidance
- Write unit tests for all new logic and components.
- Write integration tests for all API calls (happy path and error handling).
- Write E2E tests for each main feature, covering happy and failure paths, using Playwright, FIRST principles, Page Object Pattern, and Gherkin language with Behave.
- Use pytest for backend, Jest/RTL for frontend.
- Maintain at least 80% unit test coverage.
- Structure E2E tests in folders by functionality unit.
- Always update test documentation and summary files after changes.

## 7. References
- For detailed requirements, see [REQUIREMENTS.md](REQUIREMENTS.md) and [QUEST_MINIGAMES_REQUIREMENTS_SPEC_AND_TEST_PLAN.md](QUEST_MINIGAMES_REQUIREMENTS_SPEC_AND_TEST_PLAN.md).
- For testing and acceptance criteria, see [TESTING.md](TESTING.md).
- For troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

---

**These rules are always in effect and must be referenced for all Copilot code, test, and documentation generation in this project.**