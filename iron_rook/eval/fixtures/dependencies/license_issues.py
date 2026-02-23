"""
License issues fixture - evaluates dependencies reviewer's ability to detect
problematic or incompatible software licenses.
"""

# requirements.txt with various licenses
REQUIREMENTS_TXT = """
# Permissive licenses (generally OK)
requests==2.28.0        # Apache-2.0
flask==2.2.0            # BSD-3-Clause
django==4.1.0           # BSD-3-Clause
click==8.1.0            # BSD-3-Clause
pydantic==1.10.0        # MIT

# Copyleft licenses (requires care)
sqlalchemy==2.0.0       # MIT (OK)
werkzeug==2.2.0         # BSD-3-Clause (OK)
bottle==0.12.0          # MIT (OK)

# Potentially problematic licenses
pyserial==3.5           # BSD-3-Clause (OK but note)
wxpython==4.2.0         # wxWindows Library License (compatible with GPL)
reportlab==3.6.0        # BSD-3-Clause + commercial license option

# GPL licenses (viral, may require code disclosure)
gnu-readline==8.1       # GPL-3.0  # WARNING: Viral license
libgcrypt-python==1.9   # GPL-2.0  # WARNING: Viral license
gnutls-python==3.7      # LGPL-2.1 # WARNING: LGPL, static linking issues
gettext-python==0.21    # GPL-3.0  # WARNING: Viral license

# Unclear/proprietary licenses
some-commercial-lib==1.0  # PROPRIETARY  # ERROR: Commercial, no source
internal-toolkit==2.0     # UNKNOWN      # ERROR: License not declared
"""

# package.json with various licenses
PACKAGE_JSON = """
{
  "dependencies": {
    "react": "18.2.0",           // MIT - OK
    "vue": "3.2.0",              // MIT - OK
    "angular": "15.0.0",         // MIT - OK
    "express": "4.18.0",         // MIT - OK
    "lodash": "4.17.21",         // MIT - OK
    
    "jquery": "3.6.0",           // MIT - OK
    "bootstrap": "5.2.0",        // MIT - OK
    
    "chart.js": "3.9.0",         // MIT - OK
    "d3": "7.6.0",               // ISC (MIT-like) - OK
    
    "moment": "2.29.0",          // MIT - OK
    
    "node-uuid": "1.4.0",        // MIT - OK
    
    "atlassian-connect-js": "1.0.0",  // UNKNOWN - WARN
    "oracle-db-driver": "5.0.0"       // PROPRIETARY - ERROR
  }
}
"""


# License compatibility matrix (simplified)
LICENSE_COMPATIBILITY = {
    "MIT": {"compatible_with": ["MIT", "Apache-2.0", "BSD-3-Clause", "ISC"]},
    "Apache-2.0": {"compatible_with": ["MIT", "Apache-2.0", "BSD-3-Clause"]},
    "BSD-3-Clause": {"compatible_with": ["MIT", "Apache-2.0", "BSD-3-Clause"]},
    "GPL-3.0": {"compatible_with": ["GPL-3.0", "GPL-2.0+"], "viral": True},
    "GPL-2.0": {"compatible_with": ["GPL-2.0", "GPL-3.0"], "viral": True},
    "LGPL-2.1": {"compatible_with": ["LGPL-2.1", "GPL-2.0+"], "viral": True},
    "AGPL-3.0": {
        "compatible_with": ["AGPL-3.0", "GPL-3.0"],
        "viral": True,
        "network_copyleft": True,
    },
    "SSPL": {"compatible_with": [], "viral": True, "not_osi_approved": True},
    "BSL": {"compatible_with": [], "not_osi_approved": True},
    "PROPRIETARY": {"compatible_with": [], "proprietary": True},
    "UNKNOWN": {"compatible_with": [], "risk": "high"},
}


def check_license_compatibility(project_license: str, dependencies: dict) -> list:
    """
    Check if dependencies are compatible with project license.

    For a MIT/BSD licensed project:
    - Permissive licenses (MIT, Apache, BSD) are fine
    - GPL/AGPL may require the whole project to be GPL
    - Proprietary licenses may have usage restrictions
    """
    issues = []

    project_info = LICENSE_COMPATIBILITY.get(project_license, {})
    compatible = project_info.get("compatible_with", [])

    for dep_name, dep_license in dependencies.items():
        dep_info = LICENSE_COMPATIBILITY.get(dep_license, {})

        if dep_info.get("proprietary"):
            issues.append(
                {
                    "package": dep_name,
                    "license": dep_license,
                    "severity": "error",
                    "message": "Proprietary license may restrict usage/distribution",
                }
            )
        elif dep_info.get("viral") and project_license not in ["GPL-3.0", "GPL-2.0", "AGPL-3.0"]:
            issues.append(
                {
                    "package": dep_name,
                    "license": dep_license,
                    "severity": "warning",
                    "message": f"Copyleft license may require {project_license} -> GPL conversion",
                }
            )
        elif dep_license == "UNKNOWN":
            issues.append(
                {
                    "package": dep_name,
                    "license": dep_license,
                    "severity": "warning",
                    "message": "License not declared - cannot verify compatibility",
                }
            )

    return issues


# Expected review findings:
# 1. gnu-readline - GPL-3.0 viral license, may require project GPL
# 2. libgcrypt-python - GPL-2.0 viral license
# 3. gnutls-python - LGPL-2.1, static linking concerns
# 4. gettext-python - GPL-3.0 viral license
# 5. some-commercial-lib - PROPRIETARY, may have usage restrictions
# 6. internal-toolkit - UNKNOWN license, cannot verify
# 7. atlassian-connect-js - UNKNOWN license
# 8. oracle-db-driver - PROPRIETARY
# 9. Recommend license check tools: license-checker, SPDX
# 10. For commercial projects, flag all GPL/AGPL/SSPL dependencies
