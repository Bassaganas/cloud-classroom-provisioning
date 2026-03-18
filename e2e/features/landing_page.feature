@e2e @landing_page
Feature: Landing Page Overview
  As a user
  I want to view workshop overview and infrastructure statistics
  So that I can understand my current resource status and costs

  Background:
    Given I am authenticated and on the landing page
    And the EC2 Manager UI is loaded

  Scenario: Display overview and workshop cards
    When I view the landing page
    Then I see all workshops displayed
    And I see all tutorial sessions listed
    And the total EC2 instance count is displayed correctly

  Scenario: Display and filter cost
    When I view the cost section on the landing page
    Then the cost is displayed
    And I can filter by time period
    And the filtered cost value is shown correctly
