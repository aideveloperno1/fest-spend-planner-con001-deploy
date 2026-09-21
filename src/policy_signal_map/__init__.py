def main() -> None:
    """로컬 실행: uv run policy-signal-map. 시작 전에 공개 근거 파일 상태를 확인한다."""
    import uvicorn

    from .web.evidence_state import get_evidence_state

    state = get_evidence_state()
    if state.blocked:
        raise SystemExit("\n".join(state.errors))
    for message in state.errors:
        print(f"[근거 파일] {message}")

    uvicorn.run("policy_signal_map.app:app", host="127.0.0.1", port=8000, reload=True)
