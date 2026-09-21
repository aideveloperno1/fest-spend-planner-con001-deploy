"""제출·사용법용 화면 캡처를 다시 만든다 (docs/screenshots/README.md 이름 규칙).

실행: uv run python scripts/capture_screenshots.py            (AI 참고 의견 포함, Ollama 필요)
      uv run python scripts/capture_screenshots.py --no-ai    (AI 영역 없이)

- 합성 근거 파일로만 찍는다. 셸의 PSM_ 환경변수를 모두 비우고 서버를 따로 띄우며,
  캡처 전마다 상단 표시가 "시연용 합성 수치"인지 확인하고 아니면 멈춘다 (실제 수치 화면이 공개 저장소에 들어가지 않게).
- 사용자 Chrome과 분리된 임시 프로필의 창 없는 Chrome을 Chrome DevTools Protocol로 조작한다. 가로 1440px PNG.
- 전체 페이지는 화면 높이를 페이지 높이로 먼저 키우고 기다린 뒤 찍는다. 캡처 옵션으로 화면 밖까지 한 번에 찍으면
  찍는 순간 차트가 다시 그려져 막대·선이 왼쪽에 뭉친 채 찍혔다 (2026-09-17 확인).
- websockets는 uvicorn[standard]와 함께 설치된 패키지를 쓴다 (실행 의존성을 따로 늘리지 않음).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

try:
    import websockets
except ImportError:  # pragma: no cover - 설치 환경 안내
    raise SystemExit("websockets 패키지가 없습니다. 저장소에서 `uv sync`를 실행한 뒤 다시 시도하세요.") from None

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "screenshots"
CHROME_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
)
WIDTH, HEIGHT = 1440, 900
SYNTHETIC_BADGE = "시연용 합성 수치"
DEFAULT_MODELS = "gemma4:26b-a4b-it-qat,exaone3.5:7.8b,exaone3.5:7.8b-instruct-q8_0"
# 4단계 캡처에 넣는 예시 입력 (사용자 확인 2026-09-17)
OPTION_A_INPUT = {
    "collect_items": "쿠폰 사용 실적, 참여 점포 정산 자료",
    "availability": "negotiating",
    "owner": "관광정책과",
    "cycle": "월 1회",
}
# 상단 고정 바 높이만큼 띄워서 스크롤한다 (카드 머리가 바에 가려지지 않게)
TOPBAR_OFFSET = 130
R07_FORM = "document.querySelector('form.choice-form input[name=question_key][value=R07]').form"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_http(url: str, what: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)  # noqa: S310
            return
        except Exception:
            time.sleep(0.2)
    raise SystemExit(f"{what}이(가) 시작되지 않았습니다: {url}")


def start_server(**env_values: str) -> tuple[subprocess.Popen, str]:
    """합성 근거로 서비스를 띄운다. 셸에 실제 파일 경로가 있어도 쓰지 않도록 PSM_ 변수를 모두 지운다."""
    port = _free_port()
    env = {key: value for key, value in os.environ.items() if not key.startswith("PSM_")}
    env.update(env_values)
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "policy_signal_map.app:app", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    _wait_http(base + "/step/1", "서비스")
    return process, base


class Page:
    """창 없는 Chrome 한 탭. 필요한 명령만 감쌌다."""

    def __init__(self, chrome: str) -> None:
        self.chrome = chrome
        self.events: list[dict] = []
        self.console_errors: list[str] = []
        self._id = 0

    async def __aenter__(self) -> Page:
        port = _free_port()
        self.profile = tempfile.mkdtemp(prefix="psm_capture_")
        self.process = subprocess.Popen(
            [self.chrome, "--headless=new", f"--remote-debugging-port={port}", f"--user-data-dir={self.profile}",
             "--no-first-run", "--hide-scrollbars", "about:blank"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_http(f"http://127.0.0.1:{port}/json/version", "Chrome")
        targets = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5).read())  # noqa: S310
        target = next(t for t in targets if t["type"] == "page")
        self.ws = await websockets.connect(target["webSocketDebuggerUrl"], max_size=100_000_000)
        for domain in ("Page.enable", "Runtime.enable", "Log.enable"):
            await self.send(domain)
        await self.viewport(WIDTH, HEIGHT)
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.ws.close()
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
        shutil.rmtree(self.profile, ignore_errors=True)

    def _record(self, message: dict) -> None:
        method = message.get("method")
        if not method:
            return
        self.events.append(message)
        params = message.get("params", {})
        if method == "Runtime.exceptionThrown":
            self.console_errors.append(params.get("exceptionDetails", {}).get("text", ""))
        elif method == "Log.entryAdded" and params.get("entry", {}).get("level") == "error":
            self.console_errors.append(params["entry"].get("text", ""))

    async def send(self, method: str, **params: object) -> dict:
        self._id += 1
        my_id = self._id
        await self.ws.send(json.dumps({"id": my_id, "method": method, "params": params}))
        while True:
            message = json.loads(await self.ws.recv())
            if message.get("id") == my_id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})
            self._record(message)

    async def _wait_event(self, name: str, timeout: float = 30) -> None:
        start = len(self.events)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if any(event.get("method") == name for event in self.events[start:]):
                return
            try:
                self._record(json.loads(await asyncio.wait_for(self.ws.recv(), timeout=0.5)))
            except TimeoutError:
                pass
        raise TimeoutError(name)

    async def viewport(self, width: int, height: int) -> None:
        await self.send("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=False)

    async def js(self, expression: str) -> object:
        result = await self.send("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in result:
            raise RuntimeError("페이지 스크립트 실행 실패: " + json.dumps(result["exceptionDetails"], ensure_ascii=False)[:300])
        return result.get("result", {}).get("value")

    async def go(self, url: str, settle: float = 1.0) -> None:
        self.events.clear()
        await self.send("Page.navigate", url=url)
        await self._wait_event("Page.loadEventFired")
        await asyncio.sleep(settle)

    async def click_and_load(self, element_js: str, settle: float = 1.0) -> None:
        self.events.clear()
        await self.send("Runtime.evaluate", expression=f"({element_js}).click()")
        await self._wait_event("Page.loadEventFired")
        await asyncio.sleep(settle)

    async def capture(self, path: Path, *, full_page: bool) -> tuple[int, int]:
        """full_page가 아니면 지금 화면 크기 그대로 찍는다. 찍은 뒤 화면 크기를 기본값으로 되돌린다."""
        badge = await self.js("document.querySelector('[data-evidence-badge]')?.textContent || ''")
        if SYNTHETIC_BADGE not in str(badge):
            raise SystemExit(f"상단 표시가 '{SYNTHETIC_BADGE}'가 아니어서 캡처를 멈춥니다: {badge!r}")
        if full_page:
            height = int(await self.js("document.documentElement.scrollHeight"))
            await self.viewport(WIDTH, height)
            await self.js("window.scrollTo(0, 0)")
            await asyncio.sleep(3)  # 차트가 새 크기로 다시 그려질 시간
        shot = await self.send("Page.captureScreenshot", format="png")
        await self.viewport(WIDTH, HEIGHT)
        path.write_bytes(base64.b64decode(shot["data"]))
        return struct.unpack(">II", path.read_bytes()[16:24])


async def start_review(page: Page, base: str) -> None:
    await page.go(base + "/step/1")
    await page.click_and_load("document.querySelector('button[value=sample]')")


async def capture_landing(page: Page, base: str, out: Path, saved: list[str]) -> None:
    """랜딩 화면. ?motion=off로 연다 — 등장 효과가 켜져 있으면 아직 나타나지 않은 구역이
    빈 칸으로 찍힌다 (2026-09-17에 차트가 다시 그려져 막대가 뭉친 채 찍힌 것과 같은 함정)."""
    await page.go(base + "/?motion=off", settle=1.5)
    saved.append(f"00_landing.png {await page.capture(out / '00_landing.png', full_page=True)}")


async def capture_main_flow(page: Page, base: str, out: Path, saved: list[str]) -> None:
    await start_review(page, base)
    saved.append(f"01_input_sample.png {await page.capture(out / '01_input_sample.png', full_page=True)}")

    await page.click_and_load("document.querySelector('button[value=submit]')", settle=2.5)
    saved.append(f"02_evidence_region.png {await page.capture(out / '02_evidence_region.png', full_page=True)}")

    await page.js(f"""(() => {{ const d = document.querySelector('details.hold-examples'); d.open = true;
        d.scrollIntoView(); window.scrollBy(0, -{TOPBAR_OFFSET}); }})()""")
    await asyncio.sleep(0.5)
    saved.append(f"02_evidence_hold.png {await page.capture(out / '02_evidence_hold.png', full_page=False)}")

    await page.go(base + "/step/4")
    await page.viewport(WIDTH, 1300)
    await page.js(f"""(() => {{
        const f = {R07_FORM};
        const pick = (name, value) => {{ const i = f.querySelector(`input[name=${{name}}][value=${{value}}]`);
            i.checked = true; i.dispatchEvent(new Event('change', {{bubbles: true}})); }};
        pick('decision', 'adopt'); pick('option_id', 'A');
        const input = {json.dumps(OPTION_A_INPUT, ensure_ascii=False)};
        f.querySelector('textarea[name=collect_items]').value = input.collect_items;
        f.querySelector('select[name=availability]').value = input.availability;
        f.querySelector('input[name=owner]').value = input.owner;
        f.querySelector('input[name=cycle]').value = input.cycle;
        f.closest('.card').scrollIntoView(); window.scrollBy(0, -{TOPBAR_OFFSET});
    }})()""")
    await asyncio.sleep(0.5)
    saved.append(f"04_choices_option_a.png {await page.capture(out / '04_choices_option_a.png', full_page=False)}")

    await page.click_and_load(f"[...{R07_FORM}.querySelectorAll('button[type=submit]')].find(b => !b.getAttribute('formaction'))")
    await page.click_and_load("[...document.querySelectorAll('a')].find(a => a.textContent.includes('보완 기획안 만들기'))")
    if await page.js("location.pathname") != "/step/5":
        raise SystemExit("5단계로 가지 못했습니다. 4단계 저장을 확인하세요.")
    saved.append(f"05_draft_compare.png {await page.capture(out / '05_draft_compare.png', full_page=True)}")


async def capture_questions(page: Page, base: str, out: Path, saved: list[str], *, with_ai: bool) -> None:
    await start_review(page, base)
    await page.click_and_load("document.querySelector('button[value=submit]')")
    await page.go(base + "/step/3")
    if with_ai:
        started = time.time()
        while time.time() - started < 200:
            state = await page.js("""({n: document.querySelectorAll('.ai-opinion').length,
                msg: document.querySelector('[data-ai-message]')?.hidden ? '' : (document.querySelector('[data-ai-message]')?.textContent || '')})""")
            if state["n"] or "확인하는 중" not in state["msg"]:
                break
            await asyncio.sleep(2)
        opinions = await page.js("[...document.querySelectorAll('.ai-opinion')].map(p => p.firstChild.textContent)")
        if not opinions:
            raise SystemExit(f"AI 참고 의견을 받지 못했습니다({state['msg']!r}). Ollama 실행과 모델을 확인하거나 --no-ai로 찍으세요.")
        print("AI 참고 의견 (캡처에 들어간 문장):")
        for line in opinions:
            print("  -", line)
    saved.append(f"03_questions.png {await page.capture(out / '03_questions.png', full_page=True)}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="제출·사용법용 화면 캡처 (합성 자료)")
    parser.add_argument("--chrome", default=next((c for c in CHROME_CANDIDATES if Path(c).exists()), None),
                        help="Chrome 또는 Edge 실행 파일 경로")
    parser.add_argument("--no-ai", action="store_true", help="3단계를 AI 참고 의견 없이 찍는다")
    parser.add_argument("--models", default=DEFAULT_MODELS, help="3단계에 보일 모델 목록 (첫 모델로 의견을 받는다)")
    parser.add_argument("--ollama", default="http://127.0.0.1:11434/v1", help="OpenAI 호환 로컬 LLM 주소")
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    if not args.chrome:
        raise SystemExit("Chrome 실행 파일을 찾지 못했습니다. --chrome으로 경로를 지정하세요.")
    args.out.mkdir(parents=True, exist_ok=True)

    saved: list[str] = []
    errors: list[str] = []

    server, base = start_server()
    try:
        async with Page(args.chrome) as page:
            await capture_landing(page, base, args.out, saved)
            await capture_main_flow(page, base, args.out, saved)
            if args.no_ai:
                await capture_questions(page, base, args.out, saved, with_ai=False)
            errors += page.console_errors
    finally:
        server.terminate()

    if not args.no_ai:
        server, base = start_server(PSM_LLM_PROVIDER="local", PSM_LLM_BASE_URL=args.ollama, PSM_LLM_MODELS=args.models)
        try:
            async with Page(args.chrome) as page:
                await capture_questions(page, base, args.out, saved, with_ai=True)
                errors += page.console_errors
        finally:
            server.terminate()

    print("저장:", args.out)
    for line in saved:
        print("  ", line)
    if errors:
        print("콘솔 오류:", errors)
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
