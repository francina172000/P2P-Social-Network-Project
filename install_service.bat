@echo off
echo Installing Flask Service...
python install_service.py install
echo Starting Flask Service...
python install_service.py start
echo Done!
pause