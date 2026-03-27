# Testing Guidance

## Unit Tests
- Write unit tests for all new logic and components
- Use pytest for backend, Jest/RTL for frontend
- Maintain at least 80% unit test coverage

## Integration Tests
- Write integration tests for all API calls
- Cover happy path and error handling scenarios

## End-to-End Tests
- Write E2E tests for each main feature covering happy and failure paths
- Use Playwright as the testing framework
- Use Playwright runner with TypeScript SDK
- Use gehrkin language with cucumber to specify scenarios
- Follow FIRST principles
- Implement Page Object Pattern
- Structure E2E tests in folders organized by functionality unit

## Documentation
- Always update test documentation and summary files after changes