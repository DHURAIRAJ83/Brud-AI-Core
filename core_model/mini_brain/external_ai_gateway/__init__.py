"""MB-21: Brud Mini Brain External AI Evaluation Gateway -- pure logic.

External AI providers are used strictly as evaluation assistants,
never as autonomous decision-makers. Every module here is
deterministic, pure, and JSON-serializable: no database access, no
network calls, no filesystem writes. All provider output remains
untrusted candidate evidence -- nothing here ever produces an approval
decision for a dataset, a release, or anything else; that authority
stays with a human admin via `admin_review()` in the service layer.
"""
