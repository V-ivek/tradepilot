Feature: Chat endpoint end-to-end
  As an authenticated user
  I want to chat with tradepilot
  So that I can get answers about US stocks

  Background:
    Given the tradepilot stack is running

  Scenario: Off-topic questions are politely rejected
    When the user sends "What's the weather?"
    Then a "text" block is streamed
    And the text mentions "outside"
    And no trading block is emitted

  Scenario: Asking for a stock quote returns a quote block
    When the user sends "What's AAPL's price?"
    Then a "quote" block is streamed
    And the block's symbol is "AAPL"
    And the block carries "change_pct"

  Scenario: Finance concept questions are answered with educational disclaimer
    When the user sends "What's an ETF?"
    Then a "text" block is streamed
    And the text mentions "etf"

  Scenario: The same conversation id is reused across turns
    When the user sends "What's AAPL's price?"
    And the user sends "What about TSLA?" in the same conversation
    Then the second response uses the first response's conversation_id

  Scenario: Requests with no Authorization header are rejected
    When an unauthenticated request is sent to "/chat"
    Then the response status is 401
