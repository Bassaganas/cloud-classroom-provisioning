---
name: e2e-testing
description: Creating or refactoring e2e tests with Playwright in Gherkin format with Behave
---

# End-to-End Testing with Playwright and Behave
Use Playwright for browser automation and Behave for writing tests in Gherkin language. Follow the FIRST principles, implement the Page Object Pattern, and organize tests by functionality unit. Ensure all tests are well-documented and maintainable.

Playwright test should be working against local development environment and also agains my deployed environment. I should be able to easily switch between the two.

organize tests in folders by functionality unit, for example:

```
/tests
  /e2e
    /quest-management
      test_create_quest.feature
      test_edit_quest.feature
    /mini-games
      test_quest_mini_game.feature
    /npc-chat
      test_npc_chat.feature
    /bargaining-market
      test_bargaining_market.feature
    /page-objects
      quest_management_page.py
      mini_games_page.py
      npc_chat_page.py
      bargaining_market_page.py
    /steps
      quest_management_steps.py
      mini_games_steps.py
      npc_chat_steps.py
      bargaining_market_steps.py
```

# Workflow
1. Write Gherkin feature files describing the end-to-end scenarios for each main feature.
2. Implement the corresponding step definitions in Python using Behave.
3. Create Page Object classes for each main feature to encapsulate the Playwright interactions.
4. Run local deployment [scripts](./scripts/docker-deploy-local.sh) and make sure application is up and running before executing the tests.
5. Run the tests against the local development environment.
6. Fix any test or implementation issues and ensure all tests pass reliably and its definition adheres to requirements.
7. Make a report of the test results, including any failures and the steps taken to fix them.

# Assumptions
- The local development environment is properly set up and can be accessed by Playwright by using [scripts](./scripts/docker-deploy-local.sh) it will be running on http://localhost:3000





always update test documentation and summary files after changes, including test pass/fail summaries and any necessary updates to the testing strategy or implementation plan based on test results.

always follow the rules in .github/instructions/rules.instructions.tests.md when writing and organizing tests.

execute all e2e tests when implementing new features or making changes to ensure that the application works as expected from the user's perspective and that all main features are covered by tests.

