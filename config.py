import os
from urllib.parse import quote
from dotenv import load_dotenv

load_dotenv()

class Config:
    DB_PASSWORD = quote('Dsouza@3191')
    SECRET_KEY = os.urandom(32)
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://p2p_user:{DB_PASSWORD}@192.168.1.6:3306/p2p_social_network'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    #Mail Server Configuration
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 465
    MAIL_USE_TLS = False
    MAIL_USE_SSL = True
    MAIL_USERNAME = 'cnetworks361@gmail.com'
    MAIL_PASSWORD = 'kqzp gmfj momu qnlc'

    #AWS EC2 Configuration
    EC2_PUBLIC_IP = '192.168.1.6'
    #NGINX_USERNAME = 'roschlynnmichael'
    #NGINX_PASSWORD = 'Dsouza3191@'
    MAX_IPFS_LENGTH = 250 * 1024 * 1024
    #SESSION_COOKIE_SECURE = True
    #CSRF_COOKIE_SECURE = True

    #Upload Folder Configuration
    UPLOAD_FOLDER = os.path.join('static', 'profile_pictures')
    BLOCKED_EXTENSIONS = {
        # Executable files
        'exe', 'msi', 'bat', 'cmd', 'sh', 'bin', 'app',
        # Script files
        'vbs', 'ps1', 'js', 'py', 'php', 'pl', 'rb',
        # System files
        'sys', 'dll', 'reg', 'com',
        # Other potentially dangerous files
        'jar', 'apk', 'deb', 'rpm'
    }

    # Add this for profile pictures
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    MAX_CONTENT_LENGTH = 100 * 1024 * 1024
    
    #FERNET KEY CONFIGURATION
    ENCRYPTION_KEY = b'klMnjhfScy3lsuzmSu5yaxhzeortgmCOBI2XOdaullo='

    # IPFS Configuration
    IPFS_API_HOST = '192.168.1.6'  # Your Windows Server 2022 IP
    IPFS_API_PORT = 5001
    IPFS_GATEWAY_PORT = 8080
    IPFS_TIMEOUT = 30  # Increased timeout for network operations
