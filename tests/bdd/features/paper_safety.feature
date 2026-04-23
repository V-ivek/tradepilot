Feature: Paper-trading safety invariants
  The system should refuse to touch Alpaca's live endpoint no matter what.

  Scenario: The paper-trading adapter refuses to boot against the live endpoint
    When an AlpacaPaperTradingAdapter is constructed against the live base URL
    Then a RuntimeError is raised mentioning "architecturally blocked"

  Scenario: An expired confirmation token is rejected by verify_order_token
    Given a signed order draft created 2 minutes ago
    Then verify_order_token returns False

  Scenario: A tampered confirmation token is rejected by verify_order_token
    Given a freshly signed order draft
    And the draft's quantity has been silently mutated
    Then verify_order_token returns False

  Scenario: The validator drops trading blocks without mode paper
    Given a trade_intent block with mode "live"
    When the validator runs
    Then the trade_intent block is dropped
