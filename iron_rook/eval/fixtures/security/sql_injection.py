"""Example fixture for SQL injection security testing.

This fixture provides a sample codebase with intentional SQL injection
vulnerabilities for testing the security reviewer agent.
"""

INJECTION_CODE = """
# vulnerable_code.py
import sqlite3

def get_user(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # VULNERABLE: Direct string formatting in SQL query
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    return cursor.fetchone()

def search_users(search_term):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # VULNERABLE: String concatenation in SQL
    cursor.execute("SELECT * FROM users WHERE name LIKE '%" + search_term + "%'")
    return cursor.fetchall()

def delete_user(user_input):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # VULNERABLE: Raw input in SQL
    sql = "DELETE FROM users WHERE id = " + user_input
    cursor.execute(sql)
    conn.commit()
"""

EXPECTED_FINDINGS = [
    {
        "title": "SQL Injection in get_user",
        "severity": "critical",
        "category": "injection",
        "file": "vulnerable_code.py",
        "line": 8,
        "evidence": 'query = f"SELECT * FROM users WHERE id = {user_id}"',
    },
    {
        "title": "SQL Injection in search_users",
        "severity": "critical",
        "category": "injection",
        "file": "vulnerable_code.py",
        "line": 15,
        "evidence": '"SELECT * FROM users WHERE name LIKE \'%" + search_term + "%\'"',
    },
    {
        "title": "SQL Injection in delete_user",
        "severity": "blocking",
        "category": "injection",
        "file": "vulnerable_code.py",
        "line": 22,
        "evidence": 'sql = "DELETE FROM users WHERE id = " + user_input',
    },
]
