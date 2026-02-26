Feature: Map Page - Quest Markers on Middle-earth Map
  As a user of the Fellowship Quest Tracker
  I want to see quest markers on the Middle-earth map
  So that I can visualize where quests are located

  Background:
    Given the user is logged in
    And the database has been seeded with quests and locations

  Scenario: Quest marker appears in Mordor
    Given a Quest in Mordor
    When the user navigates to the map
    Then the map is displayed with a quest marker in Mordor coordinates
    And quest markers are clickable and show full quest information
    And all quests on the map have associated locations

  Scenario: Map displays all location markers
    When the user navigates to the map
    Then the map displays location markers for seeded locations
    And at least 28 location markers are visible on the map

  Scenario: Quest popup shows complete information
    Given a Quest in Mordor
    When the user navigates to the map
    And the user clicks on a quest marker
    Then the quest popup displays the full quest title
    And the quest popup displays the complete quest description
    And the quest popup displays the quest status
    And the quest popup displays the quest type and priority
    And the quest popup displays the location name
    And the quest popup displays action buttons
