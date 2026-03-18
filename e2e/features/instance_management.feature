@e2e @instance_management
Feature: EC2 Instance Management
  As a user managing tutorial sessions
  I want to create, view, and delete EC2 instances
  So that I can control resources and costs

  Background:
    Given I am authenticated and on the tutorial session page
    And the EC2 Manager UI is loaded

  Scenario: Create pool instance via UI
    When I create a new pool instance via the UI
    Then the new instance ID appears in the UI
    And the instance exists in AWS EC2 with "pool" type tag
    And a Route53 record exists for that instance

  Scenario: Delete pool instance via UI
    Given a pool instance exists in the UI
    When I select and delete it in the UI
    Then it disappears from the UI
    And the EC2 instance is terminated in AWS
    And the Route53 record is deleted

  Scenario: Bulk delete pool instances
    Given multiple pool instances exist in the UI
    When I select all and delete them in the UI
    Then all instances disappear from the UI and AWS
    And all Route53 records are deleted

  Scenario: Delete admin instance via UI
    Given an admin instance exists in the UI
    When I select and delete it in the UI
    Then it disappears from the UI
    And the EC2 instance is terminated in AWS
    And the Route53 record is deleted
