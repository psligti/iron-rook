"""Example fixture for hardcoded secrets security testing.

This fixture provides a sample codebase with intentional secret exposures
for testing the security reviewer agent.
"""

SECRETS_CODE = """
# config.py
import os

# VULNERABLE: Hardcoded API key
API_KEY = "sk-prod-abc123def456ghi789jkl012mno345pqr678"

# VULNERABLE: Hardcoded database password
DATABASE_URL = "postgresql://admin:SuperSecret123!@db.example.com:5432/production"

# VULNERABLE: Hardcoded AWS credentials
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# VULNERABLE: Hardcoded JWT secret
JWT_SECRET = "my-super-secret-jwt-key-do-not-share"

# Acceptable: Environment variable
SAFE_API_KEY = os.environ.get("API_KEY")
"""

EXPECTED_FINDINGS = [
    {
        "title": "Hardcoded API Key",
        "severity": "blocking",
        "category": "secrets",
        "file": "config.py",
        "line": 5,
        "evidence": 'API_KEY = "sk-prod-abc123def456ghi789jkl012mno345pqr678"',
    },
    {
        "title": "Hardcoded Database Password",
        "severity": "blocking",
        "category": "secrets",
        "file": "config.py",
        "line": 8,
        "evidence": 'DATABASE_URL = "postgresql://admin:SuperSecret123!@..."',
    },
    {
        "title": "Hardcoded AWS Credentials",
        "severity": "blocking",
        "category": "secrets",
        "file": "config.py",
        "line": 11,
        "evidence": 'AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"',
    },
    {
        "title": "Hardcoded JWT Secret",
        "severity": "critical",
        "category": "secrets",
        "file": "config.py",
        "line": 15,
        "evidence": 'JWT_SECRET = "my-super-secret-jwt-key-do-not-share"',
    },
]
