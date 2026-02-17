# Security Context for Automated Reviews

This document provides architectural context for security reviewers to avoid false positives
and focus on real vulnerabilities. **Read this BEFORE analyzing code.**

## Authentication & Authorization

### Where Auth Happens
- **Router/API Gateway Layer**: All authentication and authorization is enforced at the FastAPI router or API gateway level
- **Service Layer**: Service functions are internal and NOT decorated with auth decorators
- **DO NOT FLAG**: Missing `@auth_required`, `@login_required`, or auth checks in service-layer functions

### Pattern Recognition
```
# THIS IS CORRECT - auth at router level
@router.post("/api/checkout")
@require_auth  # <-- Auth here
async def checkout_endpoint(request: Request):
    return await checkout_service(request.data)  # <-- No auth decorator needed

# DO NOT FLAG service functions without auth decorators
async def checkout_service(data: dict):  # <-- This is FINE
    ...
```

## Rate Limiting

### Where Rate Limiting Happens
- **API Gateway**: Rate limiting is enforced at the API gateway (Kong, Envoy, etc.)
- **Middleware**: Application-level rate limiting in FastAPI middleware
- **DO NOT FLAG**: Missing rate limiting decorators on individual service functions

### When to Flag Rate Limiting Issues
- Only flag if the code REMOVES or BYPASSES existing rate limiting
- Only flag if a new public endpoint is added without router-level protection

## Session Management

### Where Sessions Are Managed
- **SessionMiddleware**: Sessions are created/validated at the router layer
- **Service Functions**: Receive `session_id` as parameters, don't create sessions
- **DO NOT FLAG**: Missing session creation in service functions

### When to Flag Session Issues
- Session fixation vulnerabilities
- Session data stored in insecure locations
- Session ID exposure in logs/URLs

## Input Validation

### Where Validation Happens
- **Pydantic Models**: Request validation via Pydantic models at router boundary
- **Service Layer**: May have additional business logic validation
- **DO NOT FLAG**: Missing input validation in service functions if router has Pydantic validation

## Known Safe Patterns

### HTML/XML Parsing
- **BeautifulSoup with `html.parser`**: This is the SECURE parser choice (not lxml or html5lib)
- **DO NOT FLAG**: "BeautifulSoup parser configuration is secure" as a vulnerability

### Unused Parameters
- Parameters marked for future use or interface compliance are intentional
- **DO NOT FLAG**: `session_manager` parameter unused if it's for future expansion

### Positive Security Controls
If you find code that IMPLEMENTS security correctly:
- Mark as **INFO** severity with **POSITIVE** category
- **DO NOT** mark as "blocking" or a vulnerability
- Example: "Uses secure html.parser" is a POSITIVE finding

## Out of Scope for Most Modules

The following are typically NOT the responsibility of individual modules:
- Authentication/authorization enforcement (router level)
- Rate limiting (gateway level)
- Session creation/validation (middleware level)
- CSRF protection (framework level)
- Content Security Policy headers (server config)

**Only flag these if the module specifically handles these concerns.**

## Severity Classification Guidelines

### CRITICAL (Immediate exploitation possible)
- Active SQL injection, XSS, command injection in changed code
- Exposed secrets/credentials that are actively used
- Authentication bypass in changed code

### HIGH (Significant security weakness)
- Missing auth check on a new endpoint (router level)
- Insecure cryptographic operations
- Sensitive data exposure

### MEDIUM (Security hardening)
- Missing rate limiting on a new endpoint
- Missing input size validation
- Verbose error messages leaking implementation details

### LOW (Best practices)
- Missing security headers
- Logging improvements
- Defense-in-depth recommendations

### INFO (Positive findings / Non-issues)
- Correct use of secure libraries
- Proper validation in place
- Good security practices observed

## DO NOT FLAG (Common False Positives)

1. **"No authentication on service function"** - Auth is at router level
2. **"No rate limiting on internal function"** - Rate limiting is at gateway
3. **"Unused session_manager parameter"** - May be intentional (future use)
4. **"BeautifulSoup uses html.parser"** - This is CORRECT, not a vulnerability
5. **"No input validation in service"** - Validation at Pydantic/router level
6. **"Missing CSRF token"** - Check if this is an API (stateless) vs web form
7. **"No HTTPS enforcement in code"** - This is server/infrastructure config

## Module-Specific Context

<!-- Add module-specific context below as needed -->

### web_vlc_checkout
- **Purpose**: Extract cart items from HTML checkout pages using GenAI
- **Auth**: Handled by calling router, not this service
- **Rate Limiting**: Handled at API gateway
- **Input**: HTML content passed from validated request
- **Output**: Structured cart items

This service processes HTML that has already passed through router-level
authentication and validation. Focus on:
- HTML sanitization effectiveness
- GenAI prompt injection risks
- DoS via malformed HTML

Do NOT focus on:
- Authentication (not this module's job)
- Rate limiting (not this module's job)
- Session management (not this module's job)
