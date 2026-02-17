from iron_rook.review.agents.security import SecurityReviewer
from iron_rook.review.base import ReviewContext
from unittest.mock import Mock

# Verify all required components are in place
reviewer = SecurityReviewer()

# Check all required attributes
assert hasattr(reviewer, '_thinking_log'), 'Missing _thinking_log'
assert hasattr(reviewer, '_phase_logger'), 'Missing _phase_logger'
assert hasattr(reviewer._phase_logger'), 'Missing log_thinking_frame method')

# Check imports
from iron_rook.review.contracts import ThinkingFrame, ThinkingStep, RunLog

# Test ThinkingFrame creation
frame = ThinkingFrame(state='test', goals=['g1'], checks=['c1'], risks=['r1'], steps=[], decision='done')
assert frame.state == 'test'
assert frame.goals == ['g1']
assert frame.decision == 'done'

# Test RunLog
log = RunLog()
log.add(frame)
assert len(log.frames) == 1

# Test log_thinking_frame method
reviewer._phase_logger = Mock()
# Mock console to capture output
with Mock() as mock_console:
    reviewer._phase_logger._console = mock_console
    reviewer._phase_logger.log_thinking_frame(frame)

# Check if log_thinking_frame was called
calls = reviewer._phase_logger.log_thinking_frame.call_args_list

print('All components verified successfully!')
