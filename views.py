from abc import ABC, abstractmethod
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np


class IView(ABC):
    @abstractmethod
    def display_message(self, msg): pass


class TextRenderer:
    @staticmethod
    def draw(image, text, position, color):
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()

        img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        draw.text(position, text, font=font, fill=color)
        return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)