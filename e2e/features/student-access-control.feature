@access_control
@student_resources
Feature: Student Access Control and Resource Isolation

  As a classroom infrastructure admin
  I want to ensure students can only access their own resources
  So that students cannot interfere with or access other students' work

  Background:
    Given Jenkins is accessible and healthy
    And Gitea is accessible and healthy
    And the admin user "fellowship" is available
    And I am properly authenticated as admin

  @jenkins_folder_access
  Scenario: Student can access only their own Jenkins folder
    Given I provision student "aragorn" with password "aragorn"
    When I provision student "legolas" with password "legolas"
    Then student "aragorn" can login to Jenkins with password "aragorn"
    And student "aragorn" can see their Jenkins folder "aragorn"
    And student "aragorn" cannot see folder "legolas" (access denied)
    And student "legolas" can login to Jenkins with password "legolas"
    And student "legolas" can see their Jenkins folder "legolas"
    And student "legolas" cannot see folder "aragorn" (access denied)
    And admin user "fellowship" can see both folders "aragorn" and "legolas"

  @jenkins_pipeline_execution
  Scenario: Student can execute pipeline in their folder but not others
    Given I provision student "gimli" with password "gimli"
    And I provision student "boromir" with password "boromir"
    When I push code to "gimli"'s Gitea repository
    Then the Jenkins pipeline for "gimli" should trigger
    And student "gimli" can see the pipeline execution
    And the pipeline runs with "gimli" credentials
    And student "boromir" cannot trigger "gimli"'s pipeline
    And the build cannot execute with "boromir" credentials in "gimli"'s folder

  @gitea_user_login
  Scenario: Gitea student user can login with correct credentials
    Given I provision student "frodo" with password "frodo"
    When I attempt to login to Gitea as "frodo" with password "frodo"
    Then the login is successful
    And student "frodo" sees Gitea repository "fellowship-org/fellowship-sut-frodo"

  @gitea_repo_access
  Scenario: Student can access only their own Gitea repository
    Given I provision student "sam" with password "sam"
    And I provision student "merry" with password "merry"
    When I login to Gitea as "sam" with password "sam"
    Then "sam" can read repository "fellowship-org/fellowship-sut-sam"
    And "sam" can push to repository "fellowship-org/fellowship-sut-sam"
    And "sam" cannot read repository "fellowship-org/fellowship-sut-merry" (403 Forbidden)
    And "sam" cannot push to repository "fellowship-org/fellowship-sut-merry" (403 Forbidden)
    When I login to Gitea as "merry" with password "merry"
    Then "merry" can read repository "fellowship-org/fellowship-sut-merry"
    And "merry" cannot access "sam"'s repository at all

  @admin_full_access
  Scenario: Admin user can access all student resources
    Given I provision student "treebeard" with password "treebeard"
    And I provision student "sauron" with password "sauron"
    When I login to Jenkins as admin "fellowship"
    Then admin can see all folders including "treebeard" and "sauron"
    And admin can view all pipeline execution details
    When I login to Gitea as admin "fellowship"
    Then admin can read all repositories
    And admin can push to all repositories
    And admin can modify all repositories

  @password_case_sensitivity
  Scenario: Student password is case-sensitive
    Given I provision student "elrond" with password "elrond"
    When I attempt to login with "elrond" and password "ELROND"
    Then the login fails (invalid credentials)
    When I attempt to login with "elrond" and password "elrond"
    Then the login succeeds

  @deprovision_removes_access
  Scenario: Deprovisioning removes student access
    Given I provision student "gandalf-test" with password "gandalf-test"
    And student "gandalf-test" is verified to have Jenkins access
    When I deprovision student "gandalf-test"
    Then student "gandalf-test" cannot login to Jenkins
    And student "gandalf-test" cannot login to Gitea
    And Jenkins folder "gandalf-test" does not exist
    And Gitea repository "fellowship-org/fellowship-sut-gandalf-test" does not exist
    And the Gitea user "gandalf-test" does not exist
