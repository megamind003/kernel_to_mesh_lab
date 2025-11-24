import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend


class EncryptedVault:
    """Encrypts and decrypts local data at rest."""
    
    def __init__(self, password: str, salt: bytes = None):
        if salt is None:
            salt = os.urandom(16)
        
        self.salt = salt
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.cipher = Fernet(key)
    
    def encrypt_file(self, input_path: str, output_path: str):
        with open(input_path, 'rb') as f:
            data = f.read()
        
        encrypted = self.cipher.encrypt(data)
        
        with open(output_path, 'wb') as f:
            f.write(self.salt + encrypted)
    
    def decrypt_file(self, input_path: str, output_path: str):
        with open(input_path, 'rb') as f:
            salt = f.read(16)
            encrypted = f.read()
        
        decrypted = self.cipher.decrypt(encrypted)
        
        with open(output_path, 'wb') as f:
            f.write(decrypted)
    
    def encrypt_bytes(self, data: bytes) -> bytes:
        return self.salt + self.cipher.encrypt(data)
    
    def decrypt_bytes(self, data: bytes) -> bytes:
        salt = data[:16]
        encrypted = data[16:]
        return self.cipher.decrypt(encrypted)
