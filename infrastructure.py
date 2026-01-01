import sqlite3
import cv2
import numpy as np
import os
from facenet_pytorch import MTCNN, InceptionResnetV1


class DatabaseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            base_path = os.path.dirname(os.path.abspath(__file__))
            cls._instance.db_path = os.path.join(base_path, "security_system.db")
            cls._instance.conn = sqlite3.connect(cls._instance.db_path, check_same_thread=False)
            cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS system_users (login TEXT, password TEXT, role TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS persons (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, dept TEXT, pos TEXT, level TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS biometrics (person_id TEXT, vector BLOB, face_img BLOB)')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS access_log (timestamp DATETIME, name TEXT, status TEXT, camera TEXT, hour INTEGER)')
        cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        cursor.execute(
            'CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, img BLOB)')

        users = [('admin', '123', 'Администратор'), ('operator', '123', 'Оператор'), ('boss', '123', 'Руководство')]
        cursor.executemany('INSERT OR IGNORE INTO system_users VALUES (?, ?, ?)', users)

        settings = [('threshold', '85'), ('max_attempts', '5'), ('lockout', '10'), ('panic_lockout', '60')]
        for k, v in settings: cursor.execute('INSERT OR IGNORE INTO settings VALUES (?, ?)', (k, v))
        self.conn.commit()

    def get_setting(self, key, default):
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        res = cursor.fetchone()
        return res[0] if res else str(default)

    def set_setting(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        self.conn.commit()


class FaceRecognitionEngine:
    def __init__(self):
        self.detector = MTCNN(keep_all=False)
        self.model = InceptionResnetV1(pretrained='vggface2').eval()

    def extract_features(self, frame):
        face = self.detector(frame)
        if face is not None:
            return self.model(face.unsqueeze(0)).detach().numpy().flatten()
        return None

    def is_match(self, v1, v2, threshold):
        dist = np.linalg.norm(v1 - v2)
        return dist < (1.0 - (float(threshold) / 100) + 0.5)