"""
TEKNOFEST 2026 Uluslararası İHA - Sentetik Veri Seti ve Etiket Üreteci
---------------------------------------------------------------------
YOLOv10 / YOLOv8 modellerini eğitmek ve test etmek amacıyla 2026 şartnamesindeki
Mavi Altıgen (Target A) ve Kırmızı Üçgen (Target B) hedeflerini rastgele zeminler,
rotasyonlar, gürültüler ve perspektif bozulmaları ile sentezleyerek
YOLO etiketli veri seti üretir.
"""

from typing import Tuple, List, Dict, Any, Optional
import os
import math
import random
import cv2
import numpy as np


class SyntheticDatasetGenerator:
    def __init__(self, output_dir: str = "dataset_synthetic", width: int = 1280, height: int = 720):
        self.output_dir = output_dir
        self.width = width
        self.height = height
        
        # Sınıflar: 0: target_a_blue_hexagon, 1: target_b_red_triangle
        self.classes = ["target_a_blue_hexagon", "target_b_red_triangle"]

    def _generate_background(self) -> np.ndarray:
        """Rastgele çim, toprak veya asfalt dokusu oluşturur."""
        bg_type = random.choice(["grass", "dirt", "asphalt"])
        
        if bg_type == "grass":
            # Yeşil çim dokusu
            base_color = (random.randint(40, 70), random.randint(90, 140), random.randint(30, 60))
        elif bg_type == "dirt":
            # Kahverengi toprak
            base_color = (random.randint(40, 70), random.randint(60, 90), random.randint(80, 120))
        else:
            # Gri asfalt
            val = random.randint(70, 110)
            base_color = (val, val, val)

        img = np.full((self.height, self.width, 3), base_color, dtype=np.uint8)
        # Gürültü ve doku
        noise = np.random.randint(-20, 20, (self.height, self.width, 3), dtype=np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        return img

    def generate_sample(self) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """Tek bir sentetik kare ve YOLO etiketlerini üretir."""
        frame = self._generate_background()
        annotations = []

        # 1. HEDEF A: Mavi Altıgen
        if random.random() > 0.15:
            cx = random.randint(150, self.width - 150)
            cy = random.randint(150, self.height - 150)
            radius = random.randint(40, 85)
            rot = random.uniform(0, 2 * math.pi)

            angles = np.linspace(rot, rot + 2 * np.pi, 7)[:-1]
            pts = np.array([
                [int(cx + radius * math.cos(a)), int(cy + radius * math.sin(a))]
                for a in angles
            ], dtype=np.int32)

            # Mavi renk (BGR)
            blue_b = random.randint(180, 240)
            blue_g = random.randint(80, 130)
            blue_r = random.randint(10, 50)
            cv2.fillPoly(frame, [pts], (blue_b, blue_g, blue_r))
            cv2.polylines(frame, [pts], isClosed=True, color=(240, 240, 240), thickness=3)

            # Bounding box
            bx, by, bw, bh = cv2.boundingRect(pts)
            annotations.append({
                "class_id": 0,
                "bbox_norm": (cx / self.width, cy / self.height, bw / self.width, bh / self.height)
            })

        # 2. HEDEF B: Kırmızı Üçgen
        if random.random() > 0.15:
            cx = random.randint(150, self.width - 150)
            cy = random.randint(150, self.height - 150)
            side = random.randint(60, 110)
            rot = random.uniform(0, 2 * math.pi)

            h_tri = side * math.sqrt(3) / 2
            local_pts = np.array([
                [0, -2 * h_tri / 3],
                [-side / 2, h_tri / 3],
                [side / 2, h_tri / 3]
            ])
            # Rotasyon matrisi
            R = np.array([[math.cos(rot), -math.sin(rot)], [math.sin(rot), math.cos(rot)]])
            rot_pts = (local_pts @ R.T) + np.array([cx, cy])
            rot_pts = rot_pts.astype(np.int32)

            # Kırmızı renk (BGR)
            red_b = random.randint(10, 40)
            red_g = random.randint(20, 60)
            red_r = random.randint(190, 245)
            cv2.fillPoly(frame, [rot_pts], (red_b, red_g, red_r))
            cv2.polylines(frame, [rot_pts], isClosed=True, color=(240, 240, 240), thickness=3)

            bx, by, bw, bh = cv2.boundingRect(rot_pts)
            annotations.append({
                "class_id": 1,
                "bbox_norm": (cx / self.width, cy / self.height, bw / self.width, bh / self.height)
            })

        return frame, annotations

    def generate_batch(self, count: int = 20) -> str:
        """Belirtilen sayıda sentetik görsel ve YOLO etiket dosyası üretir."""
        img_dir = os.path.join(self.output_dir, "images")
        lbl_dir = os.path.join(self.output_dir, "labels")
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(lbl_dir, exist_ok=True)

        for i in range(count):
            frame, annots = self.generate_sample()
            img_name = f"synth_{i:04d}.jpg"
            lbl_name = f"synth_{i:04d}.txt"

            img_path = os.path.join(img_dir, img_name)
            lbl_path = os.path.join(lbl_dir, lbl_name)

            cv2.imwrite(img_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])

            with open(lbl_path, "w", encoding="utf-8") as f:
                for a in annots:
                    cid = a["class_id"]
                    nx, ny, nw, nh = a["bbox_norm"]
                    f.write(f"{cid} {nx:.6f} {ny:.6f} {nw:.6f} {nh:.6f}\n")

        # data.yaml dosyası yaz
        yaml_content = f"""path: {os.path.abspath(self.output_dir)}
train: images
val: images
names:
  0: target_a_blue_hexagon
  1: target_b_red_triangle
"""
        with open(os.path.join(self.output_dir, "data.yaml"), "w", encoding="utf-8") as f:
            f.write(yaml_content)

        print(f"[DATASET] {count} adet sentetik örnek üretildi: {self.output_dir}")
        return self.output_dir
