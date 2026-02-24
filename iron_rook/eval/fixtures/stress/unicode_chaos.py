"""
Edge case: Unicode and special characters.

STRESS TEST: Tests encoding handling, string parsing, display issues.
EXPECTED BEHAVIOR:
- Should handle unicode without crashing
- Should detect issues regardless of character encoding
- Should NOT produce garbled output
"""

# Unicode identifiers (valid in Python 3)
变量 = "chinese variable"
変数 = "japanese variable"
переменная = "russian variable"
variable_café = "accented"
emoji_var = "🎉🎊💼"


def función_con_acentos(nombre: str, año: int) -> dict:
    análisis = f"Análisis de {nombre} en {año}"
    return {
        "nombre": nombre,
        "año": año,
        "análisis": análisis,
        "estado": "completado ✓",
        "código": "UTF-8 ™",
    }


class Café:
    def __init__(self, nombre: str):
        self.nombre = nombre
        self.menu = {
            "café": "☕",
            "thé": "🍵", 
            "bière": "🍺",
            "sake": "🍶",
        }
    
    def commander(self, article: str) -> str:
        if article in self.menu:
            return f"Voici votre {article}: {self.menu[article]}"
        return "Désolé, article non disponible ❌"


# Zero-width characters (could hide malicious code)
hidden = "normal" + "\u200b" + "text"  # zero-width space
hidden2 = "start\ufeffend"  # BOM character

# Special string content
sql_with_unicode = "SELECT * FROM users WHERE name = 'François' AND role = 'admin'"
xss_test = "<script>alert('XSS 测试 测试')</script>"
emoji_sql = "SELECT * FROM 🎉 WHERE status = '✅'"


# Mathematical symbols (looks like operators but aren't)
x = 5 × 3  # multiplication sign, not asterisk
y = 10 ÷ 2  # division sign, not slash
z = 2 − 1  # minus sign, not hyphen


# RTL override (could make code display differently)
rtl_test = "Hello \u202e World"  # RTL override


# Homoglyphs (characters that look like others)
# Cyrillic 'а' looks like Latin 'a'
fаlse = True  # Cyrillic 'а', not Latin
clаss = "fake keyword"


def confusing_function():
    # Greek question mark looks like semicolon
    if True; print("This uses Greek question mark")
    
    # Cyrillic in identifiers
    рrint("This uses Cyrillic 'р' not Latin 'p'")
    
    return "confusing"


# Expected review findings:
# 1. Non-ASCII identifiers may cause confusion
# 2. Zero-width characters could be security concern
# 3. RTL override is potential security issue
# 4. Homoglyphs are potential security concern
# 5. Unicode in SQL/XSS may affect detection
# 6. Mathematical symbols instead of operators (syntax issue)
