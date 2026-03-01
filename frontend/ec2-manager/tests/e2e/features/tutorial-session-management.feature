Feature: Tutorial session management workflows
  As an instructor using EC2 Tutorials Manager
  I want to create, manage, and delete tutorial sessions and their instances
  So that I can run workshops smoothly

  Background:
    Given I am logged in to EC2 Tutorials Manager

  Scenario: Create tutorial session with initial pool and admin instances
    When I create a test tutorial session with 2 pool and 1 admin and cleanup 9
    And I open the tutorial dashboard for that session
    Then I should see "Instances (3)"
    And the instances table should contain 3 rows

  Scenario: Delete tutorial session and all associated instances
    When I create a test tutorial session with 2 pool and 1 admin and cleanup 7
    And I open the tutorial dashboard for that session
    And I delete the tutorial session and confirm deleting associated instances
    Then I should return to the landing page
    And I should not see the deleted session on landing

  Scenario: Add pool instances to an existing tutorial session
    When I create a test tutorial session with 1 pool and 0 admin
    And I open the tutorial dashboard for that session
    Then I should see "Instances (1)"
    When I open the create instance dialog
    And I create 2 new instances
    Then I should see "Instances (3)"
    And the instances table should contain 3 rows

  Scenario: Add an admin instance with explicit cleanup days
    When I create a test tutorial session with 1 pool and 0 admin
    And I open the tutorial dashboard for that session
    When I open the create instance dialog
    And I create 1 admin instance with cleanup days set to 10
    Then I should see "Instances (2)"

  Scenario: Open workshop selector from landing FAB
    When I click the create session FAB on landing
    Then I should see the workshop selector dialog

  Scenario: Create session from workshop selector using keyboard flow
    When I click the create session FAB on landing
    And I select the first workshop from the selector using keyboard
    And I create a tutorial session from the session form as test with 1 pool and 0 admin
    Then I should see the created session on landing

  Scenario: Create instances from tutorial dashboard FAB flow
    When I create a test tutorial session with 1 pool and 0 admin
    And I open the tutorial dashboard for that session
    Then I should see "Instances (1)"
    When I open the create instance dialog
    And I create 3 new instances
    Then I should see "Instances (4)"
    And the instances table should contain 4 rows
