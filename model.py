from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

@dataclass
class Employee:
    id: str
    name: str
    dept: str = ""
    pos: str = ""
    level: str = "Базовый"

@dataclass
class IncidentReport:
    id: int
    timestamp: str
    img_bytes: bytes
    camera: str = "Cam 1"
    message: str = "ВЗЛОМ"