@jenkins_webhook
@pipeline_trigger
Feature: Jenkins Pipeline Triggered by Gitea Webhook

  As a developer
  I want my code push to automatically trigger a Jenkins pipeline
  So that my tests and builds run automatically

  Background:
    Given Gitea is accessible and healthy
    And Jenkins is accessible and healthy
    And I have a student session with EC2 resources
    And I have a personal Gitea repository created

  @webhook_basic
  Scenario: Webhook is created when repository is set up
    Given a new student repository is created in Gitea
    When the webhook configuration is initialized
    Then a webhook exists on the repository
    And the webhook is active and points to Jenkins
    And the webhook is configured to trigger on push events

  @push_triggers_pipeline
  Scenario: Code push triggers Jenkins job via webhook
    Given a student repository in Gitea with a webhook configured
    And a Jenkinsfile exists in the repository's main branch
    When I push code to the repository (commit: "Initial implementation")
    Then Gitea sends a webhook event to Jenkins
    And the webhook delivery is successful (HTTP 200)
    And Jenkins receives the webhook payload
    And a new build job is started in Jenkins

  @pipeline_execution
  Scenario: Jenkins pipeline executes build stages
    Given a Jenkins pipeline is triggered from a Gitea webhook
    When the pipeline starts executing
    Then the Lint stage runs (e.g., pylint/flake8)
    And the Test stage runs (e.g., pytest)
    And the Build stage runs (e.g., artifact creation)
    And the pipeline completes successfully
    And the build status is SUCCESS

  @pipeline_failure_handling
  Scenario: Pipeline correctly handles build failures
    Given a Jenkins pipeline is triggered
    When the Test stage fails (failing test)
    Then the pipeline stops at the failing stage
    And the build status is FAILURE
    And the build log contains error details
    And the student can view the failure details in Jenkins UI

  @webhook_payload_validation
    Scenario: Webhook payload contains correct student/repo information
    Given a student repository with a webhook configured
    When a push event triggers the webhook
    Then the webhook payload includes:
      | field          | value                    |
      | repository     | student-{student-id}     |
      | branch         | main                     |
      | commits        | >= 1                     |
      | pusher_id      | {student-id}             |
    And Jenkins correctly parses the student identifier from the payload
    And the Jenkins job is named or tagged with the student identifier

  @multiple_pushes
  Scenario: Multiple sequential pushes trigger separate builds
    Given a Gitea repository with webhook enabled
    When I push code (commit 1: "Feature A")
    Then build #1 is triggered and completes successfully
    When I push different code (commit 2: "Feature B")
    Then build #2 is triggered
    And build #2 is independent from build #1
    And both builds have isolated logs and artifacts

  @webhook_timeout
  Scenario: Pipeline respects execution timeout
    Given a Jenkins pipeline is running
    When the pipeline execution exceeds the configured timeout (10 minutes)
    Then the pipeline aborts automatically
    And the build status is ABORTED or FAILURE
    And resources are cleaned up properly
