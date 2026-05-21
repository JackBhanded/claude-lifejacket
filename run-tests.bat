@echo off
REM ===========================================================================
REM  Claude Lifejacket - test runner (just double-click me)
REM
REM  This proves the safe-write engine before it's ever allowed near your real
REM  memory files. Green = trustworthy. If anything's red, nothing ships.
REM ===========================================================================
setlocal
cd /d "%~dp0"

echo.
echo   Checking the Lifejacket's stitching... (running the safety tests)
echo.

REM Make sure pytest is available; install it quietly if it's missing.
python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo   First run - fetching the test tool ^(pytest^). One moment...
    python -m pip install --quiet pytest
)

REM Run the suite. pyproject.toml already points pytest at src/ and tests/.
python -m pytest
set RESULT=%errorlevel%

echo.
if "%RESULT%"=="0" (
    echo   All good - every stitch held. This lifejacket will float. :^)
) else (
    echo   Some tests didn't pass. Nothing of yours was touched - these run in a
    echo   scratch folder only. Send me the output above and I'll fix it.
)
echo.
pause
endlocal
