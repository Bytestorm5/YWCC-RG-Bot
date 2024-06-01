import json
import threading
from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv
load_dotenv()

class JsonInteractor:
    def __init__(self, filename: str):
        self.filename = filename
        
        key = bytes(os.environ.get("CRYPT").encode())
        
        self.fernet = Fernet(key)
        self._lock = threading.Lock()
        
        if os.path.exists(filename):
            with open(filename, 'rb') as file:
                encrypted_data = file.read()
            decrypted_data = self.fernet.decrypt(encrypted_data)
            self.file = json.loads(decrypted_data.decode('utf-8'))
        else:
            self.file = {}
    
    def _update_file_unsafe(self, dict: dict):
        data = json.dumps(dict).encode('utf-8')
        encrypted_data = self.fernet.encrypt(data)
        with open(self.filename, 'wb') as file:
            file.write(encrypted_data)
    def update_file(self):
        with self._lock:
            self._update_file_unsafe(self.file)
    
    def __contains__(self, key):
        return key in self.file
    
    def __getitem__(self, key):
        return self.file[key]
    
    def __setitem__(self, key, data):
        with self._lock:
            self.file[key] = data
            self._update_file_unsafe(self.file)
    
if __name__ == "__main__":
    js = JsonInteractor('modmail.json')
    js['test'] = ["haha funny"]