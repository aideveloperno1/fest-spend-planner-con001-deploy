def main() -> None:
    """로컬 실행: uv run policy-signal-map

    서버를 켜기 전에 근거 파일 상태를 확인한다. 실제 분석 자료와 클라우드 LLM이 함께 설정돼 있으면 시작하지 않는다.
    """
    import uvicorn

    from .web.evidence_state import get_evidence_state

    state = get_evidence_state()
    if state.blocked:
        raise SystemExit("\n".join(state.errors))
    for message in state.errors:
        print(f"[근거 파일] {message}")

    uvicorn.run("policy_signal_map.app:app", host="127.0.0.1", port=8000, reload=True)
