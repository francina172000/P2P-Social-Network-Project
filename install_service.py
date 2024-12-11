import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import subprocess
import logging

class FlaskService(win32serviceutil.ServiceFramework):
    _svc_name_ = "FlaskEventletService"
    _svc_display_name_ = "Flask Eventlet Web Service"
    _svc_description_ = "Runs the Flask web application with Eventlet"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process = None

        # Set up logging
        logging.basicConfig(
            filename='C:/logs/flask_service.log',
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('FlaskService')

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        if self.process:
            self.process.terminate()

    def SvcDoRun(self):
        try:
            self.logger.info('Service starting...')
            
            # Change to your application directory
            os.chdir(r'D:\Projects\Decentralized-Social-Network-Protocol')
            
            # Start IPFS daemon
            subprocess.Popen(['ipfs', 'daemon'], 
                           creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Start the Flask application
            python_path = r'C:\Python311\python.exe'  # Update with your Python path
            self.process = subprocess.Popen(
                [python_path, 'wsgi.py'],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            self.logger.info('Service started successfully')
            
            # Wait for the stop event
            win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
            
        except Exception as e:
            self.logger.error(f'Service error: {str(e)}')
            raise

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(FlaskService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(FlaskService)