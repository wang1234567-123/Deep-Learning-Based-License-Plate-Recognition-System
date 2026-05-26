import base64
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


CHARS = [
    '京', '沪', '津', '渝', '冀', '晋', '蒙', '辽', '吉', '黑',
    '苏', '浙', '皖', '闽', '赣', '鲁', '豫', '鄂', '湘', '粤',
    '桂', '琼', '川', '贵', '云', '藏', '陕', '甘', '青', '宁',
    '新',
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K',
    'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T', 'U', 'V',
    'W', 'X', 'Y', 'Z', 'I', 'O', '-',
]


@dataclass(frozen=True)
class PlateCandidate:
    plate: str
    confidence: float | None
    bbox: dict[str, float] | None


class LprNetRecognizer:
    def __init__(self, weights_path: str, use_cuda: bool = True, device: str = 'cuda:0', img_size: tuple[int, int] = (94, 24)):
        self.weights_path = weights_path
        self.use_cuda = use_cuda
        self.device = device
        self.img_size = img_size
        self._lock = threading.Lock()
        self._net = None
        self._torch = None

    def _ensure_loaded(self):
        if self._net is not None:
            return
        with self._lock:
            if self._net is not None:
                return
            try:
                import torch
            except Exception as e:
                raise RuntimeError(f'PyTorch 未安装或不可用: {e}') from e

            lpr_root = Path(__file__).resolve().parents[1] / 'LPRNet_Pytorch-master' / 'LPRNet_Pytorch-master'
            if not lpr_root.exists():
                raise RuntimeError(f'LPRNet 模型目录不存在: {lpr_root}')
            if str(lpr_root) not in sys.path:
                sys.path.insert(0, str(lpr_root))

            from model.LPRNet import build_lprnet

            net = build_lprnet(lpr_max_len=8, phase=False, class_num=len(CHARS), dropout_rate=0)
            if self.use_cuda and torch.cuda.is_available():
                device = torch.device(self.device)
            else:
                device = torch.device('cpu')

            state = torch.load(self.weights_path, map_location=device)
            net.load_state_dict(state)
            net.to(device)
            net.eval()
            self._net = net
            self._torch = torch

    def recognize_bgr(self, bgr: np.ndarray) -> PlateCandidate | None:
        if bgr is None or bgr.size == 0:
            return None
        self._ensure_loaded()
        torch = self._torch
        net = self._net

        resized = cv2.resize(bgr, self.img_size, interpolation=cv2.INTER_LINEAR)
        img = resized.astype('float32')
        img -= 127.5
        img *= 0.0078125
        img = np.transpose(img, (2, 0, 1))
        tensor = torch.from_numpy(img).unsqueeze(0)

        if self.use_cuda and torch.cuda.is_available():
            tensor = tensor.to(self.device)

        with torch.no_grad():
            prebs = net(tensor)
            probs = torch.softmax(prebs, dim=1)
            probs_np = probs.detach().cpu().numpy()

        preb = probs_np[0, :, :]
        labels = []
        confs = []
        for j in range(preb.shape[1]):
            idx = int(np.argmax(preb[:, j], axis=0))
            confs.append(float(preb[idx, j]))
            labels.append(idx)

        blank = len(CHARS) - 1
        no_repeat = []
        no_repeat_confs = []
        pre_c = labels[0]
        if pre_c != blank:
            no_repeat.append(pre_c)
            no_repeat_confs.append(confs[0])
        for idx, c in enumerate(labels):
            if (pre_c == c) or (c == blank):
                if c == blank:
                    pre_c = c
                continue
            no_repeat.append(c)
            no_repeat_confs.append(confs[idx])
            pre_c = c

        plate = ''.join(CHARS[i] for i in no_repeat if 0 <= i < len(CHARS))
        if not plate:
            return None
        confidence = float(np.mean(no_repeat_confs)) if no_repeat_confs else None
        return PlateCandidate(plate=plate, confidence=confidence, bbox=None)


_YOLO_CACHE: dict[str, Any] = {}
_YOLO_LOCK = threading.Lock()


def _load_yolo(model_path: str):
    from ultralytics import YOLO

    with _YOLO_LOCK:
        model = _YOLO_CACHE.get(model_path)
        if model is None:
            model = YOLO(model_path)
            _YOLO_CACHE[model_path] = model
        return model


