# =============================================================================
# Certify Intel - Pre-Push Local Tests
# =============================================================================
# MANDATORY: Run this script before pushing to GitHub
# Usage: .\scripts\pre-push-tests.ps1
# =============================================================================

param(
    [switch]$SkipTests,
    [switch]$SkipLint,
    [switch]$Verbose
)

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   CERTIFY INTEL - PRE-PUSH TESTS          " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$ErrorCount = 0
$StartTime = Get-Date

# -----------------------------------------------------------------------------
# Step 1: Check Python environment
# -----------------------------------------------------------------------------
Write-Host "[1/4] Checking Python environment..." -ForegroundColor Yellow

$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Python not found!" -ForegroundColor Red
    $ErrorCount++
} else {
    Write-Host "  Found: $pythonVersion" -ForegroundColor Green
}

# -----------------------------------------------------------------------------
# Step 2: Install test dependencies (if needed)
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/4] Checking test dependencies..." -ForegroundColor Yellow

$testDeps = @("pytest", "pytest-asyncio", "flake8")
foreach ($dep in $testDeps) {
    $installed = pip show $dep 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Installing $dep..." -ForegroundColor Gray
        pip install $dep --quiet
    } else {
        Write-Host "  Found: $dep" -ForegroundColor Green
    }
}

# -----------------------------------------------------------------------------
# Step 3: Run linting (flake8)
# -----------------------------------------------------------------------------
if (-not $SkipLint) {
    Write-Host ""
    Write-Host "[3/4] Running code quality checks (flake8)..." -ForegroundColor Yellow

    Push-Location backend

    # Critical errors only (syntax errors, undefined names)
    $flakeResult = python -m flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  CRITICAL ERRORS FOUND:" -ForegroundColor Red
        Write-Host $flakeResult -ForegroundColor Red
        $ErrorCount++
    } else {
        Write-Host "  No critical errors" -ForegroundColor Green
    }

    # Style warnings (non-blocking)
    if ($Verbose) {
        Write-Host "  Running style checks..." -ForegroundColor Gray
        python -m flake8 . --count --exit-zero --max-complexity=10 --max-line-length=120 --statistics
    }

    Pop-Location
} else {
    Write-Host ""
    Write-Host "[3/4] Skipping lint checks (--SkipLint)" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# Step 4: Run unit tests
# -----------------------------------------------------------------------------
if (-not $SkipTests) {
    Write-Host ""
    Write-Host "[4/4] Running unit tests..." -ForegroundColor Yellow

    Push-Location backend

    # Set test environment
    $env:SECRET_KEY = "test-secret-key"
    $env:DATABASE_URL = "sqlite:///./test.db"

    # Run pytest
    $testResult = python -m pytest tests/ -v --tb=short 2>&1
    $testExitCode = $LASTEXITCODE

    if ($Verbose) {
        Write-Host $testResult
    }

    if ($testExitCode -ne 0) {
        Write-Host "  TESTS FAILED!" -ForegroundColor Red
        if (-not $Verbose) {
            Write-Host "  Run with -Verbose to see full output" -ForegroundColor Gray
        }
        $ErrorCount++
    } else {
        # Count passed tests
        $passedCount = ($testResult | Select-String "passed").Count
        Write-Host "  All tests passed!" -ForegroundColor Green
    }

    # Cleanup test database
    if (Test-Path "test.db") {
        Remove-Item "test.db" -Force
    }

    Pop-Location
} else {
    Write-Host ""
    Write-Host "[4/4] Skipping tests (--SkipTests)" -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
$Duration = (Get-Date) - $StartTime

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan

if ($ErrorCount -eq 0) {
    Write-Host "   ALL CHECKS PASSED!                      " -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Ready to push to GitHub." -ForegroundColor White
    Write-Host "Duration: $($Duration.TotalSeconds.ToString('F1')) seconds" -ForegroundColor Gray
    Write-Host ""
    exit 0
} else {
    Write-Host "   $ErrorCount ERROR(S) FOUND!              " -ForegroundColor Red
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Fix the errors above before pushing." -ForegroundColor Red
    Write-Host "Duration: $($Duration.TotalSeconds.ToString('F1')) seconds" -ForegroundColor Gray
    Write-Host ""
    exit 1
}
