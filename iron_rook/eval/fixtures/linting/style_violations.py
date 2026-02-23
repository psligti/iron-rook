"""
Style violations fixture - evaluates linting reviewer's ability to detect
code style issues that linters like ruff/pylint/flake8 would catch.
"""


class userManager:  # LINT: class name should be PascalCase -> UserManager
    """Manages user data with various style issues."""

    def __init__(self):  # LINT: missing type hints
        self.users = {}  # LINT: missing type annotation
        self.Count = 0  # LINT: attribute should be snake_case

    def get_user(self, user_id):  # LINT: missing space after comma, no type hints
        # LINT: line too long (this comment is intentionally very long to demonstrate the line length violation that most linters would catch at around 88 or 100 characters)
        return self.users.get(user_id)

    def AddUser(self, name, email=""):  # LINT: method should be snake_case
        userId = len(self.users) + 1  # LINT: variable should be snake_case
        self.users[userId] = {"name": name, "email": email}  # LINT: missing spaces
        self.Count += 1  # LINT: missing spaces around operator
        return userId

    def delete_User(self, user_id):  # LINT: inconsistent naming
        if user_id in self.users:
            del self.users[user_id]
            self.Count -= 1  # LINT: missing spaces
            return True
        return False

    def get_all(self):
        # LINT: TODO without issue/link
        # TODO fix this later
        return self.users


def process_data(data):
    # LINT: bare except
    try:
        result = []
        for item in data:
            result.append(item["value"])
    except:
        result = []

    return result


def calculate_sum(numbers):  # LINT: missing docstring
    total = 0  # LINT: missing spaces
    for n in numbers:
        total += n  # LINT: missing spaces
    return total


# LINT: multiple statements on one line
x = 1
y = 2
z = 3


# LINT: comparison to True/False
def check_status(status):
    if status == True:  # LINT: use `if status:` instead
        return "active"
    elif status == False:  # LINT: use `if not status:` instead
        return "inactive"
    return "unknown"


# LINT: unused import (if this were real)
import os  # Would be flagged if not used


# LINT: redefining built-in
def list(items):  # LINT: shadows built-in 'list'
    return items


# LINT: mutable default argument
def add_item(item, items=[]):  # LINT: dangerous default
    items.append(item)
    return items


# LINT: f-string without placeholders
def get_message():
    return f"Hello World"  # LINT: should be regular string


# LINT: unnecessary lambda
def get_keys(dictionary):
    sorted_keys = sorted(dictionary, key=lambda x: x)  # LINT: key=None is same
    return sorted_keys


# LINT: multiple imports on one line
import json, sys, os  # LINT: should be separate lines


# LINT: line break before binary operator
def check_conditions(
    a,
    b,  # LINT: break after operator, not before
    c,
):
    return a and b and c


# Expected review findings:
# 1. class userManager - should be UserManager (PascalCase)
# 2. self.Count - should be self.count (snake_case)
# 3. Missing type hints on most functions
# 4. Missing spaces after commas and around operators
# 5. Line too long comment
# 6. bare except clause
# 7. TODO without issue tracker
# 8. comparison to True/False instead of truthiness
# 9. Shadows built-in 'list'
# 10. Mutable default argument
# 11. f-string without placeholders
# 12. Unnecessary lambda
# 13. Multiple imports on one line
# 14. Line break before comma/operator
