import sys
import os
import io
from functools import wraps
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, send_file
from flask import current_app, session, after_this_request
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from python_scripts.sql_models.models import db, User, FriendRequest, Group, GroupMember, Message
from python_scripts.handlers.p2p_socket_handler import P2PSocketHandler
from python_scripts.handlers.message_handler import MessageHandler
from python_scripts.handlers.ipfs_handler import IPFSHandler
from python_scripts.dht.group_dht import GroupDHT
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from python_scripts.public_chat.bucket_manager import BucketManager
from python_scripts.public_chat.chat_node import ChatNode
import smtplib
import random
import mimetypes
import logging
import string
import socket
from email.mime.text import MIMEText
from werkzeug.security import generate_password_hash, check_password_hash
from python_scripts.handlers.community_file_handler import CommunityFileHandler
from werkzeug.exceptions import RequestEntityTooLarge
from flask_socketio import SocketIO, emit, join_room, send, leave_room
import requests
import json
from config import Config
from urllib.parse import quote
from dotenv import load_dotenv
from sqlalchemy_utils import database_exists, create_database
from datetime import datetime
from werkzeug.utils import secure_filename
import logging
import tempfile
import hashlib
import time
from python_scripts.dht.group_dht import GroupDHT
from concurrent.futures import ThreadPoolExecutor

upload_executor = ThreadPoolExecutor(max_workers=5)
upload_status = {}
active_group_dhts = {}
active_users = {}
chat_nodes = {}
bucket_manager = BucketManager()

load_dotenv()

# Flask Application Setup
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.from_object('config.Config')

# SocketIO Setup
socketio = SocketIO(app, 
                   cors_allowed_origins="*", 
                   manage_session=False, 
                   logger=True, 
                   engineio_logger=True)

mail = Mail(app)

#IPFS Setup
ipfs_handler = IPFSHandler()

# Add health check
if not ipfs_handler.check_ipfs_health():
    app.logger.error(f"IPFS connection failed! Please check if IPFS daemon is running at {Config.IPFS_API_HOST}:{Config.IPFS_API_PORT}")
    # You might want to handle this error appropriately
else:
    app.logger.info(f"Successfully connected to IPFS node at {Config.IPFS_API_HOST}:{Config.IPFS_API_PORT}")

#Message Handler Setup
message_handler = MessageHandler()

app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER

# Login Manager Setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'

def get_system_ip():
    try:
        # This creates a socket that doesn't actually connect
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # This triggers the socket to get the system's primary IP
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1' 

SYSTEM_IP = get_system_ip()

# Get allowed extensions and upload folder from config
def allowed_file(filename):
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    
    # For profile picture uploads
    if request.endpoint == 'upload_profile_picture':
        return ext in app.config['ALLOWED_EXTENSIONS']
    
    # For file sharing in chat
    return ext not in app.config['BLOCKED_EXTENSIONS']

# Configuration for mail server, serializer and SQLAlchemy
db.init_app(app)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

def create_database_if_not_exists(app):
    try:
        engine = db.create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        if not database_exists(engine.url):
            create_database(engine.url)
        print(f"Database {engine.url.database} {'exists' if database_exists(engine.url) else 'created'}")
        return True
    except Exception as e:
        print(f"Error creating database: {str(e)}")
        return False

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Function to send email
def send_email(subject, body, sender, recipients, password):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
            smtp_server.login(sender, password)
            smtp_server.sendmail(sender, recipients, msg.as_string())
        print("Message sent!")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        raise

def authenticated_only(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            emit('error', {'message': 'Please log in to continue'})
            return
        return f(*args, **kwargs)
    return wrapped

# Function to generate verification code
def generate_verification_code():
    return ''.join(random.choices(string.digits, k=6))

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 400
    
    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = serializer.dumps(email, salt='email-confirm-salt')
    confirm_url = url_for('activate', token=token, _external=True)
    
    subject = "Confirm Your Email"
    body = f"Please click the following link to confirm your email: {confirm_url}"
    sender = app.config['MAIL_USERNAME']
    recipients = [email]
    password = app.config['MAIL_PASSWORD']

    try:
        send_email(subject, body, sender, recipients, password)
        return jsonify({
            "message": "Registration successful. Please check your email for activation link.",
        }), 201
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return jsonify({
            "message": "Registration successful but email verification failed. Please contact support.",
        }), 201

@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if request.method == 'GET':
        return render_template('reset_password_request.html')
    
    email = request.json.get('email')
    user = User.query.filter_by(email=email).first()
    if user:
        token = serializer.dumps(user.email, salt='password-reset-salt')
        reset_url = url_for('reset_password', token=token, _external=True)
        subject = "Password Reset Request"
        body = f"Click the following link to reset your password: {reset_url}"
        send_email(subject, body, app.config['MAIL_USERNAME'], [user.email], app.config['MAIL_PASSWORD'])
        return jsonify({"message": "Password reset link sent to your email."}), 200
    return jsonify({"error": "No account found with that email address."}), 404

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'GET':
        return render_template('reset_password.html', token=token)
    
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except (SignatureExpired, BadSignature):
        return jsonify({"error": "The password reset link is invalid or has expired."}), 400

    new_password = request.json.get('new_password')
    user = User.query.filter_by(email=email).first()
    if user:
        user.password = generate_password_hash(new_password)
        db.session.commit()
        return jsonify({"message": "Your password has been updated."}), 200
    return jsonify({"error": "User not found."}), 404

@app.route('/send_friend_request', methods=['POST'])
@login_required
def send_friend_request():
    data = request.json
    receiver_username = data.get('receiver_username')
    receiver = User.query.filter_by(username=receiver_username).first()

    if not receiver:
        return jsonify({"error": "User not found."}), 404
    
    if receiver == current_user:
        return jsonify({"error": "You cannot send a friend request to yourself."}), 400
    
    # Check if they are already friends
    if current_user.friends.filter_by(id=receiver.id).first():
        return jsonify({"error": "You are already friends with this user."}), 400
    
    # Check for existing friend requests in both directions
    existing_request = FriendRequest.query.filter(
        ((FriendRequest.sender == current_user) & (FriendRequest.receiver == receiver)) |
        ((FriendRequest.sender == receiver) & (FriendRequest.receiver == current_user))
    ).first()

    if existing_request:
        if existing_request.status == 'pending':
            if existing_request.sender == current_user:
                return jsonify({"error": "You have already sent a friend request to this user."}), 400
            else:
                return jsonify({"error": "This user has already sent you a friend request. Check your pending requests."}), 400
        elif existing_request.status == 'accepted':
            return jsonify({"error": "You are already friends with this user."}), 400
        elif existing_request.status == 'rejected':
            # If a previous request was rejected, we can allow a new request
            existing_request.status = 'pending'
            existing_request.sender = current_user
            existing_request.receiver = receiver
            existing_request.timestamp = datetime.utcnow()
            db.session.commit()
            return jsonify({"message": "Friend request sent successfully."}), 200
    
    # If no existing request, create a new one
    new_request = FriendRequest(sender=current_user, receiver=receiver)
    db.session.add(new_request)
    db.session.commit()

    return jsonify({"message": "Friend request sent successfully."}), 200

@app.route('/accept_friend_request/<int:request_id>', methods=['POST'])
@login_required
def accept_friend_request(request_id):
    friend_request = FriendRequest.query.get_or_404(request_id)
    
    if friend_request.receiver != current_user:
        return jsonify({"error": "Unauthorized"}), 403
    
    if friend_request.status != 'pending':
        return jsonify({"error": "This request has already been processed"}), 400
    
    friend_request.status = 'accepted'
    
    # Add each user to the other's friends list
    current_user.friends.append(friend_request.sender)
    friend_request.sender.friends.append(current_user)
    
    db.session.commit()
    
    # Emit a socket event to notify the sender and receiver
    friend = friend_request.sender
    socketio.emit('friend_request_accepted', {
        'friend_id': friend.id,
        'friend_username': friend.username,
        'friend_profile_picture': friend.profile_picture
    }, room=current_user.id)
    socketio.emit('friend_request_accepted', {
        'friend_id': current_user.id,
        'friend_username': current_user.username,
        'friend_profile_picture': current_user.profile_picture
    }, room=friend.id)

    return jsonify({"message": "Friend request accepted"}), 200

@app.route('/reject_friend_request/<int:request_id>', methods=['POST'])
@login_required
def reject_friend_request(request_id):
    friend_request = FriendRequest.query.get_or_404(request_id)
    
    if friend_request.receiver != current_user:
        return jsonify({"error": "Unauthorized"}), 403
    
    if friend_request.status != 'pending':
        return jsonify({"error": "This request has already been processed"}), 400
    
    friend_request.status = 'rejected'
    db.session.commit()
    
    return jsonify({"message": "Friend request rejected"}), 200

@app.route('/friend_requests', methods=['GET'])
@login_required
def get_friend_requests():
    pending_requests = FriendRequest.query.filter_by(receiver=current_user, status='pending').all()
    requests_data = [{
        'id': req.id,
        'sender_username': req.sender.username,
        'timestamp': req.timestamp
    } for req in pending_requests]
    return jsonify(requests_data), 200

@app.route('/friend_requests/<int:request_id>', methods=['DELETE'])
@login_required
def delete_friend_request(request_id):
    friend_request = FriendRequest.query.get_or_404(request_id)
    if friend_request.receiver != current_user:
        return jsonify({"error": "Unauthorized access."}), 403

@app.route('/activate/<token>', methods=['GET'])
def activate(token):
    try:
        email = serializer.loads(token, salt='email-confirm-salt', max_age=3600)
    except SignatureExpired:
        return jsonify({"error": "The confirmation link has expired."}), 400
    except BadSignature:
        return jsonify({"error": "The confirmation link is invalid."}), 400

    user = User.query.filter_by(email=email).first()
    if user:
        if not user.is_active:
            user.is_active = True
            db.session.commit()
            return jsonify({"message": "Your account has been activated successfully."}), 200
        else:
            return jsonify({"message": "Your account is already activated."}), 200
    else:
        return jsonify({"error": "No user found with that email address."}), 404

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('login'))
    
