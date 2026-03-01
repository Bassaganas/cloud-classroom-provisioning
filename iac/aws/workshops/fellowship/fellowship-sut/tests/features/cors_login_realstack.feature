@bdd @realstack @cors @login
Feature: CORS and login on real Fellowship SUT stack
  As an instructor
  I want browser login and CORS validated against real docker services
  So that frontend and backend integration is proven without mocks

  Scenario: CORS preflight and UI login succeed on real stack
    Given the real Fellowship SUT stack is running via docker compose
    And the Caddy API endpoint allows CORS preflight from localhost 3000
    When I login through the Fellowship UI with valid credentials
    Then I should land on the dashboard
    And the authenticated session endpoint should return the current user
