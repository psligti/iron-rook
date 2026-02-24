"""
Edge case: Mixed language and non-Python content.

STRESS TEST: Tests multi-language handling, file type detection.
EXPECTED BEHAVIOR:
- Should handle or skip non-Python appropriately
- Should NOT crash on non-Python code
"""

# This file contains multiple languages in code blocks

PYTHON_CODE = """
def python_function():
    return "Hello from Python"
"""

JAVASCRIPT_CODE = """
function javascriptFunction() {
    const x = eval(userInput); // SECURITY ISSUE in JS context
    return "Hello from JavaScript";
}
"""

SQL_CODE = """
-- This is SQL, not Python
SELECT * FROM users WHERE id = ' + userId + ' -- SQL injection in JS/SQL context
"""

BASH_CODE = """
#!/bin/bash
# This is bash, not Python
USER_INPUT=$1
eval "$USER_INPUT"  # SECURITY ISSUE in bash context
curl "https://api.example.com?key=sk-1234567890abcdef"  # API key in bash
"""

TEMPLATE_CODE = """
<html>
    <body>
        <div>{{ user_input }}</div>  <!-- Potential XSS in template context -->
        <script>document.write(location.hash)</script>
    </body>
</html>
"""

YAML_CODE = """
# This is YAML, not Python
database:
  password: hardcoded_password_123
  api_key: sk-secret-key-here
"""


# Python code with embedded queries
def get_user(user_id: str):
    # This string LOOKS like SQL injection but is just a string
    # in Python - agent should understand context
    query = "SELECT * FROM users WHERE id = ?"
    return query, (user_id,)


# This Python code has a real issue
def get_user_unsafe(user_id: str):
    import sqlite3

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = '{user_id}'")  # REAL ISSUE
    return cursor.fetchone()


# Expected review findings:
# 1. get_user_unsafe has real SQL injection
# 2. Should NOT flag embedded JS/SQL/Bash as issues in Python string context
# 3. Should understand that these are strings, not executed code
#
# METADATA:
# - Tests context awareness
# - Tests language detection
# - Tests false positive handling
