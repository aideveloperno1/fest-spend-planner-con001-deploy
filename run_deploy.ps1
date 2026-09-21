param(
    [switch]$NoLlm
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$env:UV_PROJECT_ENVIRONMENT = Join-Path $PSScriptRoot ".venv"
$env:PSM_EVIDENCE_PATH = Join-Path $PSScriptRoot "src\policy_signal_map\resources\evidence\review_evidence_public_v2.1.json"
Remove-Item Env:PSM_REGION_MAPPING_PATH -ErrorAction SilentlyContinue

if ($NoLlm) {
    $env:PSM_LLM_PROVIDER = "none"
    Remove-Item Env:PSM_LLM_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:PSM_LLM_MODELS -ErrorAction SilentlyContinue
    Remove-Item Env:PSM_LLM_MODEL -ErrorAction SilentlyContinue
} else {
    $env:PSM_LLM_PROVIDER = "local"
    $env:PSM_LLM_BASE_URL = "http://127.0.0.1:11434/v1"
    $env:PSM_LLM_MODELS = "exaone3.5:7.8b"
    $env:PSM_LLM_MODEL = "exaone3.5:7.8b"
    $env:PSM_LLM_TIMEOUT_S = "120"
}

uv sync --frozen
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
uv run policy-signal-map
