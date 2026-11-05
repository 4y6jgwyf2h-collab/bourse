@echo off
cd /d "%~dp0"
set PY=python
where py 1>NUL 2>NUL && set PY=py
py -3.13 -c "print()" 1>NUL 2>NUL && set PY=py -3.13
set BOURSE_LOCAL=1
%PY% -m streamlit run app.py
pause
