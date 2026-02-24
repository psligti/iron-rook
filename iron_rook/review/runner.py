from __future__ import annotations

from typing import Any

from dawn_kestrel.core.harness import SimpleReviewAgentRunner as DawnKestrelSimpleReviewAgentRunner
from dawn_kestrel.llm.evidence_sharing import (
    EvidenceSharingStrategy,
    HashMapEvidenceSharingStrategy,
)

_SHARED_EVIDENCE_SHARING_STRATEGY = HashMapEvidenceSharingStrategy(max_entries=2000)


class SimpleReviewAgentRunner(DawnKestrelSimpleReviewAgentRunner):
    def __init__(
        self,
        agent_name: str,
        allowed_tools: list[str] | None = None,
        temperature: float = 0.3,
        top_p: float = 0.9,
        max_retries: int = 2,
        timeout_seconds: float = 120.0,
        evidence_sharing_strategy: EvidenceSharingStrategy | None = None,
        **kwargs: Any,
    ):
        strategy = evidence_sharing_strategy or _SHARED_EVIDENCE_SHARING_STRATEGY
        super().__init__(
            agent_name=agent_name,
            allowed_tools=allowed_tools,
            temperature=temperature,
            top_p=top_p,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            evidence_sharing_strategy=strategy,
            **kwargs,
        )
