import smtplib
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv
import ssl
import logging
import socket

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('smtp_test')

load_dotenv()

# Global email configuration
GMAIL_SENDER = 'cnetworks361@gmail.com'
GMAIL_PASSWORD = 'kqzp gmfj momu qnlc'
TEST_RECIPIENT = 'roschlynn@outlook.com'

def test_email():
    try:
        # Create message
        msg = MIMEText("This is a test email sent from Python using Gmail SMTP.")
        msg['Subject'] = "Test Email from Python"
        msg['From'] = GMAIL_SENDER
        msg['To'] = TEST_RECIPIENT
        
        # Create SSL context with debug info
        context = ssl.create_default_context()
        logger.debug("SSL Context created")
        
        # Detailed connection attempt
        logger.info("Attempting to connect to SMTP server...")
        smtp_server = smtplib.SMTP_SSL(
            'smtp.gmail.com', 
            465, 
            context=context,
            local_hostname='localhost'
        )
        smtp_server.set_debuglevel(2)  # Enable verbose debug output
        logger.info("Connected to SMTP server")
        
        try:
            # Login attempt
            logger.info("Attempting to login...")
            smtp_server.login(GMAIL_SENDER, GMAIL_PASSWORD)
            logger.info("Login successful")
            
            # Send mail attempt
            logger.info("Attempting to send email...")
            smtp_server.sendmail(GMAIL_SENDER, [TEST_RECIPIENT], msg.as_string())
            logger.info("Email sent successfully!")
            
            return True
            
        except smtplib.SMTPAuthenticationError as auth_error:
            logger.error(f"Authentication failed: {auth_error}")
            logger.error("This might be due to:")
            logger.error("1. Incorrect password")
            logger.error("2. 2FA is enabled but using password instead of App Password")
            logger.error("3. Less secure app access is disabled")
            return False
            
        except smtplib.SMTPException as smtp_error:
            logger.error(f"SMTP error occurred: {smtp_error}")
            logger.error(f"SMTP error code: {getattr(smtp_error, 'smtp_code', 'N/A')}")
            logger.error(f"SMTP error message: {getattr(smtp_error, 'smtp_error', 'N/A')}")
            return False
            
        finally:
            try:
                smtp_server.quit()
                logger.info("SMTP connection closed properly")
            except Exception as e:
                logger.error(f"Error closing SMTP connection: {e}")
                
    except ssl.SSLError as ssl_error:
        logger.error(f"SSL Error: {ssl_error}")
        logger.error("This might be due to:")
        logger.error("1. SSL/TLS protocol issues")
        logger.error("2. Certificate validation problems")
        return False
        
    except ConnectionError as conn_error:
        logger.error(f"Connection Error: {conn_error}")
        logger.error("This might be due to:")
        logger.error("1. No internet connection")
        logger.error("2. Gmail SMTP server is down")
        logger.error("3. Firewall blocking the connection")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        return False

def verify_gmail_settings():
    """Verify Gmail configuration and network connectivity"""
    logger.info("Verifying Gmail configuration...")
    
    # Check internet connectivity
    try:
        import socket
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        logger.info("Internet connection: OK")
    except OSError:
        logger.error("Internet connection: FAILED")
        return False

    # Check if credentials are provided
    if not all([GMAIL_SENDER, GMAIL_PASSWORD]):
        logger.error("Missing credentials")
        return False
    
    # Try to resolve Gmail's SMTP server
    try:
        smtp_ip = socket.gethostbyname('smtp.gmail.com')
        logger.info(f"Gmail SMTP server resolved: {smtp_ip}")
    except socket.gaierror:
        logger.error("Could not resolve Gmail's SMTP server")
        return False
    
    return True

if __name__ == "__main__":
    print("Starting email test...")
    
    # First verify settings
    if verify_gmail_settings():
        # Then try to send email
        success = test_email()
        print(f"Test {'succeeded' if success else 'failed'}")
    else:
        print("Failed to verify Gmail settings")