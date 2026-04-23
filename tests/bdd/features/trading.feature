Feature: Two-turn paper-trading confirmation gate
  As an authenticated user
  I want to place paper orders only after confirmation
  So that the LLM never places an order in a single turn

  Background:
    Given the tradepilot stack is running

  Scenario: Buy request emits a trade_intent and halts
    When the user sends "Buy 10 TSLA at market"
    Then a "trade_intent" block is streamed
    And the block carries mode "paper"
    And no "order_result" block is emitted in the same turn
    And the conversation's graph state has awaiting_confirmation set to true

  Scenario: Confirmation on the next turn places the paper order
    Given the user has a pending paper order for TSLA
    When the user sends "confirm" in the same conversation
    Then an "order_result" block is streamed
    And the block carries mode "paper"
    And the conversation's graph state has awaiting_confirmation set to false
    And the fake paper broker recorded a filled order for "TSLA"

  Scenario: Cancel on the next turn clears the pending order
    Given the user has a pending paper order for TSLA
    When the user sends "cancel" in the same conversation
    Then no "order_result" block is emitted
    And the conversation's graph state has awaiting_confirmation set to false
    And the fake paper broker has no recorded orders

  Scenario: Tampered pending draft is rejected at execute time
    Given the user has a pending paper order for TSLA
    And the pending draft has been tampered with
    When the user sends "confirm" in the same conversation
    Then a "text" block mentions "expired or tampered"
    And no "order_result" block is emitted

  Scenario: A paper-trading response always contains the phrase "paper trading"
    When the user sends "Show my account"
    Then at least one text block contains "paper trading"
    And an "account_summary" block carries mode "paper"
