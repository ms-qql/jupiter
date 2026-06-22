"""Parser-Unit-Tests gegen den REAL verifizierten Event-Vertrag (Live-Spike)."""
from __future__ import annotations

from app.engine.events import (
    extract_rate_limit,
    extract_text,
    extract_usage,
    is_error_result,
    parse_line,
)

INIT = '{"type":"system","subtype":"init","session_id":"abc","model":"claude-haiku-4-5-20251001","permissionMode":"default","apiKeySource":"none"}'
ASSISTANT = '{"type":"assistant","message":{"content":[{"type":"text","text":"OK"}],"usage":{"input_tokens":10,"cache_creation_input_tokens":18772,"cache_read_input_tokens":17506,"output_tokens":8}},"session_id":"abc"}'
RESULT = '{"type":"result","subtype":"success","is_error":false,"num_turns":1,"result":"OK","session_id":"abc","total_cost_usd":0.0396646,"usage":{"input_tokens":10,"cache_creation_input_tokens":18772,"cache_read_input_tokens":17506,"output_tokens":72},"modelUsage":{"claude-haiku-4-5-20251001":{"contextWindow":200000,"maxOutputTokens":32000}}}'
RATE = '{"type":"rate_limit_event","rate_limit_info":{"status":"allowed","resetsAt":1782165000,"rateLimitType":"five_hour"}}'


def test_parse_line_blank_and_garbage_return_none():
    assert parse_line("") is None
    assert parse_line("   ") is None
    assert parse_line("not json at all") is None
    assert parse_line('{"no":"type"}') is None


def test_parse_init_event():
    ev = parse_line(INIT)
    assert ev is not None
    assert ev.type == "system" and ev.subtype == "init"
    assert ev.session_id == "abc"
    assert ev.raw["apiKeySource"] == "none"  # Subscription-Auth, kein API-Key


def test_extract_text():
    ev = parse_line(ASSISTANT)
    assert extract_text(ev) == "OK"


def test_extract_usage_and_context_fill():
    ev = parse_line(RESULT)
    usage = extract_usage(ev)
    assert usage is not None
    # 10 + 17506 + 18772 = 36288 von 200000 → 18.1 %
    assert usage.context_used_tokens == 36288
    assert usage.context_fill_pct == 18.1
    assert usage.billed_tokens == 82
    assert usage.total_cost_usd == 0.0396646
    assert usage.context_window == 200000


def test_result_not_error():
    assert is_error_result(parse_line(RESULT)) is False


def test_extract_rate_limit():
    info = extract_rate_limit(parse_line(RATE))
    assert info is not None
    assert info["rateLimitType"] == "five_hour"


def test_classify_exit_clean_and_error():
    from app.engine.claude_driver import classify_exit

    # Sauberer Abschluss.
    assert classify_exit(0, stopping=False).subtype == "closed"
    assert classify_exit(None, stopping=False).subtype == "closed"
    # Von uns gestoppt (SIGTERM → -15) ist KEIN Fehler.
    assert classify_exit(-15, stopping=True).subtype == "closed"
    # Unerwarteter Crash.
    ev = classify_exit(1, stopping=False, stderr="boom")
    assert ev.subtype == "error" and ev.raw["message"] == "boom"
    # Unerwartetes Signal ohne Stop-Anforderung → Fehler.
    assert classify_exit(-9, stopping=False).subtype == "error"
