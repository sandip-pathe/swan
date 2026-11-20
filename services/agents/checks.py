"""Public, fixed explanations for recorded agent-stage checks."""

FAILURES = {
    "AI_UNKNOWN_OR_MISSING_EVIDENCE": "Market citations were missing or did not match the supplied evidence.",
    "AI_UNKNOWN_NEWS_CITATION": "A news citation did not match the supplied headlines.",
    "AI_INVALID_WAIT": "A wait proposal contained execution fields.",
    "AI_INCOMPLETE_PROPOSAL": "The proposal was missing required execution fields.",
    "AI_UNSUPPORTED_INSTRUMENT": "The proposed contract did not match the cited evidence.",
    "AI_OPTION_DIRECTION_MISMATCH": "The proposal direction did not match the contract.",
    "AI_REVIEW_MISSING_EVIDENCE": "The review did not cover every proposal citation.",
    "AI_STRATEGY_EXPIRED": "The evidence-based strategy lifetime had expired.",
    "AI_DAILY_TOKEN_BUDGET": "The daily analysis allowance was exhausted.",
    "AI_RESPONSE_UNAVAILABLE_OR_INVALID": "The response was unavailable or invalid.",
    "AI_INCOMPLETE": "The provider response was incomplete.",
    "AI_REFUSED": "The provider declined the request.",
    "AI_CONTEXT_TOO_LARGE": "The request exceeded the context limit.",
    "AI_RESPONSE_TOO_LARGE": "The response exceeded the size limit.",
    "INVALID_RESPONSE": "The response failed format or contract checks.",
    "INTERRUPTED": "The stage was interrupted before its checks completed.",
    "UNAVAILABLE": "The stage could not complete its checks.",
}
