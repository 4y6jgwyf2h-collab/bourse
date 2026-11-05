@echo off
cd /d "%~dp0"
set PY=python
set PYW=pythonw
where py 1>NUL 2>NUL && set PY=py&& set PYW=pyw
py -3.13 -c "print()" 1>NUL 2>NUL && set PY=py -3.13&& set PYW=pyw -3.13
echo Verification des modules...
%PY% -m pip install -q --disable-pip-version-check --no-warn-script-location -r requirements.txt
echo Ouverture de Bourse...
start "" %PYW% fenetre.pyw
