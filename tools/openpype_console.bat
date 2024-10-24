goto comment
SYNOPSIS
  Helper script running scripts through the QuadPype environment.

DESCRIPTION
  This script is usually used as a replacement for building when tested farm integration like Deadline.

EXAMPLE

cmd> .\quadpype_console.bat path/to/python_script.py
:comment

cd "%~dp0\.."
echo %QUADPYPE_MONGO%
.poetry\bin\poetry.exe run python start.py %*
