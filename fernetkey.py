from cryptography.fernet import Fernet

enc_key = Fernet.generate_key()
print(enc_key)