@app.errorhandler(404)
def not_found_error(error):
    if current_user.is_authenticated:
        return render_template('404.html'), 404
    return redirect(url_for('login'))

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    if request.is_xhr:
        return jsonify({"error": "An internal server error occurred. Please try again later."}), 500
    return render_template('500.html'), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'GET':
        return render_template('login.html')
    
    data = request.json
    identifier = data.get('identifier')
    password = data.get('password')

    user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()

    if not user:
        return jsonify({"error": "No account found with that username or email."}), 404
    
    if not user.is_active:
        return jsonify({"error": "Account not activated. Please check your email for the activation link."}), 403

    if not user.check_password(password):
        return jsonify({"error": "Incorrect password."}), 401
    
    if user and user.check_password(password):
        login_user(user)
        P2PSocketHandler.start_user_socket_server(user)
        return jsonify({"message": "Login successful!", "redirect": url_for('dashboard')}), 200

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    pending_requests = FriendRequest.query.filter_by(receiver = current_user, status = 'pending').all()
    friends = current_user.friends.all()
    return render_template('dashboard.html', pending_requests=pending_requests, friends=friends)

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "An internal server error occurred. Please try again later."}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Unhandled exception: {str(e)}")
    return jsonify({"error": "An unexpected error occurred. Please try again later."}), 500

@app.route('/api/current_user', methods=['GET'])
@login_required
def get_current_user():
    return jsonify({
        'username': current_user.username,
        'email': current_user.email
    }), 200

@app.route('/api/search_users', methods=['GET'])
@login_required
def search_users():
    query = request.args.get('query', '')
    if len(query) < 3:
        return jsonify([])
    
    users = User.query.filter(User.username.ilike(f'%{query}%')).limit(10).all()
    return jsonify([{'id': user.id, 'username': user.username, 'profile_picture': user.profile_picture if user.profile_picture else 'default.png'} for user in users])

@app.route('/api/send_friend_request', methods=['POST'])
@login_required
def api_send_friend_request():
    data = request.json
    receiver_id = data.get('receiver_id')
    receiver = User.query.get(receiver_id)

    if not receiver:
        return jsonify({"error": "User not found."}), 404
    if receiver == current_user:
        return jsonify({"error": "You cannot send a friend request to yourself."}), 400

    # Check if they are already friends
    if receiver in current_user.friends:
        return jsonify({"error": "You are already friends with this user."}), 400

    existing_request = FriendRequest.query.filter(
        ((FriendRequest.sender == current_user) & (FriendRequest.receiver == receiver)) |
        ((FriendRequest.sender == receiver) & (FriendRequest.receiver == current_user)),
        FriendRequest.status == 'pending'
    ).first()

    if existing_request:
        if existing_request.sender == current_user:
            return jsonify({"error": "Friend request already sent."}), 400
        else:
            return jsonify({"error": "This user has already sent you a friend request."}), 400

    new_request = FriendRequest(sender=current_user, receiver=receiver)
    db.session.add(new_request)
    db.session.commit()

    return jsonify({"message": "Friend request sent successfully."}), 200

@app.route('/upload_profile_picture', methods=['POST'])
@login_required
def upload_profile_picture():
    if 'profile_picture' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['profile_picture']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            file_extension = filename.rsplit('.', 1)[1].lower()
            new_filename = f"user_{current_user.id}.{file_extension}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
            file.save(file_path)
            
            # Update user's profile picture in the database
            current_user.profile_picture = new_filename
            db.session.commit()
            
            return jsonify({
                "success": True,
                "message": "Profile picture updated successfully",
                "filename": new_filename
            }), 200
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error uploading profile picture: {str(e)}")
            return jsonify({
                "success": False,
                "error": "An error occurred while uploading the profile picture"
            }), 500
    
    return jsonify({
        "success": False,
        "error": "File type not allowed"
    }), 400

