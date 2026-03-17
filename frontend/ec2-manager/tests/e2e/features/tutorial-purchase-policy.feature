Feature: Tutorial purchase policy enforcement
  As a platform owner
  I want purchase policy to be enforced at tutorial level
  So that test tutorials use Spot and productive tutorials use On-Demand

  Background:
    Given I am logged in to EC2 Tutorials Manager

  Scenario: Test tutorial enforces Spot purchase type during instance creation
    When I create a test tutorial session with 1 pool and 0 admin
    And I open the tutorial dashboard for that session
    Then I should see "Instances (1)"
    When I open the create instance dialog
    Then I should see the test tutorial Spot enforcement message
    When I set Spot max price to "0.011" and create 1 instance
    Then the spot create request should contain purchase_type spot and spot_max_price "0.011"
    And I should see "Instances (2)"

  Scenario: Productive tutorial enforces On-Demand during instance creation
    When I create a productive tutorial session with 1 pool and 0 admin
    And I open the tutorial dashboard for that session
    Then I should see "Instances (1)"
    When I open the create instance dialog
    Then I should see the productive tutorial On-Demand enforcement message
    When I create 1 new instance
    Then I should see "Instances (2)"
