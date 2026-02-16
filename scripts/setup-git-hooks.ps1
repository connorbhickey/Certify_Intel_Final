# =============================================================================
# Certify Intel - Git Hooks Setup
# =============================================================================
# Installs pre-push hook to run tests before pushing to GitHub
# Usage: .\scripts\setup-git-hooks.ps1
# =============================================================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   CERTIFY INTEL - GIT HOOKS SETUP         " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Get repo root
$repoRoot = git rev-parse --show-toplevel 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Not in a git repository!" -ForegroundColor Red
    exit 1
}

$hooksDir = Join-Path $repoRoot ".git\hooks"

# Create hooks directory if it doesn't exist
if (-not (Test-Path $hooksDir)) {
    New-Item -ItemType Directory -Path $hooksDir -Force | Out-Null
}

# Create pre-push hook
$prePushHook = Join-Path $hooksDir "pre-push"
$prePushContent = @'
#!/bin/sh
# Certify Intel - Pre-Push Hook
# Runs local tests before allowing push to GitHub

echo ""
echo "Running pre-push tests..."
echo ""

# Get the repo root
REPO_ROOT=$(git rev-parse --show-toplevel)

# Run PowerShell test script
if command -v powershell &> /dev/null; then
    powershell -ExecutionPolicy Bypass -File "$REPO_ROOT/scripts/pre-push-tests.ps1"
elif command -v pwsh &> /dev/null; then
    pwsh -ExecutionPolicy Bypass -File "$REPO_ROOT/scripts/pre-push-tests.ps1"
else
    # Fallback: Run pytest directly
    echo "PowerShell not found, running pytest directly..."
    cd "$REPO_ROOT/backend"
    python -m pytest tests/ -v --tb=short
fi

# Check exit code
if [ $? -ne 0 ]; then
    echo ""
    echo "Pre-push tests FAILED! Push aborted."
    echo "Fix the errors and try again."
    echo ""
    exit 1
fi

exit 0
'@

# Write hook file
$prePushContent | Out-File -FilePath $prePushHook -Encoding utf8 -NoNewline

Write-Host "[1/2] Created pre-push hook" -ForegroundColor Green
Write-Host "      Location: $prePushHook" -ForegroundColor Gray

# Make hook executable (for Git Bash on Windows)
git update-index --chmod=+x $prePushHook 2>$null

Write-Host "[2/2] Hook made executable" -ForegroundColor Green

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   GIT HOOKS INSTALLED!                    " -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "From now on, tests will run automatically" -ForegroundColor White
Write-Host "before every 'git push' command." -ForegroundColor White
Write-Host ""
Write-Host "To bypass (not recommended):" -ForegroundColor Gray
Write-Host "  git push --no-verify" -ForegroundColor Gray
Write-Host ""