@app.route('/remove_profile_picture', methods=['POST'])
@login_required
def remove_profile_picture():
    try:
        # Remove the current profile picture file
        if current_user.profile_picture != 'default.png':
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], current_user.profile_picture)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Set the user's profile picture to the default
        current_user.profile_picture = 'default.png'
        db.session.commit()
        
        return jsonify({"message": "Profile picture removed successfully"}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error removing profile picture: {str(e)}")
        return jsonify({"error": "An error occurred while removing the profile picture"}), 500

@app.route('/get_profile_picture/<int:user_id>')
def get_profile_picture(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({"profile_picture": user.profile_picture}), 200

@app.route('/api/friends', methods=['GET'])
@login_required
def get_friends():
    friend_requests = FriendRequest.query.filter(
        ((FriendRequest.sender_id == current_user.id) | (FriendRequest.receiver_id == current_user.id)) &
        (FriendRequest.status == 'accepted')
    ).all()
    friends = []
    for request in friend_requests:
        friend = request.receiver if request.sender_id == current_user.id else request.sender
        friends.append({
            'friend_id': friend.id,
            'friend_username': friend.username,
            'friend_profile_picture': friend.profile_picture
        })
    return jsonify(friends)

@app.route('/api/chats', methods=['GET'])
@login_required
def get_chats():
    # Implement logic to fetch and return user's chats
    # For now, you can return an empty list
    return jsonify([])

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/api/get_friend_socket_info/<int:friend_id>')
@login_required
def get_friend_socket_info(friend_id):
    friend = User.query.get_or_404(friend_id)
    return jsonify({
        'host': friend.socket_host,
        'port': friend.socket_port
    })

@app.route('/api/chat_history/<int:friend_id>')
@login_required
def get_chat_history(friend_id):
    try:
        # First check if friend exists
        friend = User.query.get(friend_id)
        if not friend:
            app.logger.error(f"Friend with ID {friend_id} not found")
            return jsonify({'messages': [], 'error': 'Friend not found'}), 404

        chat_history_hash = current_user.chat_history_hash
        app.logger.debug(f"Current user chat history hash: {chat_history_hash}")
        
        if not chat_history_hash:
            app.logger.debug("No chat history hash found")
            return jsonify({'messages': []}), 200

        try:
            # Get content from IPFS with detailed logging
            app.logger.debug(f"Attempting to get content from IPFS with hash: {chat_history_hash}")
            encrypted_history = ipfs_handler.get_content(chat_history_hash)
            app.logger.debug(f"Retrieved encrypted history of length: {len(encrypted_history) if encrypted_history else 0}")
            
            if not encrypted_history:
                app.logger.warning("No encrypted history retrieved from IPFS")
                return jsonify({'messages': []}), 200

            # Try to decode the JSON
            try:
                chat_history = json.loads(encrypted_history)
                app.logger.debug(f"Successfully decoded JSON with {len(chat_history)} messages")
            except json.JSONDecodeError as e:
                app.logger.error(f"JSON decode error: {str(e)}")
                app.logger.error(f"Raw content (first 200 chars): {encrypted_history[:200]}")
                return jsonify({'messages': [], 'error': 'Invalid chat history format'}), 200

            # Filter messages
            filtered_history = [
                msg for msg in chat_history 
                if (msg['sender_id'] == current_user.id and msg['friend_id'] == friend_id) or 
                   (msg['sender_id'] == friend_id and msg['friend_id'] == current_user.id)
            ]
            app.logger.debug(f"Filtered {len(filtered_history)} messages for friend {friend_id}")

            # Decrypt messages
            decrypted_history = []
            for msg in filtered_history:
                try:
                    decrypted_msg = msg.copy()
                    decrypted_msg['content'] = message_handler.decrypt_message(msg['content'])
                    decrypted_history.append(decrypted_msg)
                except Exception as e:
                    app.logger.error(f"Error decrypting message: {str(e)}")
                    decrypted_msg = msg.copy()
                    decrypted_msg['content'] = "Error: Could not decrypt message"
                    decrypted_history.append(decrypted_msg)

            app.logger.debug(f"Successfully decrypted {len(decrypted_history)} messages")
            return jsonify({'messages': decrypted_history}), 200

        except Exception as e:
            app.logger.error(f"Error with IPFS operations: {str(e)}")
            raise

    except Exception as e:
        app.logger.error(f"Error retrieving chat history: {str(e)}", exc_info=True)
        return jsonify({
            "error": "An error occurred while retrieving chat history.",
            "details": str(e)
        }), 500

@socketio.on('connect')
def handle_connect(auth=None):
    if current_user.is_authenticated:
        if current_user.id not in active_users:
            active_users[current_user.id] = set()
        active_users[current_user.id].add(request.sid)
        update_community_stats()

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        if current_user.id in active_users:
            active_users[current_user.id].discard(request.sid)
            if not active_users[current_user.id]:
                active_users.pop(current_user.id, None)
            update_community_stats()

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    app.logger.debug(f"Client {request.sid} joined room: {room}")

@socketio.on('leave')
def on_leave(data):
    room = data['room']
    leave_room(room)
    app.logger.debug(f"Client {request.sid} left room: {room}")

@socketio.on('message')
def handle_message(data):
    try:
        room = data['room']
        content = data['content']
        sender_id = data['sender_id']
        recipient_id = data['recipient_id']
        timestamp = data['timestamp']

        # Store message in database/IPFS if needed
        message_data = {
            'sender_id': sender_id,
            'recipient_id': recipient_id,
            'content': content,
            'timestamp': timestamp,
            'room': room
        }

        # Emit to the room (both sender and recipient will receive it)
        emit('new_message', message_data, room=room)
        
        app.logger.debug(f"Message sent in room {room}: {message_data}")
    except Exception as e:
        app.logger.error(f"Error handling message: {str(e)}")

@app.route('/api/send_message', methods=['POST'])
@login_required
def send_message():
    data = request.json
    friend_id = data.get('friend_id')
    message_content = data.get('message')
    room = data.get('room')
    timestamp = data.get('timestamp')
    
    try:
        # Check IPFS health before proceeding
        if not ipfs_handler.check_ipfs_health():
            raise Exception("IPFS service is not available")

        # Store message for both users regardless of active chat
        for user in [current_user, User.query.get(friend_id)]:
            chat_history = []
            if user.chat_history_hash:
                try:
                    encrypted_history = ipfs_handler.get_content(user.chat_history_hash)
                    chat_history = json.loads(encrypted_history)
                except Exception as e:
                    app.logger.error(f"Error loading chat history for user {user.id}: {str(e)}")
                    chat_history = []

            # Add new message to history
            new_message = {
                'sender_id': current_user.id,
                'friend_id': friend_id,
                'content': message_handler.encrypt_message(message_content),
                'timestamp': timestamp,
                'cleared_by': []
            }
            
            chat_history.append(new_message)
            
            try:
                # Store updated history in IPFS with timeout
                updated_history_hash = ipfs_handler.add_content(json.dumps(chat_history))
                user.chat_history_hash = updated_history_hash
            except Exception as e:
                app.logger.error(f"Failed to store chat history in IPFS: {str(e)}")
                raise Exception("Failed to store message")

        db.session.commit()

        # Emit the message through socket
        socketio.emit('new_message', {
            'sender_id': current_user.id,
            'recipient_id': friend_id,
            'content': message_content,
            'timestamp': timestamp,
            'room': room
        }, room=room)

        return jsonify({"success": True, "message": "Message sent and stored successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error in send_message: {str(e)}", exc_info=True)
        db.session.rollback()  # Add rollback in case of error
        return jsonify({"error": str(e)}), 500

@app.route('/api/store_message', methods=['POST'])
@login_required
def store_message():
    data = request.json
    friend_id = data.get('friend_id')
    message = data.get('message')
    
    # Store message in IPFS
    ipfs_handler = IPFSHandler()
    ipfs_hash = ipfs_handler.add_content(message)
    
    # Here you might want to store the IPFS hash in your database to keep track of the chat history
    
    return jsonify({'status': 'success', 'ipfs_hash': ipfs_hash})

@app.route('/api/clear_chat/<int:friend_id>', methods=['POST'])
@login_required
def clear_chat(friend_id):
    try:
        # Get the current user's chat history
        if current_user.chat_history_hash:
            current_user_history = json.loads(ipfs_handler.get_content(current_user.chat_history_hash))
        else:
            current_user_history = []

        # Remove messages with the specific friend
        current_user_history = [msg for msg in current_user_history 
                                if not (msg['friend_id'] == friend_id or msg['sender_id'] == friend_id)]

        # Store the updated history back to IPFS
        new_history_hash = ipfs_handler.add_content(json.dumps(current_user_history))

        # Update the current user's chat history hash in the database
        current_user.chat_history_hash = new_history_hash

        db.session.commit()

        return jsonify({"success": True, "message": "Chat history cleared successfully."}), 200
    except Exception as e:
        app.logger.error(f"Error clearing chat history: {str(e)}")
        return jsonify({"success": False, "error": "An error occurred while clearing chat history."}), 500
    
def handle_file_upload(file_content, filename, user_id, task_id):
    try:
        # Update status to processing
        upload_status[task_id] = {'status': 'processing'}
        
        # Encrypt the file content
        encrypted_content = message_handler.encrypt_file(file_content)

        # Upload to IPFS
        ipfs_hash = ipfs_handler.add_content(encrypted_content)
        
        if not ipfs_hash:
            raise Exception("Failed to upload to IPFS")

        # Store the successful result
        upload_status[task_id] = {
            'status': 'completed',
            'ipfs_hash': ipfs_hash,
            'filename': filename,
            'owner_id': user_id,
            'file_link': f'/api/download_file/{ipfs_hash}/{filename}'
        }
        
        # Emit success event
        socketio.emit('upload_complete', {
            'uploadId': task_id,
            'file_link': f'/api/download_file/{ipfs_hash}/{filename}'
        }, room=f"user_{user_id}")

    except Exception as e:
        app.logger.error(f"Error in file upload task: {str(e)}")
        upload_status[task_id] = {
            'status': 'error',
            'error': str(e)
        }
        socketio.emit('upload_error', {
            'task_id': task_id,
            'error': str(e)
        }, room=f"user_{user_id}")
    
    # Clean up status after 5 minutes
    def cleanup_status():
        time.sleep(300)  # 5 minutes
        upload_status.pop(task_id, None)
    
    upload_executor.submit(cleanup_status)

@app.route('/api/share_file', methods=['POST'])
@login_required
def share_file():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})
            
        file = request.files['file']
        if not file.filename:
            return jsonify({'success': False, 'error': 'No file selected'})
            
        # Generate task ID
        task_id = f"upload_{int(time.time())}_{current_user.id}"
        
        # Read file content
        file_content = file.read()
        
        # Encrypt and upload to IPFS
        encrypted_content = message_handler.encrypt_file(file_content)
        ipfs_hash = ipfs_handler.add_content(encrypted_content)
        
        if not ipfs_hash:
            raise Exception("Failed to upload to IPFS")
            
        # Generate download link
        file_link = f'/api/download_file/{ipfs_hash}/{secure_filename(file.filename)}'
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'file_link': file_link,
            'ipfs_hash': ipfs_hash,
            'filename': secure_filename(file.filename)
        })
        
    except Exception as e:
        app.logger.error(f"Error sharing file: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/upload_status/<task_id>')
@login_required
def get_upload_status(task_id):
    try:
        status = upload_status.get(task_id, {'status': 'in_progress'})
        return jsonify(status)
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

@app.route('/api/download_file/<ipfs_hash>/<filename>', methods=['GET'])
@login_required
def download_file(ipfs_hash, filename):
    try:
        # Get file content from IPFS
        encrypted_content = ipfs_handler.get_content(ipfs_hash)
        if not encrypted_content:
            return jsonify({'success': False, 'error': 'File not found'}), 404
            
        # Decrypt the content
        decrypted_content = message_handler.decrypt_file(encrypted_content)
        
        # Create response with proper headers
        response = send_file(
            io.BytesIO(decrypted_content),
            mimetype=mimetypes.guess_type(filename)[0] or 'application/octet-stream',
            as_attachment=True,
            download_name=filename  # This ensures proper filename with extension
        )
        
        # Add headers to prevent caching
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response
        
    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sign_chat/<int:friend_id>', methods=['POST'])
@login_required
def sign_chat(friend_id):
    try:
        chat_id = f"{current_user.id}_{friend_id}"
        chat_history = json.loads(ipfs_handler.get_content(current_user.chat_history_hash))
        chat_hash = hashlib.sha256(json.dumps(chat_history).encode()).hexdigest()
        # Instead of blockchain signature, use a simple hash
        signature = hashlib.sha256(f"{chat_hash}_{current_user.id}".encode()).hexdigest()
        return jsonify({"signature": signature}), 200
    except Exception as e:
        app.logger.error(f"Error signing chat: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/verify_chat/<int:friend_id>', methods=['POST'])
@login_required
def verify_chat(friend_id):
    try:
        data = request.json
        chat_id = f"{current_user.id}_{friend_id}"
        chat_history = json.loads(ipfs_handler.get_content(current_user.chat_history_hash))
        chat_hash = hashlib.sha256(json.dumps(chat_history).encode()).hexdigest()
        # Verify using the same simple hash method
        expected_signature = hashlib.sha256(f"{chat_hash}_{current_user.id}".encode()).hexdigest()
        is_verified = data['signature'] == expected_signature
        return jsonify({"verified": is_verified}), 200
    except Exception as e:
        app.logger.error(f"Error verifying chat: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/community')
@login_required
def community():
    return render_template('community.html')

@app.route('/api/groups/create', methods=['POST'])
@login_required
def create_group():
    try:
        data = request.json
        group_name = data.get('name')
        member_ids = data.get('members', [])
        
        # Create group in database
        group = Group(
            name=group_name,
            creator_id=current_user.id,
            created_at=datetime.utcnow()
        )
        
        # Add members to the group
        for user_id in member_ids:
            user = User.query.get(user_id)
            if user:
                group.members.append(user)
        
        db.session.add(group)
        db.session.commit()
        
        # Create DHT for group
        dht = GroupDHT(group.id)
        
        # Add members to DHT using existing find_free_port
        for user_id in member_ids:
            user = User.query.get(user_id)
            if user:
                # Use P2PSocketHandler's find_free_port method
                dht_port = P2PSocketHandler.find_free_port()
                dht.add_member(user.id, user.ip_address, dht_port)
        
        active_group_dhts[group.id] = dht
        
        return jsonify({
            'success': True,
            'group_id': group.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@socketio.on('group_message')
def handle_group_message(data):
    try:
        group_id = data['group_id']
        content = data['content']
        
        if group_id in active_group_dhts:
            dht = active_group_dhts[group_id]
            
            message_data = {
                'sender_id': current_user.id,
                'content': content,
                'timestamp': time.time()
            }
            
            # Store in DHT
            message_key = dht.store_message(message_data)
            
            # Emit to all group members
            emit('new_group_message', {
                'group_id': group_id,
                'message_key': message_key,
                'message': message_data
            }, room=f"group_{group_id}")
            
    except Exception as e:
        emit('error', {'message': str(e)})

@app.route('/api/communities', methods=['GET'])
@login_required
def get_communities():
    try:
        # Get all groups where the current user is a member
        communities = db.session.query(Group).join(
            GroupMember,
            Group.id == GroupMember.group_id
        ).filter(
            GroupMember.user_id == current_user.id
        ).all()
        
        # Format the response
        community_list = []
        for community in communities:
            # Count online members
            online_members = sum(1 for member in community.members 
                               if member.id in active_users)
            
            community_list.append({
                'id': community.id,
                'name': community.name,
                'description': community.description,
                'member_count': len(community.members),
                'online_count': online_members,
                'created_at': community.created_at.isoformat() if community.created_at else None
            })
        
        return jsonify(community_list)
        
    except Exception as e:
        app.logger.error(f"Error getting communities: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    
def update_community_stats():
    # Get all communities with their updated stats
    communities = Group.query.all()
    for community in communities:
        online_count = len([m for m in community.members if m.id in active_users])
        socketio.emit('community_stats_update', {
            'community_id': community.id,
            'member_count': len(community.members),
            'online_count': online_count
        }, to=None)      

@app.route('/api/users/available', methods=['GET'])
@login_required
def get_available_users():
    try:
        # Get all users except current user
        users = User.query.filter(User.id != current_user.id).all()
        return jsonify([{
            'id': user.id,
            'username': user.username,
            'email': user.email
        } for user in users])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/communities/<int:community_id>/members', methods=['GET'])
@login_required
def get_community_members(community_id):
    try:
        members = db.session.query(GroupMember, User).join(
            User, GroupMember.user_id == User.id
        ).filter(
            GroupMember.group_id == community_id
        ).all()
        
        return jsonify([{
            'user_id': member.GroupMember.user_id,
            'username': member.User.username,
            'role': member.GroupMember.role,
            'joined_at': member.GroupMember.joined_at.isoformat()
        } for member in members])
    except Exception as e:
        app.logger.error(f"Error getting community members: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/communities/<int:community_id>/members', methods=['POST'])
@login_required
def add_community_member(community_id):
    try:
        # Check if current user is admin
        is_admin = GroupMember.query.filter_by(
            group_id=community_id, 
            user_id=current_user.id, 
            role='admin'
        ).first()
        
        if not is_admin:
            return jsonify({'error': 'Unauthorized'}), 403
            
        data = request.json
        user_id = data.get('user_id')
        
        # Check if user exists and isn't already a member
        if not User.query.get(user_id):
            return jsonify({'error': 'User not found'}), 404
            
        if GroupMember.query.filter_by(group_id=community_id, user_id=user_id).first():
            return jsonify({'error': 'User is already a member'}), 400
            
        new_member = GroupMember(
            group_id=community_id,
            user_id=user_id,
            role='member'
        )
        db.session.add(new_member)
        db.session.commit()
        
        update_community_stats()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/communities/<int:community_id>/members/<int:user_id>', methods=['DELETE'])
@login_required
def remove_community_member(community_id, user_id):
    try:
        # Check if current user is admin
        is_admin = GroupMember.query.filter_by(
            group_id=community_id, 
            user_id=current_user.id, 
            role='admin'
        ).first()
        
        if not is_admin:
            return jsonify({'error': 'Unauthorized'}), 403
            
        member = GroupMember.query.filter_by(
            group_id=community_id, 
            user_id=user_id
        ).first()
        
        if not member:
            return jsonify({'error': 'Member not found'}), 404
            
        # Prevent removing the last admin
        if member.role == 'admin':
            admin_count = GroupMember.query.filter_by(
                group_id=community_id, 
                role='admin'
            ).count()
            if admin_count <= 1:
                return jsonify({'error': 'Cannot remove the last admin'}), 400
        
        db.session.delete(member)
        db.session.commit()
        
        update_community_stats()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/community/share_file', methods=['POST'])
@login_required
def handle_community_file_upload():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        community_id = request.form.get('community_id')
        
        if not file or not community_id:
            return jsonify({'error': 'Invalid request parameters'}), 400
            
        # Read file content
        file_content = file.read()
        filename = secure_filename(file.filename)
        
        # Register file with CommunityFileHandler
        file_metadata = CommunityFileHandler.register_file(
            file_content=file_content,
            filename=filename,
            user_id=current_user.id,
            community_id=community_id
        )
        
        # Create a message to notify about the shared file
        message = Message(
            community_id=community_id,
            sender_id=current_user.id,
            username=current_user.username,
            content=f"Shared file: {filename}",
            file_info={
                'name': filename,
                'size': len(file_content),
                'type': file.content_type,
                'hash': file_metadata['hash']
            }
        )
        
        db.session.add(message)
        db.session.commit()
        
        # Emit message to community room
        socketio.emit('message', {
            'username': current_user.username,
            'content': message.content,
            'timestamp': message.timestamp.isoformat(),
            'sender_id': current_user.id,
            'fileInfo': message.file_info
        }, room=f"community_{community_id}")
        
        return jsonify({
            'message': 'File uploaded successfully',
            'file_info': file_metadata
        })
        
    except Exception as e:
        app.logger.error(f"Error in community file upload: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/community/download_file/<file_hash>/<filename>')
@login_required
def download_community_file(file_hash, filename):
    try:
        community_id = request.args.get('community_id')
        if not community_id:
            return jsonify({'error': 'Community ID not provided'}), 400
            
        # Get the file content
        file_content = CommunityFileHandler.get_shared_file(file_hash)
        if not file_content:
            return jsonify({'error': 'File not found'}), 404

        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_path = temp_file.name
        
        # Write the content to the temp file
        with open(temp_path, 'wb') as f:
            if isinstance(file_content, str):
                f.write(file_content.encode())
            else:
                f.write(file_content)

        # Get MIME type
        mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

        # Clean up the temp file after sending
        @after_this_request
        def cleanup(response):
            try:
                os.unlink(temp_path)
            except Exception as e:
                app.logger.error(f"Error cleaning up temp file: {e}")
            return response

        return send_file(
            temp_path,
            mimetype=mime_type,
            as_attachment=True,
            download_name=filename,
            max_age=0
        )

    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return jsonify({'error': str(e)}), 500

@app.route('/api/community/share_file', methods=['POST'])
@login_required
def share_community_file():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
            
        file = request.files['file']
        community_id = request.form.get('community_id')
        
        if not file or not community_id:
            return jsonify({'success': False, 'error': 'Invalid request'}), 400
            
        # Calculate file hash and info
        file_content = file.read()
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_size = len(file_content)
        file_type = mimetypes.guess_type(file.filename)[0] or 'application/octet-stream'
        
        # Reset file pointer
        file.seek(0)
        
        # Store file in memory/cache
        CommunityFileHandler.shared_files[file_hash] = {
            'data': file_content,
            'name': file.filename,
            'type': file_type,
            'size': file_size
        }
        
        # Create message in database
        message = Message(
            community_id=community_id,
            sender_id=current_user.id,
            username=current_user.username,
            content=f"Shared file: {file.filename}",
            timestamp=datetime.utcnow()
        )
        db.session.add(message)
        db.session.commit()
        
        # Emit using community_message event
        message_data = {
            'id': message.id,
            'sender_id': current_user.id,
            'username': current_user.username,
            'content': f"Shared file: {file.filename}",
            'timestamp': message.timestamp.isoformat(),
            'fileInfo': {
                'hash': file_hash,
                'name': file.filename,
                'size': file_size,
                'type': file_type
            }
        }
        
        socketio.emit('community_message', message_data, room=f'community_{community_id}')
        
        return jsonify({
            'success': True,
            'message': message_data
        })
        
    except Exception as e:
        app.logger.error(f"File sharing error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/communities', methods=['POST'])
@login_required
def create_community():
    try:
        data = request.json
        new_community = Group(
            name=data['name'],
            description=data.get('description', ''),
            creator_id=current_user.id,  # Make sure to set the creator_id
            created_at=datetime.utcnow()
        )
        db.session.add(new_community)
        db.session.flush()  # Get the new community ID
        
        # Add creator as admin member
        admin_member = GroupMember(
            group_id=new_community.id,
            user_id=current_user.id,
            role='admin'  # Set creator as admin
        )
        db.session.add(admin_member)
        
        # Add other members if provided
        for user_id in data.get('members', []):
            if user_id != current_user.id:  # Skip creator as they're already added
                member = GroupMember(
                    group_id=new_community.id,
                    user_id=user_id,
                    role='member'
                )
                db.session.add(member)
        
        db.session.commit()
        
        # Return the newly created community data
        return jsonify({
            'id': new_community.id,
            'name': new_community.name,
            'description': new_community.description,
            'member_count': len(data.get('members', [])) + 1,  # Include creator
            'online_count': 1,  # Creator is online
            'created_at': new_community.created_at.isoformat()
        })
        
    except Exception as e:
        app.logger.error(f"Error creating community: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/communities/<int:community_id>/clear_chat', methods=['POST'])
@login_required
def clear_community_chat(community_id):
    try:
        # Check if user is admin of the community
        member = GroupMember.query.filter_by(
            group_id=community_id,
            user_id=current_user.id
        ).first()
        
        if not member or member.role != 'admin':
            return jsonify({
                'error': 'Unauthorized. Only community admins can clear chat.'
            }), 403
        
        # Delete messages for this community
        Message.query.filter_by(community_id=community_id).delete()
        db.session.commit()
        
        # Emit event to all users in the community to clear their chat
        socketio.emit('clear_chat', {
            'community_id': community_id
        }, room=f"community_{community_id}")
        
        return jsonify({'success': True, 'message': 'Chat cleared successfully'}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error clearing chat: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/public_chat', methods=['GET'])
@login_required
def public_chat():
    return render_template('public_chat.html')

@socketio.on('join_chat')
def handle_join_chat():
    try:
        user_id = str(current_user.id)
        
        # Check if user has a bucket
        if not bucket_manager.user_has_bucket(user_id):
            emit('error', {'message': 'Please create a bucket first'})
            return
            
        # Create chat node if doesn't exist
        if user_id not in chat_nodes:
            chat_nodes[user_id] = ChatNode(user_id, current_user.username)
            
            # Get existing bucket hash and sync
            existing_hash = bucket_manager.get_bucket_hash(user_id)
            if existing_hash:
                chat_nodes[user_id].sync_with_peer(existing_hash)
        
        # Join chat room
        join_room('p2p_chat')
        
        # Get current bucket hash
        current_hash = chat_nodes[user_id].get_bucket_hash()
        
        # Broadcast join message
        emit('user_joined', {
            'user_id': user_id,
            'username': current_user.username,
            'bucket_hash': current_hash
        }, room='p2p_chat')
        
        # Send chat history to user
        emit('chat_history', {
            'messages': chat_nodes[user_id].get_chat_history()
        })
        
    except Exception as e:
        app.logger.error(f"Error in join_chat: {str(e)}")
        emit('error', {'message': str(e)})

@socketio.on('send_message')
def handle_message(data):
    try:
        content = data.get('message', '').strip()
        if not content:
            return
            
        user_id = str(current_user.id)
        
        # Get user's chat node
        node = chat_nodes.get(user_id)
        if not node:
            return
            
        # Broadcast message
        result = node.broadcast_message(content)
        
        # Update bucket hash in manager
        bucket_manager.update_bucket_hash(user_id, result['bucket_hash'])
        
        # Send to all peers
        emit('new_message', {
            'message': result['message'],
            'bucket_hash': result['bucket_hash']
        }, room='p2p_chat')
        
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('check_bucket')
@authenticated_only
def handle_check_bucket():
    try:
        user_id = str(current_user.id)
        print(f"Checking bucket for user {user_id}")
        
        # Get bucket hash from bucket manager
        bucket_hash = bucket_manager.get_bucket_hash(user_id)
        has_bucket = bucket_hash is not None
        
        print(f"Bucket status - has_bucket: {has_bucket}, hash: {bucket_hash}")
        
        # Create chat node if bucket exists but node doesn't
        if has_bucket and user_id not in chat_nodes:
            chat_nodes[user_id] = ChatNode(user_id, current_user.username)
            chat_nodes[user_id].sync_with_peer(bucket_hash)
        
        emit('bucket_status', {
            'has_bucket': has_bucket,
            'bucket_hash': bucket_hash
        })
    except Exception as e:
        print(f"Error checking bucket: {e}")
        emit('error', {'message': str(e)})

@socketio.on('create_bucket')
def handle_create_bucket():
    try:
        user_id = str(current_user.id)
        print(f"Creating bucket for user {user_id}")
        
        # Create new chat node if it doesn't exist
        if user_id not in chat_nodes:
            chat_nodes[user_id] = ChatNode(user_id, current_user.username)
        
        # Get bucket hash
        bucket_hash = chat_nodes[user_id].get_bucket_hash()
        
        # Update bucket manager
        bucket_manager.update_bucket_hash(user_id, bucket_hash)
        
        print(f"Bucket created with hash: {bucket_hash}")
        
        emit('bucket_status', {
            'has_bucket': True,
            'bucket_hash': bucket_hash
        })
    except Exception as e:
        print(f"Error creating bucket: {e}")
        emit('error', {'message': str(e)})

@socketio.on('sync_request')
def handle_sync_request(data):
    try:
        peer_bucket_hash = data.get('bucket_hash')
        if not peer_bucket_hash:
            return
            
        user_id = str(current_user.id)
        
        # Get user's chat node
        node = chat_nodes.get(user_id)
        if not node:
            return
            
        # Sync with peer's bucket
        new_hash = node.sync_with_peer(peer_bucket_hash)
        
        # Update bucket hash in manager
        bucket_manager.update_bucket_hash(user_id, new_hash)
        
        # Broadcast new bucket hash
        emit('bucket_updated', {
            'user_id': user_id,
            'bucket_hash': new_hash
        }, room='p2p_chat')
        
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('typing')
def handle_typing(data):
    room = data.get('room')
    user_id = data.get('user_id')
    emit('user_typing', {'user_id': user_id}, room=room)

@socketio.on('stop_typing')
def handle_stop_typing(data):
    room = data.get('room')
    user_id = data.get('user_id')
    emit('user_stop_typing', {'user_id': user_id}, room=room)

@socketio.on('message_reaction')
def handle_reaction(data):
    room = data.get('room')
    message_id = data.get('message_id')
    reaction = data.get('reaction')
    user_id = data.get('user_id')
    
    emit('reaction_update', {
        'message_id': message_id,
        'reaction': reaction,
        'user_id': user_id
    }, room=room)

@socketio.on('join')
def on_join(data):
    room = data.get('room')
    if room:
        join_room(room)
        print(f"User {current_user.username} joined room: {room}")

@socketio.on('message')
@login_required
def handle_message(data):
    try:
        content = data.get('content')
        message_type = data.get('type', 'text')
        filename = data.get('filename')
        file_link = data.get('file_link')
        
        room = data.get('room')
        if not room or not room.startswith('community_'):
            return
        
        community_id = int(room.split('_')[1])
        
        # Create message object
        message = Message(
            community_id=community_id,
            sender_id=current_user.id,
            username=current_user.username,
            content=content,
            message_type=message_type
        )
        
        if message_type == 'file':
            message.filename = filename
            message.file_link = file_link
            
        db.session.add(message)
        db.session.commit()
        
        # Emit to room
        message_data = {
            'sender_id': current_user.id,
            'username': current_user.username,
            'content': content,
            'timestamp': datetime.utcnow().isoformat(),
            'type': message_type,
            'filename': filename,
            'file_link': file_link
        }
        
        emit('message', message_data, room=room)
        
    except Exception as e:
        app.logger.error(f"Error handling message: {str(e)}")
        emit('error', {'message': str(e)})

@socketio.on('connect')
def handle_connect(auth=None):
    if current_user.is_authenticated:
        join_room('p2p_chat')
        if current_user.id not in active_users:
            active_users[current_user.id] = set()
        active_users[current_user.id].add(request.sid)
        update_community_stats()

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        if current_user.id in active_users:
            active_users[current_user.id].discard(request.sid)
            if not active_users[current_user.id]:
                active_users.pop(current_user.id, None)
            update_community_stats()

@socketio.on('join_community')
def handle_join_community(data):
    try:
        community_id = data['community_id']
        if community_id in active_group_dhts:
            dht = active_group_dhts[community_id]
            
            # Get all messages from DHT
            messages = dht.get_messages()
            
            # Sort messages by timestamp
            messages.sort(key=lambda x: x['timestamp'])
            
            # Send message history to client
            emit('message_history', {
                'community_id': community_id,
                'messages': messages
            })
            
            # Join the room
            join_room(f"community_{community_id}")
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('get_message_history')
@login_required
def handle_get_message_history(data):
    community_id = data.get('community_id')
    if not community_id:
        return
        
    messages = Message.query.filter_by(community_id=community_id)\
        .order_by(Message.timestamp.asc())\
        .all()
        
    message_history = [{
        'username': msg.username,
        'content': msg.content,
        'message': msg.content,
        'timestamp': msg.timestamp.isoformat(),
        'sender_id': msg.sender_id,
        'fileInfo': msg.file_info
    } for msg in messages]
    
    emit('message_history', {
        'community_id': community_id,
        'messages': message_history
    })

@socketio.on('join_community')
def handle_join_community(data):
    try:
        community_id = data.get('community_id')
        if community_id:
            # Join the room
            join_room(f"community_{community_id}")
            print(f"User {current_user.username} joined community: {community_id}")
            
            # Update community stats
            update_community_stats()
            
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('get_my_files')
def handle_get_my_files():
    try:
        user_id = str(current_user.id)
        print(f"Getting files for user {user_id}")
        
        # Create chat node if it doesn't exist
        if user_id not in chat_nodes:
            bucket_hash = bucket_manager.get_bucket_hash(user_id)
            if bucket_hash:
                chat_nodes[user_id] = ChatNode(user_id, current_user.username)
                chat_nodes[user_id].secure_bucket.sync_with_peer(bucket_hash)
        
        node = chat_nodes.get(user_id)
        if not node:
            emit('error', {'message': 'Chat node not found'})
            return

        files = node.secure_bucket.get_files()
        print(f"Found {len(files)} files")
        emit('my_files_list', {'files': files})

    except Exception as e:
        print(f"Error getting files: {e}")
        emit('error', {'message': str(e)})

@socketio.on('delete_file')
def handle_delete_file(data):
    try:
        user_id = str(current_user.id)
        file_id = data.get('fileId')
        
        node = chat_nodes.get(user_id)
        if not node:
            emit('error', {'message': 'Chat node not found'})
            return

        success = node.secure_bucket.delete_file(file_id)
        if success:
            # Refresh file list
            files = node.secure_bucket.get_files()
            emit('my_files_list', {'files': files})
        else:
            emit('error', {'message': 'Failed to delete file'})

    except Exception as e:
        emit('error', {'message': str(e)})

@app.route('/api/share_file/<file_id>/<filename>')
@login_required
def download_shared_file(file_id, filename):
    try:
        # Get user's chat node
        user_id = str(current_user.id)
        if user_id not in chat_nodes:
            chat_nodes[user_id] = ChatNode(user_id, current_user.username)
            
        # Get file content from secure bucket
        file_content = chat_nodes[user_id].secure_bucket.get_file_content(file_id)
        if not file_content:
            return jsonify({'error': 'File not found'}), 404
            
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(file_content)
            temp_path = temp_file.name
            
        @after_this_request
        def cleanup(response):
            try:
                os.unlink(temp_path)
            except Exception as e:
                app.logger.error(f"Error cleaning up temp file: {e}")
            return response
            
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=filename,
            max_age=0
        )
        
    except Exception as e:
        app.logger.error(f"Error downloading file: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@socketio.on('get_user_info')
@authenticated_only
def handle_get_user_info():
    emit('user_info', {
        'user_id': current_user.id,  # Assuming you're using Flask-Login
        'username': current_user.username
    })

@socketio.on('send_message')
@authenticated_only
def handle_store_message(data):
    try:
        content = data['message']
        timestamp = data.get('timestamp', time.time())
        user_id = str(current_user.id)
        
        # Get or create chat node
        if user_id not in chat_nodes:
            chat_nodes[user_id] = ChatNode(user_id, current_user.username)
        
        # Create message structure
        message = {
            'id': hashlib.sha256(f"{user_id}-{content}-{timestamp}".encode()).hexdigest(),
            'sender_id': user_id,
            'username': current_user.username,
            'content': content,
            'timestamp': timestamp
        }
        
        # Store message and get updated bucket hash
        result = chat_nodes[user_id].broadcast_message(content)
        bucket_manager.update_bucket_hash(user_id, result['bucket_hash'])
        
        # Emit new message to all clients in p2p_chat room
        emit('new_message', message, broadcast=True, room='p2p_chat')
        
    except Exception as e:
        print(f"Error storing message: {e}")
        emit('error', {'message': str(e)})

@socketio.on('clear_chat_history')
@authenticated_only
def handle_clear_chat():
    try:
        user_id = str(current_user.id)
        
        # Get user's chat node
        node = chat_nodes.get(user_id)
        if not node:
            node = ChatNode(user_id, current_user.username)
            chat_nodes[user_id] = node
            
        # Check if there's any history to clear
        current_history = node.get_chat_history()
        if not current_history:
            emit('chat_history_cleared', {
                'success': True,
                'message': 'Chat history is already empty'
            })
            return
            
        # Clear chat history in bucket
        result = node.clear_chat_history()
        
        # Update bucket hash
        bucket_manager.update_bucket_hash(user_id, result['bucket_hash'])
        
        emit('chat_history_cleared', {
            'success': True,
            'bucket_hash': result['bucket_hash']
        }, broadcast=True)  # Broadcast to all users so everyone's chat clears
        
    except Exception as e:
        print(f"Error clearing chat history: {e}")
        emit('error', {'message': str(e)})

@socketio.on('get_requests')
@authenticated_only
def handle_get_requests():
    try:
        user_id = str(current_user.id)
        node = chat_nodes.get(user_id)
        if not node:
            return
            
        requests = node.secure_bucket.get_requests()
        
        # Add requestor flag to sent requests
        sent_requests = [{**req, 'requestor': True} for req in requests['sent']]
        # Add requestor flag to received requests
        received_requests = [{**req, 'requestor': True} for req in requests['received']]
        
        # Send both types of requests with requestor flag
        emit('my_requests', {'requests': sent_requests})
        emit('received_requests', {'requests': received_requests})
            
    except Exception as e:
        print(f"Error getting requests: {e}")
        emit('error', {'message': str(e)})

@socketio.on('broadcast_file_request')
@authenticated_only
def handle_file_request(data):
    try:
        user_id = str(current_user.id)
        node = chat_nodes.get(user_id)
        if not node:
            return
            
        # Add user info to request
        request_data = {
            'filename': data.get('filename'),
            'timestamp': time.time(),
            'status': 'pending',
            'requester_id': user_id,
            'username': current_user.username,
            'requestor': True
        }
        
        # Add request to bucket and get both hashes
        result = node.secure_bucket.add_file_request(request_data)
        
        # Get updated requests
        requests = node.secure_bucket.get_requests()
        
        # Send updates to appropriate clients
        if 'sent_hash' in result:
            emit('my_requests', {'requests': requests['sent']}, room=user_id)
        if 'received_hash' in result:
            emit('received_requests', {'requests': requests['received']}, broadcast=True)
            
    except Exception as e:
        print(f"Error handling file request: {e}")
        emit('error', {'message': str(e)})

@socketio.on('clear_all_requests')
@authenticated_only
def handle_clear_all_requests():
    try:
        user_id = str(current_user.id)
        node = chat_nodes.get(user_id)
        if not node:
            return
            
        # Clear all requests
        node.secure_bucket.clear_all_requests()
        
        # Get updated (empty) requests
        requests = node.secure_bucket.get_requests()
        
        # Broadcast the cleared state to all users
        emit('my_requests', {'requests': []}, broadcast=True)
        emit('received_requests', {'requests': []}, broadcast=True)
            
    except Exception as e:
        print(f"Error clearing all requests: {e}")
        emit('error', {'message': str(e)})

@socketio.on('get_chat_history')
@authenticated_only
def handle_get_chat_history():
    try:
        user_id = str(current_user.id)
        node = chat_nodes.get(user_id)
        if not node:
            node = ChatNode(user_id, current_user.username)
            chat_nodes[user_id] = node
            
        chat_history = node.get_chat_history()
        emit('chat_history', {'messages': chat_history})
            
    except Exception as e:
        print(f"Error getting chat history: {e}")
        emit('error', {'message': str(e)})

@app.route('/peer_files')
@login_required
def peer_files():
    return render_template('peer_files.html')

@app.route('/api/peer_files', methods=['GET'])
@login_required
def get_peer_files():
    try:
        users_data = {}
        print(f"Getting peer files. Current user: {current_user.username}")
        print(f"Available buckets: {bucket_manager.buckets_data.keys()}")
        
        # Get all users with buckets
        for user_id, bucket_info in bucket_manager.buckets_data.items():
            if user_id != str(current_user.id):  # Exclude current user
                # Get username from database
                user = User.query.get(int(user_id))
                if user:
                    print(f"Processing user {user.username} with bucket hash {bucket_info.get('hash')}")
                    users_data[user_id] = {
                        'username': user.username,
                        'bucket_hash': bucket_info.get('hash'),
                        'files': []
                    }
                    
                    # Get files if user has a chat node
                    if user_id in chat_nodes:
                        node = chat_nodes[user_id]
                        files = node.secure_bucket.get_files()
                        print(f"Found {len(files)} files for user {user.username}")
                        users_data[user_id]['files'] = files
                    else:
                        print(f"No chat node found for user {user.username}")
        
        return jsonify({
            'success': True,
            'users': users_data
        })
    except Exception as e:
        print(f"Error in get_peer_files: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/peer_file/<user_id>/<file_id>/<filename>')
@login_required
def download_peer_file(user_id, file_id, filename):
    try:
        # Get the peer's chat node
        if user_id not in chat_nodes:
            return jsonify({'error': 'Peer not found'}), 404
            
        node = chat_nodes[user_id]
        
        # Get file content from peer's secure bucket
        file_content = node.secure_bucket.get_file_content(file_id)
        if not file_content:
            return jsonify({'error': 'File not found'}), 404
            
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(file_content)
            temp_path = temp_file.name
            
        @after_this_request
        def cleanup(response):
            try:
                os.unlink(temp_path)
            except Exception as e:
                app.logger.error(f"Error cleaning up temp file: {e}")
            return response
            
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=filename,
            max_age=0
        )
        
    except Exception as e:
        app.logger.error(f"Error downloading peer file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@socketio.on('p2p_search')
@authenticated_only
def handle_p2p_search(data):
    try:
        filename = data.get('filename')
        if not filename:
            return
            
        # Search in both P2P network and IPFS
        p2p_results = []
        ipfs_results = []
        
        # P2P flood search
        if hasattr(chat_nodes[str(current_user.id)], 'p2p_network'):
            chat_nodes[str(current_user.id)].p2p_network.flood_search(filename)
            
        # Combine results
        all_results = p2p_results + ipfs_results
        emit('p2p_search_results', {'results': all_results})
        
    except Exception as e:
        print(f"Error in P2P search: {e}")
        emit('error', {'message': str(e)})

@socketio.on('p2p_request_file')
@authenticated_only
def handle_p2p_file_request(data):
    try:
        filename = data.get('filename')
        source = data.get('source')
        
        # Request file from peer
        if hasattr(chat_nodes[str(current_user.id)], 'p2p_network'):
            chat_nodes[str(current_user.id)].p2p_network.request_file(
                filename, 
                source
            )
            
    except Exception as e:
        print(f"Error requesting P2P file: {e}")
        emit('error', {'message': str(e)})

@app.route('/api/my_shared_files')
@login_required
def get_my_shared_files():
    try:
        node = chat_nodes.get(str(current_user.id))
        if not node:
            return jsonify({'success': False, 'error': 'Node not found'})
            
        files = node.secure_bucket.get_files()
        return jsonify({
            'success': True,
            'files': files
        })
    except Exception as e:
        print(f"Error getting shared files: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/share_p2p_file', methods=['POST'])
@login_required
def share_p2p_file():
    # Your second implementation here
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'})
            
        file = request.files['file']
        if not file.filename:
            return jsonify({'success': False, 'error': 'No file selected'})
            
        # Get node
        node = chat_nodes.get(str(current_user.id))
        if not node:
            return jsonify({'success': False, 'error': 'Node not found'})
            
        # Add file to bucket
        file_info = node.secure_bucket.add_file(
            file.read(),
            file.filename
        )
        
        # Share with P2P network
        node.p2p_network.share_file(file_info)
        
        return jsonify({
            'success': True,
            'file': file_info
        })
    except Exception as e:
        print(f"Error sharing file: {e}")
        return jsonify({'success': False, 'error': str(e)})

@socketio.on('search_files')
@authenticated_only
def handle_file_search(data):
    try:
        query = data.get('query')
        if not query:
            emit('search_results', {'success': True, 'results': []})
            return
            
        # Use P2P flooding for search
        user_id = str(current_user.id)
        if user_id in chat_nodes and hasattr(chat_nodes[user_id], 'p2p_network'):
            # Initiate flood search
            chat_nodes[user_id].p2p_network.flood_search(query)
            
            # Wait briefly for responses to come in
            time.sleep(2)  # Adjust timeout as needed
            
            # Get collected results from the P2P network
            results = []
            for filename, sources in chat_nodes[user_id].p2p_network.file_sources.items():
                for host, port, file_id in sources:
                    results.append({
                        'name': filename,
                        'username': f'Peer at {host}:{port}',
                        'source': {
                            'host': host,
                            'port': port,
                            'file_id': file_id
                        }
                    })
            
            emit('search_results', {
                'success': True,
                'results': results
            })
        
    except Exception as e:
        print(f"Error in P2P search: {e}")
        emit('error', {'message': str(e)})

@app.route('/api/delete_file/<file_id>', methods=['DELETE'])
@login_required
def delete_file(file_id):
    try:
        node = chat_nodes.get(str(current_user.id))
        if not node:
            return jsonify({'success': False, 'error': 'Node not found'})
            
        success = node.secure_bucket.delete_file(file_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'File not found'})
            
    except Exception as e:
        print(f"Error deleting file: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/peer_file/<user_id>/<file_id>/<filename>', endpoint='download_peer_file_alt')
@login_required
def download_peer_file_alternate(user_id, file_id, filename):
    try:
        # Get the peer's chat node
        if user_id not in chat_nodes:
            chat_nodes[user_id] = ChatNode(user_id, current_user.username)
            
        node = chat_nodes[user_id]
        
        # Get file content from peer's secure bucket
        file_content = node.secure_bucket.get_file_content(file_id)
        if not file_content:
            return jsonify({'error': 'File not found'}), 404
            
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(file_content)
            temp_path = temp_file.name
            
        @after_this_request
        def cleanup(response):
            try:
                os.unlink(temp_path)
            except Exception as e:
                app.logger.error(f"Error cleaning up temp file: {e}")
            return response
            
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=filename,
            max_age=0
        )
        
    except Exception as e:
        app.logger.error(f"Error downloading file: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@socketio.on('download_file')
@authenticated_only
def handle_file_download(data):
    try:
        filename = data.get('filename')
        source = data.get('source')
        
        if not filename or not source:
            emit('error', {'message': 'Invalid download request'})
            return
            
        # Request file from peer using P2P network
        user_id = str(current_user.id)
        if user_id in chat_nodes and hasattr(chat_nodes[user_id], 'p2p_network'):
            chat_nodes[user_id].p2p_network.request_file(
                filename,
                (source['host'], source['port'], source['file_id'])
            )
            
            # The P2P network will handle receiving the file and emitting the download_ready event
            
    except Exception as e:
        print(f"Error handling file download: {e}")
        emit('error', {'message': str(e)})

@app.route('/download_temp/<filename>')
@login_required
def download_temp_file(filename):
    try:
        user_id = str(current_user.id)
        if user_id not in chat_nodes:
            return jsonify({'error': 'Node not found'}), 404
            
        temp_dir = chat_nodes[user_id].p2p_network.temp_directory
        return send_from_directory(temp_dir, filename, as_attachment=True)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('flood_share_file')
@authenticated_only
def handle_flood_share(data):
    try:
        # Create a unique file ID
        file_id = f"{current_user.id}_{time.time()}"
        
        # Store file info in memory
        shared_files[file_id] = {
            'name': data['name'],
            'size': data['size'],
            'data': data['data'],
            'owner': current_user.id
        }
        
        # Broadcast to connected peers - Fix the emit syntax
        socketio.emit('flood_new_file', {
            'fileId': file_id,
            'name': data['name'],
            'size': data['size'],
            'peer': current_user.username
        })  # Remove broadcast=True
        
        # Send confirmation to the uploader
        emit('flood_file_shared', {
            'success': True,
            'fileId': file_id,
            'name': data['name'],
            'size': data['size']
        })
        
    except Exception as e:
        emit('error', {'message': str(e)})

shared_files = {}

@socketio.on('flood_search')
@authenticated_only
def handle_flood_search(data):
    try:
        query = data['query'].lower()
        results = []
        
        # Search through shared files
        for file_id, file_info in shared_files.items():
            if query in file_info['name'].lower():
                results.append({
                    'fileId': file_id,
                    'name': file_info['name'],
                    'size': file_info['size'],
                    'peer': User.query.get(file_info['owner']).username
                })
        
        emit('flood_search_results', {'results': results})
        
    except Exception as e:
        emit('error', {'message': str(e)})

@app.route('/api/flood_upload', methods=['POST'])
@login_required
def handle_flood_upload():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file part'})
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No selected file'})
            
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'File type not allowed'})
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_id = f"{current_user.id}_{time.time()}_{filename}"
            
            # Read file content directly from request
            file_content = file.read()
                
            # Store in shared_files dictionary
            shared_files[file_id] = {
                'name': filename,
                'size': len(file_content),
                'data': file_content,
                'owner': current_user.id
            }
            
            # Broadcast to peers
            socketio.emit('flood_new_file', {
                'fileId': file_id,
                'name': filename,
                'size': shared_files[file_id]['size'],
                'peer': current_user.username
            })
            
            return jsonify({
                'success': True,
                'fileId': file_id,
                'name': filename,
                'size': shared_files[file_id]['size']
            })
            
    except Exception as e:
        print(f"Upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/flood_download/<file_id>')
@login_required
def handle_flood_download(file_id):
    try:
        if file_id not in shared_files:
            return jsonify({'success': False, 'error': 'File not found'}), 404
            
        file_info = shared_files[file_id]
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(file_info['data'])
            temp_path = temp_file.name
            
        @after_this_request
        def cleanup(response):
            try:
                os.unlink(temp_path)
            except Exception as e:
                app.logger.error(f"Error cleaning up temp file: {e}")
            return response
            
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=file_info['name'],
            max_age=0
        )
        
    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@socketio.on('community_message')
@authenticated_only
def handle_community_message(data):
    try:
        content = data.get('content') or data.get('message')
        room = data.get('room')
        
        if not room or not room.startswith('community_'):
            return
        
        community_id = int(room.split('_')[1])
        
        # Create message object with current timestamp
        current_time = datetime.utcnow()
        message = Message(
            community_id=community_id,
            sender_id=current_user.id,
            username=current_user.username,
            content=content,
            timestamp=current_time  # Add timestamp field if it exists in your model
        )
        
        db.session.add(message)
        db.session.commit()
        
        # Emit to room using the timestamp
        message_data = {
            'id': message.id,
            'sender_id': current_user.id,
            'username': current_user.username,
            'content': content,
            'timestamp': current_time.isoformat()  # Format the timestamp
        }
        
        emit('community_message', message_data, room=room)
        
    except Exception as e:
        app.logger.error(f"Error handling community message: {str(e)}")
        emit('error', {'message': str(e)})

@socketio.on('public_chat_message')
@authenticated_only
def handle_public_chat_message(data):
    try:
        content = data.get('message', '').strip()
        if not content:
            return
            
        user_id = str(current_user.id)
        
        # Get user's chat node
        node = chat_nodes.get(user_id)
        if not node:
            node = ChatNode(user_id, current_user.username)
            chat_nodes[user_id] = node
            
        # Create and broadcast message
        result = node.broadcast_message(content)
        
        # Update bucket hash in manager
        bucket_manager.update_bucket_hash(user_id, result['bucket_hash'])
        
        # Send to all peers
        emit('new_message', {
            'message': {
                'id': result['message_id'],
                'content': content,
                'sender_id': current_user.id,
                'username': current_user.username,
                'timestamp': result['timestamp']
            },
            'bucket_hash': result['bucket_hash']
        }, room='p2p_chat')
        
    except Exception as e:
        emit('error', {'message': str(e)})