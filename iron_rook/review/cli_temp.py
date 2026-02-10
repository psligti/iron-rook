async def log_verbose_todos(repo_root: str) -> None:
    """Log todo information from session storage if available.

    Args:
        repo_root: Repository root directory
    """
    _logger = ReviewLogger.get()

    if not _logger.verbose_logging_enabled():
        return

    try:
        from dawn_kestrel.storage.store import TodoStorage

        todo_storage = TodoStorage(Path(repo_root))
        session_id = "review-cli-session"

        todos = await todo_storage.get_todos(session_id)

        if todos:
            _logger.logger.info("")
            _logger.logger.info("[VERBOSE] ===== TODO LIST =====")
            _logger.logger.info(f"[VERBOSE] Total todos: {len(todos)}")

            completed_count = sum(1 for t in todos if t.get("state") == "completed")
            in_progress_count = sum(1 for t in todos if t.get("state") == "in_progress")
            pending_count = sum(1 for t in todos if t.get("state") == "pending")

            _logger.logger.info(f"[VERBOSE]   Completed: {completed_count}")
            _logger.logger.info(f"[VERBOSE]   In Progress: {in_progress_count}")
            _logger.logger.info(f"[VERBOSE]   Pending: {pending_count}")

            for idx, todo in enumerate(todos, 1):
                state = todo.get("state", "unknown")
                priority = todo.get("priority", "medium")
                description = todo.get("description", "")

                _logger.logger.info("[VERBOSE]")
                _logger.logger.info(f"[VERBOSE]   #{idx} [{state.upper()}] [{priority.upper()}]")
                _logger.logger.info(
                    f"[VERBOSE]       {description[:150]}{'...' if len(description) > 150 else ''}"
                )

                if todo.get("created_at"):
                    _logger.logger.info(f"[VERBOSE]       Created: {todo['created_at']}")
                if todo.get("due_date"):
                    _logger.logger.info(f"[VERBOSE]       Due: {todo['due_date']}")

            _logger.logger.info("[VERBOSE] ===== END TODO LIST =====")
            _logger.logger.info("")
        else:
            _logger.logger.info("[VERBOSE] No todos found in session storage")

    except Exception as e:
        _logger.logger.warning(f"[VERBOSE] Could not retrieve todos: {e}")
