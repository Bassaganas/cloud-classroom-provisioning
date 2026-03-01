Feature: Tutorial endpoint rendering
  As an instructor
  I want endpoint links to render correctly for each workshop
  So that I can open running machines reliably

  Background:
    Given I am logged in to EC2 Tutorials Manager

  Scenario: Fellowship tutorial dashboard shows endpoint links
    When I open tutorial "tut1" for workshop "fellowship"
    Then I should see tutorial overview widgets and the instances table
    And the table row count should match the API tutorial_session response
    And endpoint links in the Endpoint column should include HTTP or HTTPS links

  Scenario: Testus Patronus falls back to HTTP public IP links
    When I open tutorial "tutorial_wetest_athenes" for workshop "testus_patronus"
    Then I should see the instances table
    And all machine links should use HTTP public IP format
