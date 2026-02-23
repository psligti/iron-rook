"""
Risk changes fixture - evaluates diff scoper reviewer's ability to identify
high-risk changes in a diff that warrant extra review attention.
"""

# DIFF CONTENT (simulated for fixture)
DIFF_CONTENT = """
diff --git a/src/auth/login.py b/src/auth/login.py
index abc123..def456 100644
--- a/src/auth/login.py
+++ b/src/auth/login.py
@@ -15,7 +15,7 @@ def authenticate(username, password):
     user = db.query(User).filter(User.username == username).first()
     
     if user and user.verify_password(password):
-        return create_session(user.id)
+        return create_session(user.id, remember=True)  # LOW RISK: Added optional param
     return None

@@ -42,10 +42,12 @@ def create_session(user_id, remember=False):
     session = Session(
         user_id=user_id,
         token=generate_token(),
-        expires_at=datetime.now() + timedelta(days=1)
+        expires_at=datetime.now() + timedelta(days=30 if remember else 1)
     )
+    if remember:
+        session.persistent = True  # MEDIUM RISK: Long-lived session
     db.add(session)
     return session.token

diff --git a/src/api/routes.py b/src/api/routes.py
index 123abc..456def 100644
--- a/src/api/routes.py
+++ b/src/api/routes.py
@@ -8,6 +8,14 @@ from flask import request, jsonify
 @app.route('/api/users/<int:user_id>')
 def get_user(user_id):
     user = db.query(User).get(user_id)
+    # HIGH RISK: No authorization check added
+    # Anyone can access any user's data
     return jsonify(user.to_dict())
 
+@app.route('/api/admin/users', methods=['POST'])
+def create_user():
+    data = request.json
+    # HIGH RISK: No input validation
+    # HIGH RISK: No admin authorization check
+    user = User(**data)
+    db.add(user)
+    return jsonify(user.to_dict()), 201

diff --git a/src/db/queries.py b/src/db/queries.py
index aaa111..bbb222 100644
--- a/src/db/queries.py
+++ b/src/db/queries.py
@@ -25,7 +25,12 @@ def search_users(query):
     # ... existing code ...
     
 def get_user_by_email(email):
-    return db.query(User).filter(User.email == email).first()
+    # HIGH RISK: SQL injection vulnerability introduced
+    raw_sql = f"SELECT * FROM users WHERE email = '{email}'"
+    return db.execute(raw_sql).fetchone()

diff --git a/src/utils/cache.py b/src/utils/cache.py
index ccc333..ddd444 100644
--- a/src/utils/cache.py
+++ b/src/utils/cache.py
@@ -10,6 +10,8 @@ _cache = {}
 def get(key):
     return _cache.get(key)
 
+def clear_all():
+    _cache.clear()  # LOW RISK: Simple utility function

diff --git a/src/config.py b/src/config.py
index eee555..fff666 100644
--- a/src/config.py
+++ b/src/config.py
@@ -5,7 +5,8 @@ DEBUG = False
 DATABASE_URL = os.environ.get('DATABASE_URL')
 SECRET_KEY = os.environ.get('SECRET_KEY')
 
-ALLOWED_HOSTS = ['example.com']
+ALLOWED_HOSTS = ['*']  # HIGH RISK: Opens to all hosts
+DEBUG = True           # HIGH RISK: Debug enabled in what looks like production

diff --git a/src/payments/checkout.py b/src/payments/checkout.py
index ggg777..hhh888 100644
--- a/src/payments/checkout.py
+++ b/src/payments/checkout.py
@@ -50,6 +50,15 @@ def process_payment(amount, token):
     return charge
 
+def refund_payment(charge_id):
+    charge = get_charge(charge_id)
+    # MEDIUM RISK: No authorization - any user can refund
+    # MEDIUM RISK: No audit trail
+    stripe.Refund.create(charge=charge.stripe_id)
+    charge.status = 'refunded'
+    db.commit()
+    return {'status': 'refunded'}
+
 # Schema changes
diff --git a/migrations/001_add_user_fields.sql b/migrations/001_add_user_fields.sql
new file mode 100644
--- /dev/null
+++ b/migrations/001_add_user_fields.sql
@@ -0,0 +1,5 @@
+-- MEDIUM RISK: No index on frequently queried column
+ALTER TABLE users ADD COLUMN last_login TIMESTAMP;
+-- HIGH RISK: Dropping NOT NULL without default value
+ALTER TABLE users ALTER COLUMN email DROP NOT NULL;
+-- MEDIUM RISK: No backfill for new required column
+ALTER TABLE orders ADD COLUMN shipping_address TEXT NOT NULL;
"""


# RISK CATEGORIES FOR DIFF SCOPING
RISK_CATEGORIES = {
    "security": {
        "patterns": [
            r"password",
            r"auth",
            r"token",
            r"secret",
            r"api_key",
            r"encrypt",
            r"decrypt",
            r"permission",
            r"role",
            r"admin",
        ],
        "weight": 10,
    },
    "data_integrity": {
        "patterns": [
            r"DELETE",
            r"DROP",
            r"TRUNCATE",
            r"migration",
            r"ALTER TABLE",
            r"NOT NULL",
            r"FOREIGN KEY",
        ],
        "weight": 8,
    },
    "financial": {
        "patterns": [
            r"payment",
            r"charge",
            r"refund",
            r"invoice",
            r"billing",
            r"price",
            r"cost",
        ],
        "weight": 9,
    },
    "infrastructure": {
        "patterns": [
            r"config",
            r"DEBUG",
            r"ALLOWED_HOSTS",
            r"docker",
            r"kubernetes",
            r"deploy",
        ],
        "weight": 7,
    },
    "performance": {
        "patterns": [
            r"index",
            r"query",
            r"cache",
            r"async",
            r"thread",
            r"connection",
        ],
        "weight": 5,
    },
}


# Expected review findings:
# 1. HIGH RISK: SQL injection in get_user_by_email() - raw f-string query
# 2. HIGH RISK: No auth check on new create_user endpoint
# 3. HIGH RISK: No input validation on create_user
# 4. HIGH RISK: ALLOWED_HOSTS = ['*'] opens to all hosts
# 5. HIGH RISK: DEBUG = True enabled
# 6. HIGH RISK: Dropping NOT NULL on email without migration strategy
# 7. MEDIUM RISK: 30-day persistent sessions
# 8. MEDIUM RISK: No authorization on refund_payment
# 9. MEDIUM RISK: No audit trail for refunds
# 10. MEDIUM RISK: No index on last_login column
# 11. MEDIUM RISK: New NOT NULL column without backfill
# 12. LOW RISK: Added optional remember parameter
# 13. LOW RISK: Simple cache utility
