from pathlib import Path

PACKAGE_DIR = Path(__file__).parent
PROJECT_ROOT = PACKAGE_DIR.parent.parent
RESOURCES_DIR = PACKAGE_DIR / "resources"
WEB_DIR = PACKAGE_DIR / "web"
# 저장소 뿌리의 docs/ — 랜딩 화면이 캡처를 /shots 주소로 읽는다 (복사하지 않는다)
DOCS_DIR = PROJECT_ROOT / "docs"