def detect_plate_candidates(
    image_bgr: np.ndarray,
    model_path: str,
    conf: float = 0.5,
    max_det: int = 5,
) -> list[dict[str, Any]]:
    model = _load_yolo(model_path)
    start = time.time()
    results = model.predict(image_bgr, conf=conf, verbose=False, max_det=max_det)
    dt = time.time() - start
    if not results:
        return []
    r0 = results[0]
    names = getattr(r0, 'names', None) or getattr(model, 'names', None) or {}

    boxes = getattr(r0, 'boxes', None)
    if boxes is None:
        return []

    xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, 'cpu') else np.asarray(boxes.xyxy)
    confs = boxes.conf.cpu().numpy() if hasattr(boxes.conf, 'cpu') else np.asarray(boxes.conf)
    clss = boxes.cls.cpu().numpy() if hasattr(boxes.cls, 'cpu') else np.asarray(boxes.cls)

    h, w = image_bgr.shape[:2]
    items: list[dict[str, Any]] = []
    for i in range(len(xyxy)):
        x1, y1, x2, y2 = xyxy[i].tolist()
        x1 = max(0.0, min(float(x1), float(w - 1)))
        y1 = max(0.0, min(float(y1), float(h - 1)))
        x2 = max(0.0, min(float(x2), float(w - 1)))
        y2 = max(0.0, min(float(y2), float(h - 1)))
        cls_id = int(clss[i])
        cls_name = str(names.get(cls_id, cls_id))
        items.append(
            {
                'class_id': cls_id,
                'class_name': cls_name,
                'confidence': float(confs[i]),
                'bbox': {
                    'x': float(x1),
                    'y': float(y1),
                    'width': float(max(0.0, x2 - x1)),
                    'height': float(max(0.0, y2 - y1)),
                },
                'processing_time': dt,
            }
        )
    items.sort(key=lambda x: x['confidence'], reverse=True)
    return items


def crop_bgr(image_bgr: np.ndarray, bbox: dict[str, float], pad: float = 0.08) -> np.ndarray | None:
    h, w = image_bgr.shape[:2]
    x = float(bbox.get('x', 0.0))
    y = float(bbox.get('y', 0.0))
    bw = float(bbox.get('width', 0.0))
    bh = float(bbox.get('height', 0.0))
    if bw <= 1 or bh <= 1:
        return None

    px = bw * pad
    py = bh * pad
    x1 = int(max(0.0, x - px))
    y1 = int(max(0.0, y - py))
    x2 = int(min(float(w), x + bw + px))
    y2 = int(min(float(h), y + bh + py))
    if x2 <= x1 or y2 <= y1:
        return None
    return image_bgr[y1:y2, x1:x2].copy()


def decode_data_url_image(data_url: str) -> np.ndarray | None:
    if not data_url:
        return None
    s = data_url.strip()
    if ',' in s:
        s = s.split(',', 1)[1]
    try:
        raw = base64.b64decode(s)
    except Exception:
        return None
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def encode_image_to_data_url_jpeg(bgr: np.ndarray, quality: int = 80) -> str | None:
    if bgr is None or bgr.size == 0:
        return None
    ok, buf = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        return None
    b64 = base64.b64encode(buf.tobytes()).decode('ascii')
    return f'data:image/jpeg;base64,{b64}'


LOSS_RE = re.compile(r'Epoch:(?P<epoch>\d+).*Loss:\s*(?P<loss>\d+(\.\d+)?)')
ACC_RE = re.compile(r'\[Info\]\s*Test Accuracy:\s*(?P<acc>\d+(\.\d+)?)')


def parse_training_line(line: str) -> dict[str, Any] | None:
    m = LOSS_RE.search(line)
    if m:
        return {'type': 'loss', 'epoch': int(m.group('epoch')), 'value': float(m.group('loss'))}
    m = ACC_RE.search(line)
    if m:
        return {'type': 'val_acc', 'value': float(m.group('acc'))}
    return None


def safe_json_loads(data: str) -> Any:
    try:
        return json.loads(data)
    except Exception:
        return None

