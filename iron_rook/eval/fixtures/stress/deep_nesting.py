"""
Edge case: Deeply nested code.

STRESS TEST: Tests AST parsing depth, recursion handling, complexity analysis.
EXPECTED BEHAVIOR:
- Should handle deep nesting without stack overflow
- Should detect complexity issues
- Should NOT crash on parsing
"""

from typing import Any, Optional


def deeply_nested_function(data: dict, depth: int = 0) -> Optional[Any]:
    if depth > 50:
        return None

    if "level1" in data:
        if "level2" in data["level1"]:
            if "level3" in data["level1"]["level2"]:
                if "level4" in data["level1"]["level2"]["level3"]:
                    if "level5" in data["level1"]["level2"]["level3"]["level4"]:
                        if "level6" in data["level1"]["level2"]["level3"]["level4"]["level5"]:
                            if (
                                "level7"
                                in data["level1"]["level2"]["level3"]["level4"]["level5"]["level6"]
                            ):
                                if (
                                    "level8"
                                    in data["level1"]["level2"]["level3"]["level4"]["level5"][
                                        "level6"
                                    ]["level7"]
                                ):
                                    if (
                                        "level9"
                                        in data["level1"]["level2"]["level3"]["level4"]["level5"][
                                            "level6"
                                        ]["level7"]["level8"]
                                    ):
                                        if (
                                            "level10"
                                            in data["level1"]["level2"]["level3"]["level4"][
                                                "level5"
                                            ]["level6"]["level7"]["level8"]["level9"]
                                        ):
                                            return deeply_nested_function(
                                                data["level1"]["level2"]["level3"]["level4"][
                                                    "level5"
                                                ]["level6"]["level7"]["level8"]["level9"][
                                                    "level10"
                                                ],
                                                depth + 1,
                                            )
    return data


class DeepNestingClass:
    def outer_method(self):
        def inner1():
            def inner2():
                def inner3():
                    def inner4():
                        def inner5():
                            def inner6():
                                def inner7():
                                    def inner8():
                                        def inner9():
                                            def inner10():
                                                return "deeply nested result"

                                            return inner10()

                                        return inner9()

                                    return inner8()

                                return inner7()

                            return inner6()

                        return inner5()

                    return inner4()

                return inner3()

            return inner2()

        return inner1()


class Level1:
    class Level2:
        class Level3:
            class Level4:
                class Level5:
                    class Level6:
                        class Level7:
                            class Level8:
                                class Level9:
                                    class Level10:
                                        value = "deeply nested class"

                                    def method(self):
                                        return self.Level10.value

                                def method(self):
                                    return self.Level10().method()

                            def method(self):
                                return self.Level10().method()

                        def method(self):
                            return self.Level10().method()

                    def method(self):
                        return self.Level10().method()

                def method(self):
                    return self.Level10().method()

            def method(self):
                return self.Level10().method()

        def method(self):
            return self.Level10().method()

    def method(self):
        return self.Level10().method()


# Expected review findings:
# 1. Cyclomatic complexity too high (deep nesting)
# 2. Cognitive complexity issues
# 3. Should be refactored to reduce nesting
# 4. Potential stack overflow with recursive calls
# 5. Hard to test/maintain
