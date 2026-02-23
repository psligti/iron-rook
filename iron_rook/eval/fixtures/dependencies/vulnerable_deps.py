"""
Vulnerable dependencies fixture - evaluates dependencies reviewer's ability to detect
packages with known security vulnerabilities.
"""

# requirements.txt with vulnerable packages (simulated)
REQUIREMENTS_TXT = """
# Web Framework
flask==1.0.0  # VULNERABLE: CVE-2018-1000656, upgrade to >=2.0.0

# Database
sqlalchemy==1.2.0  # VULNERABLE: CVE-2019-7164, upgrade to >=1.3.0
pymysql==0.9.0  # VULNERABLE: CVE-2019-5030, upgrade to >=0.9.3

# Authentication
pyjwt==1.6.0  # VULNERABLE: CVE-2018-1000539, upgrade to >=1.6.4
python-jose==3.0.0  # VULNERABLE: multiple CVEs, upgrade to >=3.2.0

# HTTP Client
requests==2.19.0  # VULNERABLE: CVE-2018-18074, upgrade to >=2.20.0
urllib3==1.24.0  # VULNERABLE: CVE-2019-11324, upgrade to >=1.24.2

# Cryptography
cryptography==2.4.0  # VULNERABLE: CVE-2018-1000807, upgrade to >=2.5.0
pyopenssl==18.0.0  # VULNERABLE: CVE-2018-1000807, upgrade to >=19.0.0

# Data Processing
pillow==5.3.0  # VULNERABLE: CVE-2019-11000, upgrade to >=6.2.0
numpy==1.15.0  # VULNERABLE: CVE-2019-6446, upgrade to >=1.16.0

# YAML Processing
pyyaml==5.1  # VULNERABLE: CVE-2020-14343, upgrade to >=5.4

# Misc
jinja2==2.10  # VULNERABLE: CVE-2019-8341, upgrade to >=2.10.1
lxml==4.3.0  # VULNERABLE: CVE-2019-11049, upgrade to >=4.3.3
"""

# pyproject.toml with vulnerable packages (simulated)
PYPROJECT_TOML = """
[project]
dependencies = [
    "django==2.1.0",  # VULNERABLE: Multiple CVEs, upgrade to >=3.2
    "celery==4.2.0",  # VULNERABLE: CVE-2019-11827, upgrade to >=4.3.0
    "redis==3.2.0",   # VULNERABLE: CVE-2021-29463, upgrade to >=3.5.3
    "boto3==1.9.0",   # OK but outdated
    "aiohttp==3.5.0", # VULNERABLE: CVE-2019-5537, upgrade to >=3.5.4
]
"""

# package.json with vulnerable npm packages (simulated)
PACKAGE_JSON = """
{
  "dependencies": {
    "lodash": "4.17.11",     // VULNERABLE: CVE-2019-10744, upgrade to >=4.17.12
    "axios": "0.18.0",       // VULNERABLE: CVE-2019-10742, upgrade to >=0.18.1
    "handlebars": "4.1.0",   // VULNERABLE: CVE-2019-19919, upgrade to >=4.5.3
    "express": "4.16.0",     // OK
    "moment": "2.24.0",      // OK but consider alternatives (date-fns, dayjs)
    "node-fetch": "2.3.0",   // VULNERABLE: CVE-2022-0235, upgrade to >=2.6.7
    "minimist": "1.2.0",     // VULNERABLE: CVE-2020-7598, upgrade to >=1.2.3
    "ws": "6.1.0"            // VULNERABLE: CVE-2019-7532, upgrade to >=7.0.0
  }
}
"""

# Known CVE database (simplified)
CVE_DATABASE = {
    "flask": {"1.0.0": ["CVE-2018-1000656"]},
    "sqlalchemy": {"1.2.0": ["CVE-2019-7164"]},
    "pyjwt": {"1.6.0": ["CVE-2018-1000539"]},
    "requests": {"2.19.0": ["CVE-2018-18074"]},
    "pyyaml": {"5.1": ["CVE-2020-14343"]},
    "lodash": {"4.17.11": ["CVE-2019-10744"]},
    "django": {"2.1.0": ["CVE-2019-12308", "CVE-2019-14232", "CVE-2019-14233"]},
}


def check_requirements_safety(requirements_path: str) -> list:
    """
    Simulated safety check - in real usage would use:
    - pip-audit
    - safety
    - dependabot
    - snyk
    """
    vulnerabilities = []
    # ... implementation
    return vulnerabilities


# Expected review findings:
# 1. flask 1.0.0 - known CVE, upgrade to >=2.0.0
# 2. sqlalchemy 1.2.0 - CVE-2019-7164
# 3. pymysql 0.9.0 - CVE-2019-5030
# 4. pyjwt 1.6.0 - CVE-2018-1000539 (key confusion attack)
# 5. requests 2.19.0 - CVE-2018-18074
# 6. urllib3 1.24.0 - CVE-2019-11324
# 7. cryptography 2.4.0 - CVE-2018-1000807
# 8. pillow 5.3.0 - CVE-2019-11000
# 9. pyyaml 5.1 - CVE-2020-14343 (arbitrary code execution)
# 10. django 2.1.0 - Multiple CVEs
# 11. lodash 4.17.11 - prototype pollution
# 12. Recommend using automated tools: pip-audit, safety, dependabot
