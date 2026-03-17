Feature: Workshop dashboard cost visibility
  As an instructor
  I want to see estimated and actual cost indicators on the general workshop dashboard
  So that I can track short-term and monthly expected spend

  Background:
    Given I am logged in to EC2 Tutorials Manager

  Scenario: General workshop dashboard shows cost summary and monthly expected cost
    When I open workshop dashboard for "fellowship"
    Then I should see workshop cost summary cards
    And I should see a monthly expected cost value
    And the general instances table should include cost columns
    And workshop cost cards should match API totals for "fellowship"

  Scenario: Landing dashboard session costs match tutorial sessions API
    When I request tutorial sessions API costs for all workshops
    Then the landing session costs should match tutorial sessions API totals

  Scenario: List API returns cost fields when include_actual_costs is enabled
    When I request workshop instances API with include_actual_costs enabled for "fellowship"
    Then the list API response should include actual cost summary fields
    And the list API response instances should include estimated and actual cost fields

  Scenario: API gracefully handles unavailable cost data
    When I request workshop instances API with include_actual_costs enabled for "fellowship" with unavailable cost source
    Then the list API response should indicate actual_data_source is "unavailable"
    And estimated cost fields should still be present in the response
