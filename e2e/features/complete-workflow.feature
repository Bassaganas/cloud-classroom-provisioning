@e2e_workflow
@complete_flow
Feature: Complete Multi-Student Workflow with EC2, Gitea, and Jenkins

  As a platform administrator
  I want to verify that the complete student workflow works end-to-end
  So that students can develop code with automatic CI/CD integration

  Background:
    Given the EC2 Manager UI is accessible
    And Gitea is accessible
    And Jenkins is accessible
    And all services are healthy
    And I am authenticated to the EC2 Manager

  @end_to_end_single_student
  Scenario: Single student completes full workflow
    Given I am authenticated to EC2 Manager as admin
    When I create a new student session with name "workspace-student-a"
    Then EC2 instances are provisioned with StudentId tag
    And Gitea reposit is created and accessible
    And a webhook is configured from Gitea to Jenkins
    When I push sample Python code to the Gitea repository
    Then a webhook event is sent to Jenkins
    And a Jenkins job is triggered with the student identifier
    And the pipeline executes: Lint → Test → Build
    And the build completes successfully
    And the build logs are accessible and contain no errors

  @end_to_end_two_students_parallel
  Scenario: Two students run independent workflows in parallel
    Given Student A creates a session
    And Student B creates a separate session
    When both students are assigned EC2 resources
    Then Student A instances are isolated from Student B
    When Student A pushes code to their repository
    And Student B pushes code to their repository (different code)
    Then Jenkins triggers Student A's build
    And Jenkins triggers Student B's build
    And both builds run to completion
    And Student A's build result is independent from Student B's
    And build logs show no cross-contamination between students

  @complete_resource_lifecycle
  Scenario: Complete lifecycle of student resources
    Given a student creates a new session
    When the session is successfully created
    Then EC2 instances exist and are running
    And instances are tagged correctly
    And Gitea repository exists and contains the seeded Jenkinsfile
    And Jenkins webhook is active on the repository
    When the student pushes code
    Then Jenkins pipeline is triggered
    And pipeline runs to completion
    When the student session is terminated
    Then EC2 instances are terminated/stopped
    And Gitea repository access is revoked
    And Jenkins jobs for the student remain in history (for audit)

  @webhook_to_jenkins_integration
  Scenario: Gitea webhook correctly transmits data to Jenkins
    Given a student repository with ConfigMap/Secret containing:
      | key           | value                    |
      | STUDENT_ID    | student-id-abc          |
      | REPO_NAME     | repo-student-id-abc     |
      | BRANCH        | main                     |
    When the student pushes code to the repository
    Then Gitea webhook POSTs to Jenkins generic webhook trigger endpoint
    And the webhook payload includes:
      | repository            | student-id-abc      |
      | branch                | main                |
      | commits               | [commit-data]       |
      | pusher                | student username    |
    And Jenkins receives the payload and extracts the student ID
    And Jenkins triggers the correct job for that student

  @seeded_jenkinsfile
  Scenario: Repository contains seeded Jenkinsfile
    Given a new student repository is created
    When inspecting the repository contents
    Then a Jenkinsfile exists at the root
    And the Jenkinsfile contains pipeline stages: lint, test, build
    And the Jenkinsfile reads student ID from environment/webhook
    And the Jenkinsfile does NOT contain deployment steps
    When a student pushes code
    And the Jenkinsfile is parsed by Jenkins
    Then the lint stage runs successfully (or shows linting issues)
    And the test stage runs successfully (or shows test failures)
    And the build stage runs successfully (or shows build errors)
    But the pipeline stops after build (no deployment stage)

  @ec2_instance_naming_consistency
  Scenario: EC2 instance names and tags are consistent
    Given a student with ID "student-1a2b3c4d" creates a session
    When instances are provisioned
    Then each instance has:
      | tag key          | tag value           |
      | StudentId        | student-1a2b3c4d    |
      | Workshop         | fellowship          |
      | Environment      | dev                 |
      | CreatedAt        | [timestamp]         |
      | ManagedBy        | e2e-tests           |
    And the instance name/description includes the student ID
    And the instance is tagged so it can be easily found and cleaned up

  @jenkins_job_isolation
  Scenario: Each student's Jenkins job runs in complete isolation
    Given two students A and B with Jenkins jobs configured
    When Student A's job writes to /tmp/student-a
    And Student B's job writes to /tmp/student-b (same runner)
    Then Student A's logs show only /tmp/student-a access
    And Student B's logs show only /tmp/student-b access
    And there is no cross-contamination between student job outputs
    And environment variables are isolated per job

  @cleanup_and_audit_trail
  Scenario: Test cleanup and audit trail maintenance
    Given multiple student sessions have been created and tested
    When test execution completes
    Then EC2 instances tagged with ManagedBy=e2e-tests are identified
    And a cleanup report is generated listing:
      | resource               | count | student_ids      |
      | EC2 instances          | 4     | [list-of-ids]    |
      | Gitea repositories     | 2     | [list-of-ids]    |
      | Jenkins builds         | 6     | [list-of-ids]    |
    And optional: instances can be manually verified before cleanup
    And cleanup proceeds for test resources only
