import cv2
import numpy as np
from infrastructure import DatabaseManager, FaceRecognitionEngine
import uuid


class PersonController:
    def __init__(self):
        self.db = DatabaseManager().conn
        self.engine = FaceRecognitionEngine()

    def add_person(self, name, dept, pos, level, frame):
        vec = self.engine.extract_features(frame)
        if vec is not None:
            # Создаем курсор, чтобы получить ID после вставки
            cursor = self.db.cursor()

            # Вставляем данные БЕЗ указания ID (база сама поставит 1, 2, 3...)
            cursor.execute("INSERT INTO persons (name, dept, pos, level) VALUES (?, ?, ?, ?)",
                           (name, dept, pos, level))

            # Получаем тот самый числовой ID, который только что создала база
            p_id = cursor.lastrowid

            _, buf = cv2.imencode('.jpg', frame)

            # Сохраняем биометрию, привязывая её к полученному числовому p_id
            self.db.execute("INSERT INTO biometrics (person_id, vector, face_img) VALUES (?, ?, ?)",
                            (p_id, vec.tobytes(), buf.tobytes()))

            self.db.commit()
            return True
        return False


class AccessController:
    def __init__(self):
        self.db = DatabaseManager().conn
        self.engine = FaceRecognitionEngine()

    def identify(self, frame, threshold):
        current_vec = self.engine.extract_features(frame)
        if current_vec is None:
            return None  # Лицо вообще не найдено в кадре

        known = self.db.execute(
            "SELECT p.name, b.vector FROM persons p JOIN biometrics b ON p.id = b.person_id").fetchall()
        for name, vec_bytes in known:
            if self.engine.is_match(current_vec, np.frombuffer(vec_bytes, dtype=np.float32), threshold):
                return name
        return "Unknown"  # Лицо есть, но в базе его нет