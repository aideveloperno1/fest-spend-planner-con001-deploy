param(
    [switch]$NoLlm
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$env:UV_PROJECT_ENVIRONMENT = Join-Path $PSScriptRoot ".venv"
$env:PSM_EVIDENCE_PATH = Join-Path $PSScriptRoot "src\policy_signal_map\resources\evidence\review_evidence_hierarchy_v1.json"
$env:PSM_SESSION_BACKEND = "memory"
Remove-Item Env:PSM_REGION_MAPPING_PATH -ErrorAction SilentlyContinue

if ($NoLlm) {
    $env:PSM_LLM_PROVIDER = "none"
    Remove-Item Env:PSM_LLM_MODELS -ErrorAction SilentlyContinue
    Remove-Item Env:PSM_LLM_MODEL -ErrorAction SilentlyContinue
} else {
    if ([string]::IsNullOrWhiteSpace($env:GEMINI_API_KEY)) {
        throw "GEMINI_API_KEY 환경변수에 Google AI Studio API 키를 설정하세요. 키는 파일이나 Git에 저장하지 마세요."
    }
    $env:PSM_LLM_PROVIDER = "google_ai"
    $env:PSM_LLM_MODELS = "gemini-3.8-flash,gemini-3.6-flash,gemini-2.5-pro,gemma-4-31b-it"
    $env:PSM_LLM_MODEL = "gemini-3.8-flash"
    $env:PSM_LLM_TIMEOUT_S = "45"
}

uv sync --frozen
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
uv run policy-signal-map
