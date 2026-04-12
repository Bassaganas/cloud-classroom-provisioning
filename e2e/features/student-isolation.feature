@multi_student
@student_isolation
Feature: Student Isolation and Resource Management
  
  As an classroom infrastructure admin
  I want to ensure that each student gets isolated EC2 instances and repositories
  So that their work doesn't interfere with other students

  Background:
    Given the EC2 Manager is accessible at the configured URL
    And Gitea is accessible and healthy
    And Jenkins is accessible and healthy
    And I have valid EC2 Manager credentials

  @instance_isolation
  Scenario: Two students get unique EC2 instances
    Given Student A creates a session via EC2 Manager
    When Student A is assigned EC2 resources
    And Student B creates a separate session via EC2 Manager
    And Student B is assigned EC2 resources
    Then Student A instances are completely different from Student B instances
    And each student's instances are tagged with their unique StudentId
    And instances are in the same VPC but different security groups (or equivalent isolation)

  @repo_isolation
  Scenario: Each student has their own Gitea repository
    Given Student A and Student B have active sessions
    When Student A creates a code repository in Gitea
    And Student B creates a code repository in Gitea
    Then both repositories exist and are unique
    And each repository is owned by the correct student
    And repositories have isolated access controls

  @naming_convention
  Scenario: Resources follow correct naming conventions
    Given a student creates a session with ID "test-student-abc123"
    When checking the created resources
    Then the EC2 instance has a tag "StudentId=test-student-abc123"
    And the instance name contains the student identifier
    And the Gitea repository path includes the student identifier
    And the Jenkins job namespace includes the student identifier

  @multiple_instances
  Scenario: Students can have multiple instances in their session
    Given Student A creates a session requesting 2 pool instances and 1 IDE
    When the resources are provisioned
    Then Student A has exactly 3 instances
    And all 3 instances are tagged with Student A's StudentId
    And each instance type is correct (pool/IDE)
    And instances are still isolated from Student B's resources
