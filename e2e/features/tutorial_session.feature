@e2e @tutorial_session
Feature: Tutorial Session Management
  As a user managing tutorial sessions
  I want to create and delete tutorial sessions
  And ensure cascade deletion of resources
  So that I can properly manage the lifecycle of sessions and their instances

  Background:
    Given I am authenticated and on the landing page
    And the EC2 Manager UI is loaded

  Scenario: Add new tutorial session
    When I add a new tutorial session via the UI
    Then the session appears in the UI
    And a corresponding EC2 instance pool is created in AWS

  Scenario: Delete tutorial session (cascade)
    Given a tutorial session with instances exists
    When I delete the session via the UI
    Then the session disappears from the UI
    And all instances in the session are terminated in AWS
    And all Route53 records for those instances are deleted
