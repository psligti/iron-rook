"""
Missing changelog fixture - evaluates changelog reviewer's ability to detect
changes that should be documented but aren't.
"""

# COMMIT HISTORY (simulated)
COMMITS = [
    {
        "hash": "abc123",
        "message": "feat: add user authentication system",
        "files_changed": ["src/auth/login.py", "src/auth/session.py", "src/models/user.py"],
        "breaking": False,
    },
    {
        "hash": "def456",
        "message": "fix: prevent SQL injection in user search",
        "files_changed": ["src/db/queries.py"],
        "breaking": False,
    },
    {
        "hash": "ghi789",
        "message": "refactor: change User.email to User.email_address",
        "files_changed": ["src/models/user.py", "src/api/users.py", "src/db/queries.py"],
        "breaking": True,  # Changed public API
    },
    {
        "hash": "jkl012",
        "message": "feat: add 2FA support",
        "files_changed": ["src/auth/two_factor.py", "src/api/auth.py"],
        "breaking": False,
    },
    {
        "hash": "mno345",
        "message": "chore: update dependencies",
        "files_changed": ["requirements.txt", "pyproject.toml"],
        "breaking": False,
    },
    {
        "hash": "pqr678",
        "message": "feat!: remove deprecated legacy API endpoints",
        "files_changed": ["src/api/legacy.py"],
        "breaking": True,
    },
    {
        "hash": "stu901",
        "message": "fix: handle edge case in payment processing",
        "files_changed": ["src/payments/processor.py"],
        "breaking": False,
    },
    {
        "hash": "vwx234",
        "message": "perf: optimize database queries for user list",
        "files_changed": ["src/db/user_queries.py"],
        "breaking": False,
    },
    {
        "hash": "yza567",
        "message": "feat: add webhooks for order events",
        "files_changed": ["src/webhooks/orders.py", "src/api/webhooks.py"],
        "breaking": False,
    },
    {
        "hash": "bcd890",
        "message": "fix!: change API response format for /api/users",
        "files_changed": ["src/api/users.py"],
        "breaking": True,
    },
]

# CURRENT CHANGELOG.md (incomplete)
CHANGELOG_MD = """
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- User authentication system

## [1.0.0] - 2024-01-15

### Added
- Initial release
- Basic user management
"""

# EXPECTED CHANGELOG (what it should be)
EXPECTED_CHANGELOG = """
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- User authentication system
- Two-factor authentication (2FA) support
- Webhooks for order events

### Changed
- Optimized database queries for user list (performance improvement)

### Fixed
- SQL injection vulnerability in user search
- Edge case in payment processing

### Security
- SQL injection fix in user search

### Breaking Changes ⚠️
- `User.email` renamed to `User.email_address` - update all references
- Legacy API endpoints (`/api/v1/*`) have been removed
- `/api/users` response format changed (see migration guide)

## [1.0.0] - 2024-01-15

### Added
- Initial release
- Basic user management
"""


def analyze_commits_for_changelog(commits: list) -> dict:
    """
    Analyze commits to determine changelog requirements.

    Categories:
    - Added: New features
    - Changed: Changes to existing features
    - Deprecated: Features being phased out
    - Removed: Features removed
    - Fixed: Bug fixes
    - Security: Security-related changes
    - Breaking: Breaking changes (highlighted)
    """
    changelog_items = {
        "added": [],
        "changed": [],
        "deprecated": [],
        "removed": [],
        "fixed": [],
        "security": [],
        "breaking": [],
    }

    for commit in commits:
        message = commit["message"]

        if commit.get("breaking"):
            changelog_items["breaking"].append(message)

        if message.startswith("feat"):
            changelog_items["added"].append(message)
        elif message.startswith("fix"):
            if "sql injection" in message.lower() or "auth" in message.lower():
                changelog_items["security"].append(message)
            else:
                changelog_items["fixed"].append(message)
        elif message.startswith("refactor"):
            changelog_items["changed"].append(message)
        elif message.startswith("perf"):
            changelog_items["changed"].append(message)

    return changelog_items


# Expected review findings:
# 1. MISSING: feat: add 2FA support - not documented
# 2. MISSING: feat: add webhooks for order events - not documented
# 3. MISSING: fix: prevent SQL injection - not documented (also security)
# 4. MISSING: fix: handle edge case in payment processing - not documented
# 5. MISSING: perf: optimize database queries - not documented
# 6. MISSING BREAKING: refactor change User.email to User.email_address
# 7. MISSING BREAKING: feat! remove deprecated legacy API endpoints
# 8. MISSING BREAKING: fix! change API response format for /api/users
# 9. Security fix should be highlighted in Security section
# 10. Breaking changes should be prominently displayed with migration guidance
# 11. changelog should follow Keep a Changelog format
# 12. Missing [Unreleased] section updates
