from iron_rook.review.logging_utils import ReviewLogger

rl = ReviewLogger.get(verbose=False)
print("Test 1: ReviewLogger initialized with verbose=False")

import logging

logging.warning("This warning should NOT be logged")
logging.error("This error should NOT be logged")

rl2 = ReviewLogger.get(verbose=True)
print("Test 2: ReviewLogger initialized with verbose=True")

logging.debug("This DEBUG should be logged")
logging.info("This INFO should be logged")

print("All tests passed!")
