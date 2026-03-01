@bdd @realstack @npc @chat @login
Feature: NPC chat journey on real Fellowship SUT stack
  As an instructor
  I want to validate realistic NPC chat from the dashboard
  So that opener, reply, and action nudges work on real services

  Scenario: NPC opens conversation and nudges to actionable next step
    Given the real Fellowship SUT stack is running via docker compose
    And I am logged into the Fellowship dashboard
    When the companion chat panel initializes
    And I send a message in companion chat
    Then I should receive a companion reply
    And I should see a suggested action nudge
    When I open the suggested action
    Then I should be navigated to a valid in-app route
    And the destination should contain targeted action context
