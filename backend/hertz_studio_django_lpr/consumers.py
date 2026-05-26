import json
import time
from typing import Any

import cv2
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.apps import apps
from django.conf import settings
from django.core.cache import cache

from .services import (
    LprNetRecognizer,
    crop_bgr,
    decode_data_url_image,
    detect_plate_candidates,
    encode_image_to_data_url_jpeg,
)


def _get_enabled_yolo_model_path() -> str | None:
    try:
        YoloModel = apps.get_model('hertz_studio_django_yolo', 'YoloModel')
    except Exception:
        return None

    enabled_field = None
    for name in ['is_enabled', 'is_active', 'enabled', 'active']:
        if hasattr(YoloModel, name):
            enabled_field = name
            break

    qs = YoloModel.objects.all()
    if enabled_field:
        qs = qs.filter(**{enabled_field: True})
    model = qs.order_by('-id').first()
    if not model:
        return None

    for candidate in ['model_path', 'best_model_path', 'weights_path', 'model_file', 'pt_path']:
        if hasattr(model, candidate):
            val = getattr(model, candidate)
            if isinstance(val, str) and val.strip():
                path = val.strip()
                if not settings.BASE_DIR:
                    return path
                if not (path.startswith('/') or (len(path) > 2 and path[1] == ':')):
                    return str(settings.BASE_DIR / path)
                return path
    return None


def _get_lpr_weights_path() -> str:
    base = settings.BASE_DIR
    return str(base / 'LPRNet_Pytorch-master' / 'LPRNet_Pytorch-master' / 'weights' / 'Final_LPRNet_model.pth')


_RECOGNIZER: LprNetRecognizer | None = None


def _get_recognizer() -> LprNetRecognizer:
    global _RECOGNIZER
    if _RECOGNIZER is not None:
        return _RECOGNIZER
    weights_path = _get_lpr_weights_path()
    _RECOGNIZER = LprNetRecognizer(weights_path=weights_path, use_cuda=True, device='cuda:0')
    return _RECOGNIZER


class YoloLiveLprConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.is_detecting = False
        await self.accept()

    async def disconnect(self, close_code):
        self.is_detecting = False

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except Exception:
            await self.send(text_data=json.dumps({'type': 'error', 'message': '数据格式错误'}))
            return

        msg_type = payload.get('type')
        action = payload.get('action')
        if msg_type == 'start_detection' or action == 'start':
            self.is_detecting = True
            await self.send(text_data=json.dumps({'type': 'status', 'message': 'ok'}))
            return
        if msg_type == 'stop_detection' or action == 'stop':
            self.is_detecting = False
            await self.send(text_data=json.dumps({'type': 'status', 'message': 'stopped'}))
            return

        if msg_type != 'detect_frame':
            return
        if not self.is_detecting:
            return

        image_data = payload.get('image') or ''
        conf = float(payload.get('confidence') or 0.5)
        send_frame = bool(payload.get('send_frame', True))
        frame = decode_data_url_image(image_data)
        if frame is None:
            await self.send(text_data=json.dumps({'type': 'error', 'message': '图像解码失败'}))
            return

        model_path = await sync_to_async(_get_enabled_yolo_model_path)()
        if not model_path:
            await self.send(text_data=json.dumps({'type': 'error', 'message': '未找到可用YOLO模型'}))
            return

        start = time.time()
        detections = await sync_to_async(detect_plate_candidates)(frame, model_path=model_path, conf=conf)
        object_count = len(detections)
        categories = [d['class_name'] for d in detections]
        confidence_scores = [d['confidence'] for d in detections]
        avg_conf = float(sum(confidence_scores) / object_count) if object_count else 0.0

        plate_number = ''
        plate_confidence = None
        plate_bbox = None
        if detections:
            rec = _get_recognizer()
            cand = detections[0]
            crop = crop_bgr(frame, cand['bbox'])
            if crop is not None:
                plate = await sync_to_async(rec.recognize_bgr)(crop)
                if plate is not None:
                    plate_number = plate.plate
                    plate_confidence = plate.confidence
                    plate_bbox = cand['bbox']

        rendered = None
        if send_frame:
            vis = frame.copy()
            for det in detections[:10]:
                b = det['bbox']
                x1 = int(b['x'])
                y1 = int(b['y'])
                x2 = int(b['x'] + b['width'])
                y2 = int(b['y'] + b['height'])
                cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"{det['class_name']} {det['confidence']:.2f}"
                cv2.putText(vis, label, (x1, max(0, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            if plate_number and plate_bbox:
                b = plate_bbox
                x1 = int(b['x'])
                y1 = int(b['y'])
                cv2.putText(vis, plate_number, (x1, max(0, y1 - 22)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
            rendered = encode_image_to_data_url_jpeg(vis, quality=75)

        processing_time = time.time() - start
        await self.send(
            text_data=json.dumps(
                {
                    'type': 'detection',
                    'timestamp': time.strftime('%H:%M:%S', time.localtime()),
                    'object_count': object_count,
                    'categories': categories,
                    'confidence_scores': confidence_scores,
                    'avg_confidence': avg_conf,
                    'processing_time': processing_time,
                    'frame': rendered,
                    'plate_number': plate_number,
                    'plate_confidence': plate_confidence,
                },
                ensure_ascii=False,
            )
        )


class LprTrainConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.job_id = self.scope['url_route']['kwargs']['job_id']
        self.group_name = f'lpr_train_{self.job_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        cached = cache.get(f'lpr:train:{self.job_id}:metrics')
        if cached:
            await self.send(text_data=json.dumps({'type': 'sync', 'data': cached}, ensure_ascii=False))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        return

    async def train_event(self, event: dict[str, Any]):
        await self.send(text_data=json.dumps(event.get('payload', {}), ensure_ascii=False))
