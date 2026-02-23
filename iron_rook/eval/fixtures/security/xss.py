"""
XSS vulnerability fixture - evaluates security reviewer's ability to detect
cross-site scripting vulnerabilities in user-facing code.
"""

from flask import request, make_response


def render_user_profile():
    """Render user profile with potential XSS vulnerability."""
    user_input = request.args.get("name", "Guest")

    # VULNERABILITY: Direct HTML rendering without escaping
    html = f"""
    <html>
        <body>
            <h1>Welcome, {user_input}!</h1>
            <div class="bio">{request.args.get("bio", "")}</div>
        </body>
    </html>
    """

    response = make_response(html)
    response.headers["Content-Type"] = "text/html"
    return response


def render_comment(comment_text: str) -> str:
    """Render comment with innerHTML assignment."""
    # VULNERABILITY: innerHTML allows script injection
    return f'document.getElementById("comments").innerHTML = "{comment_text}";'


def build_search_results():
    """Build search results HTML."""
    query = request.args.get("q", "")

    # VULNERABILITY: Unescaped user input in HTML context
    return f"""
        <div class="search-header">
            <p>You searched for: {query}</p>
        </div>
        <script>
            // VULNERABILITY: Direct DOM injection
            document.write('<div>Results for: {query}</div>');
        </script>
    """


# Expected review findings:
# 1. Missing HTML escaping for user_input in render_user_profile
# 2. innerHTML assignment allows XSS in render_comment
# 3. Multiple injection points in build_search_results
# 4. document.write is inherently dangerous
