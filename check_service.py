import win32serviceutil
import time
import smtplib
from email.mime.text import MIMEText
from config import Config

def check_service():
    try:
        status = win32serviceutil.QueryServiceStatus('FlaskEventletService')[1]
        if status != 4:  # 4 is running
            # Attempt to restart the service
            win32serviceutil.RestartService('FlaskEventletService')
            
            # Send notification email
            msg = MIMEText('Flask service was down and has been restarted.')
            msg['Subject'] = 'Flask Service Alert'
            msg['From'] = Config.MAIL_USERNAME
            msg['To'] = Config.ADMIN_EMAIL

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
                smtp_server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
                smtp_server.sendmail(Config.MAIL_USERNAME, [Config.ADMIN_EMAIL], msg.as_string())
    except Exception as e:
        print(f"Error checking service: {str(e)}")

if __name__ == '__main__':
    while True:
        check_service()
        time.sleep(300)  # Check every 5 minutes