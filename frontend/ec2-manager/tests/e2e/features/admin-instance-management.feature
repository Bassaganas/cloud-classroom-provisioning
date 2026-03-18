Feature: Admin instance management and cleanup days
  As an instructor
  I want to manage admin instance cleanup days and delete instances with confirmation
  So I can have control over resource lifecycle

  Background:
    Given I am logged in to EC2 Tutorials Manager

  Scenario: Admin instance displays remaining cleanup days
    When I create a test tutorial session with 0 pool and 1 admin with cleanup 14
    And I open the tutorial dashboard for that session
    Then I should see the admin instance in the instances table
    And the admin instance should show "Remaining Days" with days remaining
    And the admin instance should have an "Extend" button

  Scenario: Extend admin instance cleanup days via modal
    When I create a test tutorial session with 0 pool and 1 admin with cleanup 7
    And I open the tutorial dashboard for that session
    And I click the "Extend" button on the admin instance
    Then I should see the "Extend Cleanup Days" modal
    When I set the new cleanup days to 14 and confirm
    Then the modal should close
    And the admin instance should be updated with 14 remaining days

  Scenario: Delete single admin instance with confirmation
    When I create a test tutorial session with 1 pool and 1 admin
    And I open the tutorial dashboard for that session
    And I click delete on the admin instance
    Then I should see a confirmation dialog
    When I confirm the deletion
    Then the admin instance should be removed from the table
    And I should see "Instances (1)"

  Scenario: Delete single pool instance with confirmation
    When I create a test tutorial session with 1 pool and 1 admin
    And I open the tutorial dashboard for that session
    And I click delete on the pool instance
    Then I should see a confirmation dialog
    When I confirm the deletion
    Then the pool instance should be removed from the table
    And I should see "Instances (1)"

  Scenario: Bulk select and delete multiple instances with confirmation
    When I create a test tutorial session with 3 pool and 2 admin
    And I open the tutorial dashboard for that session
    Then I should see "Instances (5)"
    When I click the "select all" checkbox in the table header
    Then all 5 instances should be selected
    And the "Delete Selected (5)" button should be enabled
    When I click the "Delete Selected (5)" button
    Then I should see a confirmation dialog for bulk delete
    When I confirm the bulk delete
    Then all instances should be deleted
    And I should see "Instances (0)"

  Scenario: Delete tutorial session cascades to all instances
    When I create a test tutorial session with 2 pool and 1 admin
    And I open the tutorial dashboard for that session
    And I delete the tutorial session and confirm deleting associated instances
    Then I should return to the landing page
    And the session should not appear on the landing page

  Scenario: Landing page shows session type (productive vs test)
    When I create a productive tutorial session with 2 pool
    And I create a test tutorial session with 2 pool
    And I go to the landing page
    Then I should see both sessions listed
    And the productive session should be marked as "Productive"
    And the test session should be marked as "Test"

  Scenario: Landing page displays workshop overview
    When I go to the landing page
    Then I should see:
      | Overview Item              |
      | Workshops                  |
      | Tutorial Sessions          |
      | Tracked Session Instances  |
      | Session Costs (Est.)       |

  Scenario: Add new tutorial session from landing page FAB (multi-step)
    When I click the create session FAB on landing
    Then I should see the workshop selector dialog
    When I select "fellowship" from the workshop list
    Then I should see the tutorial session form
    When I fill in session details:
      | Field                        | Value      |
      | Session ID                   | test_001   |
      | Pool Instances               | 2          |
      | Admin Instances              | 1          |
      | Productive tutorial          | checked    |
    And I submit the form
    Then the session should be created
    And I should return to the landing page
    And the new session should appear in the workshop card

  Scenario: Delete tutorial session from landing page with cascade
    When I create a test tutorial session with 2 pool and 1 admin
    And I go to the landing page
    And I click delete on the session card
    Then I should see a confirmation dialog
    When I confirm deletion
    Then the session should be deleted from the landing page
    And all associated instances should be removed

