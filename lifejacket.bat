@echo off
REM Run Claude Lifejacket from this folder without worrying about PATH.
REM Works whether or not it's been pip-installed, because we add the bundled
REM src/ folder to PYTHONPATH as a fallback.
setlocal
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
python -m claude_lifejacket %*
endlocal
