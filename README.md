# Decentralized Social Network Protocol
Final semester project for Computer Networks.
Saint Louis University - Under the guidance of Prof. Nan Cen

## Team Members
- Francina Godwin Pali (francina172000)
- Roschlynn Michael Dsouza (roschlynnmichael)

### Project Description
This project aims to create a decentralized social network protocol using peer-to-peer technology. There are four main sections of this project:
- **Private Chat**: Users can add other users as friends using friend requests. Friend requests can be accepted or rejected. Once accepted, users can chat privately. This functionality follows a hybrid P2P approach by using Inter Planetary File System (IPFS) for storing chat history, P2P socket.io for real-time communication, and SQLAlchemy for database management. The MySQL database is being used as the centralized database for storing user information and store information about friend requests. IPFS is also being used for sharing files between private users. Every user also has their own chat clearing functionality to clear chats, update their profile pictures and change as needed. The private chat also shows when a user is typing a message.

- **Private Group Chat**: Users can create private groups and add their friends into those private groups. The person who created the group is the administrator of that group. The administrator can add or remove other users from the group. The group chat also has file sharing functionality using IPFS. The group chat is private and only the users inside the group can see the messages and files. This system also follows a hybrid P2P approach by using IPFS for storing group chat history, P2P socket.io for real-time communication, and SQLAlchemy for database management. The MySQL database is being used as the centralized database for storing user information. Chat history is also being stored in IPFS along with the files.

- **Public Chat**: This is more of a broadcast enabled chat. Any user even those who are not friends can join this chat. This chat system follows a P2P approach by using IPFS for storing just the chat history. Messages are broadcasted to all the peers in the network.

- **P2P Flood File Sharing**: This is a file sharing system implemented for the public chat room. This system follows a P2P Flood Sharing approach. Every user can upload files in their network which is also broadcasted to all peers in the network. Other peers can search for those files and in the search box it shows the user who has that file available with them. The system also allows to download the file from the peer who has it. 

All messages and files are stored in IPFS for private chat and private group chat. The public chat and P2P Flood File Sharing do not use IPFS for storing messages and files. Messages and files are delivered in real-time using Python Socket Library and Flask-SocketIO. We are also utilizing WebRTC for enabling this real-time communication.

## How to Run the Project.
1. Setup a server either running Ubuntu Server, Windows Server or get a cloud server from AWS, Azure, etc.
2. Install Python 3.11 in the server.
3. Now begin by installing MySQL Server 9 and configure it. The commands for install MySQL on Ubuntu Server are:
    - `sudo apt update`
    - `sudo apt install mysql-server`
    - `sudo mysql_secure_installation`
4. Install IPFS as well in the server. Be sure to use the Kubo Version of IPFS that is more oriented towards command line usage. You will also need to configure IPFS by running the following commands:
    - `ipfs init`
    - `ipfs config Addresses.API /ip4/0.0.0.0/tcp/5001`
    - `ipfs config Addresses.Gateway /ip4/0.0.0.0/tcp/8080`
5. Install all the dependencies in the requirements.txt file by running the following command:
    - `pip install -r requirements.txt`
6. Run the project by running the following command:
    - `python app.py`
7. Flask automatically handles creation of the database and tables. Do not worry about it.
8. You will need to perform port forwarding if you are using your own server at home. This step varies depending on your router. The flask appp runs on Port 5000 and IPFS runs on Port 5001.
9. You can access the application by going to the Public IP of your server followed by :5000.
