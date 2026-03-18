@e2e @admin_instance_days
Feature: Admin Instance Days Management
  As a user managing admin instances
  I want to view and extend the remaining days for admin instances
  And verify auto-deletion when days expire
  So that I have control over admin instance lifecycle

  Background:
    Given I am authenticated and on the tutorial session page
    And the EC2 Manager UI is loaded

  Scenario: Display remaining days for admin instance
    Given an admin instance exists in the UI
    Then the UI shows the correct remaining days for that instance

  Scenario: Extend admin instance days
    Given an admin instance exists in the UI
    When I extend the days via the UI for that instance
    Then the new value is shown in the UI
    And the CleanupDays tag is updated in AWS

  Scenario: Admin instance is auto-deleted after days expire
    Given an admin instance with 0 days remaining is created
    When I trigger the backend cleanup Lambda
    Then the instance no longer appears in the UI
    And the instance is terminated in AWS
    And the Route53 record is deleted
