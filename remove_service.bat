@echo off
echo Stopping Flask Service...
python install_service.py stop
echo Removing Flask Service...
python install_service.py remove
echo Done!
pause