import datetime
import json
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.exceptions import FieldError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from hertz_studio_django_auth.utils.decorators import no_login_required
from hertz_studio_django_utils.responses.HertzResponse import HertzResponse


@no_login_required
def index(request):
    """
    系统首页视图
    展示系统的基础介绍和功能特性
    """
    return render(request, 'index.html')


def _get_yolo_detection_record_model():
    try:
        return apps.get_model('hertz_studio_django_yolo', 'DetectionRecord')
    except Exception:
        return None


def _pick_field_name(model, candidates: list[str]) -> str | None:
    existing = {f.name for f in model._meta.fields}
    for name in candidates:
        if name in existing:
            return name
    return None


def _safe_filter(qs, **kwargs):
    try:
        return qs.filter(**kwargs)
    except FieldError:
        return qs


def _format_cell_value(value: Any) -> Any:
    if value is None:
        return ''
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat(sep=' ', timespec='seconds') if isinstance(value, datetime.datetime) else value.isoformat()
    if isinstance(value, (list, tuple, set)):
        return ', '.join(str(v) for v in value)
    return str(value)


def _parse_categories(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None and str(v).strip()]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        if s.startswith('[') or s.startswith('{'):
            try:
                import json

                loaded = json.loads(s)
                if isinstance(loaded, list):
                    return [str(v) for v in loaded if v is not None and str(v).strip()]
                if isinstance(loaded, dict):
                    return [str(k) for k in loaded.keys() if str(k).strip()]
            except Exception:
                pass
        if ',' in s:
            return [p.strip() for p in s.split(',') if p.strip()]
        return [s]
    return [str(value)]


def _file_value_to_url(value: Any) -> str:
    if value is None:
        return ''
    url = getattr(value, 'url', None)
    if isinstance(url, str) and url:
        return url
    return str(value)


def _file_value_to_path(value: Any) -> str | None:
    if value is None:
        return None
    path = getattr(value, 'path', None)
    if isinstance(path, str) and path:
        return path
    raw = str(value).strip()
    if not raw:
        return None
    raw = raw.replace('\\', '/')
    if len(raw) > 2 and raw[1] == ':':
        return raw
    if raw.startswith('/media/'):
        return str(Path(settings.MEDIA_ROOT) / raw[len('/media/'):])
    if raw.startswith('media/'):
        return str(Path(settings.BASE_DIR) / raw)
    return str(Path(settings.BASE_DIR) / raw)


def _require_auth(request):
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return None, HertzResponse.unauthorized(message='未登录或登录已失效', code=401)
    return user, None


def _get_request_user(request):
    user = getattr(request, 'user', None)
    if user and getattr(user, 'is_authenticated', False):
        return user
    return None


@csrf_exempt
@no_login_required
@require_POST
def token_refresh_override(request):
    def _encode_jwt(payload: dict[str, Any], expire_seconds: int, token_type: str) -> str:
        import jwt

        now = int(time.time())
        claims = dict(payload)
        claims.update({'type': token_type, 'iat': now, 'exp': now + int(expire_seconds)})
        secret = getattr(settings, 'JWT_SECRET_KEY', None) or settings.SECRET_KEY
        return jwt.encode(claims, secret, algorithm=getattr(settings, 'JWT_ALGORITHM', 'HS256'))

    try:
        body = (request.body or b'').decode('utf-8')
        data = json.loads(body) if body else {}
    except Exception:
        data = {}

    refresh_token = (data.get('refresh_token') or '').strip()
    if not refresh_token:
        return HertzResponse.validation_error(message='缺少参数 refresh_token', code=400)

    try:
        from hertz_studio_django_auth.models import HertzUser
        from hertz_studio_django_auth.utils.auth.token_utils import TokenUtils
    except Exception as e:
        return HertzResponse.error(message='token刷新失败', error=str(e), code=500)

    payload = None
    for method_name in ['decode_token', 'decode', 'verify_refresh_token', 'verify_token', 'decode_refresh_token']:
        if hasattr(TokenUtils, method_name):
            fn = getattr(TokenUtils, method_name)
            try:
                payload = fn(refresh_token)
                break
            except Exception:
                payload = None

    if payload is None:
        try:
            import jwt

            secret = getattr(settings, 'JWT_SECRET_KEY', None) or settings.SECRET_KEY
            payload = jwt.decode(
                refresh_token,
                secret,
                algorithms=[getattr(settings, 'JWT_ALGORITHM', 'HS256')],
                options={'verify_aud': False},
            )
        except Exception:
            payload = None

    if not isinstance(payload, dict):
        payload = {}

    user_id = payload.get('user_id') or payload.get('sub') or payload.get('id')
    user = None
    if user_id is not None:
        try:
            user = HertzUser.objects.filter(user_id=user_id).first() or HertzUser.objects.filter(id=user_id).first()
        except Exception:
            user = None

    if user is None:
        return HertzResponse.unauthorized(message='未登录或登录已失效', code=401)

    roles = []
    try:
        roles = list(user.roles.all())
    except Exception:
        roles = []

    user_data = {
        'user_id': str(getattr(user, 'user_id', getattr(user, 'id', ''))),
        'username': getattr(user, 'username', ''),
        'email': getattr(user, 'email', ''),
        'roles': [getattr(r, 'role_code', '') for r in roles if getattr(r, 'role_code', '')],
        'permissions': [],
    }

    try:
        token_data = TokenUtils.generate_token(user_data)
        if isinstance(token_data, (list, tuple)):
            token_data = next((item for item in token_data if isinstance(item, dict)), {})
        if not isinstance(token_data, dict):
            token_data = {}
        access_token = (
            token_data.get('access_token')
            or token_data.get('access')
            or token_data.get('token')
            or (token_data.get('data') or {}).get('access_token')
        )
        refresh_token_new = token_data.get('refresh_token') or token_data.get('refresh') or refresh_token
        if not access_token:
            access_token = _encode_jwt(
                user_data,
                getattr(settings, 'JWT_ACCESS_TOKEN_LIFETIME', 60 * 60 * 24),
                'access',
            )
        if not refresh_token_new:
            refresh_token_new = _encode_jwt(
                user_data,
                getattr(settings, 'JWT_REFRESH_TOKEN_LIFETIME', 60 * 60 * 24 * 7),
                'refresh',
            )
        return HertzResponse.success(message='token刷新成功', data={'access_token': access_token, 'refresh_token': refresh_token_new})
    except Exception as e:
        return HertzResponse.error(message='token刷新失败', error=str(e), code=500)


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
                if not (path.startswith('/') or (len(path) > 2 and path[1] == ':')):
                    from django.conf import settings as dj_settings

                    return str(dj_settings.BASE_DIR / path)
                return path
    return None


_LPR_RECOGNIZER = None
_LPR_RECOGNIZER_PATH = None


def _resolve_lpr_weights_path() -> str | None:
    base_dir = Path(settings.BASE_DIR)
    direct_candidates = [
        base_dir / 'LPRNet_Pytorch-master' / 'LPRNet_Pytorch-master' / 'weights' / 'Final_LPRNet_model.pth',
        base_dir / 'LPRNet_Pytorch-master' / 'weights' / 'Final_LPRNet_model.pth',
    ]
    for candidate in direct_candidates:
        if candidate.is_file():
            return str(candidate)

    train_root = base_dir / 'media' / 'lpr' / 'train'
    if train_root.exists():
        latest_match = None
        latest_mtime = -1.0
        for match in train_root.rglob('Final_LPRNet_model.pth'):
            try:
                mtime = match.stat().st_mtime
            except OSError:
                continue
            if mtime > latest_mtime:
                latest_match = match
                latest_mtime = mtime
        if latest_match is not None:
            return str(latest_match)

    return None


def _get_lpr_recognizer():
    global _LPR_RECOGNIZER, _LPR_RECOGNIZER_PATH
    weights_path = _resolve_lpr_weights_path()
    if not weights_path:
        return None
    if _LPR_RECOGNIZER is not None and _LPR_RECOGNIZER_PATH == weights_path:
        return _LPR_RECOGNIZER
    from hertz_studio_django_lpr.services import LprNetRecognizer

    _LPR_RECOGNIZER = LprNetRecognizer(weights_path=weights_path, use_cuda=True, device='cuda:0')
    _LPR_RECOGNIZER_PATH = weights_path
    return _LPR_RECOGNIZER


def _recognize_plate_from_record(record) -> dict[str, Any] | None:
    file_path = _file_value_to_path(getattr(record, 'original_file', None))
    if not file_path or not Path(file_path).is_file():
        return None

    img = cv2.imread(file_path)
    if img is None:
        return None

    try:
        from hertz_studio_django_lpr.services import crop_bgr, detect_plate_candidates
    except Exception:
        return None

    model_path = _get_enabled_yolo_model_path()
    rec = _get_lpr_recognizer()
    if not model_path or rec is None:
        return None

    detections = detect_plate_candidates(img, model_path=model_path, conf=0.3)
    if not detections:
        return None

    cand = detections[0]
    bbox = cand.get('bbox')
    crop = crop_bgr(img, bbox) if bbox else None
    if crop is None:
        return None

    plate = rec.recognize_bgr(crop)
    if plate is None or not plate.plate:
        return None

    info = {
        'plate_number': plate.plate,
        'plate_confidence': plate.confidence,
        'plate_bbox': bbox,
    }

    try:
        from hertz_studio_django_lpr.models import PlateRecognitionRecord

        PlateRecognitionRecord.objects.create(
            detection_record_id=int(getattr(record, 'id')),
            user_id=getattr(record, 'user_id', None),
            user_name=getattr(record, 'user_name', '') or '',
            plate_number=info['plate_number'],
            plate_confidence=info['plate_confidence'],
            bbox=info['plate_bbox'] or {},
        )
    except Exception:
        pass

    return info


@csrf_exempt
@no_login_required
@require_POST
def yolo_detection_with_lpr(request):
    user = _get_request_user(request)

    upload = request.FILES.get('file')
    if not upload:
        return HertzResponse.validation_error(message='缺少参数 file', code=400)

    confidence_threshold = request.POST.get('confidence_threshold') or request.GET.get('confidence_threshold') or 0.5
    try:
        conf = float(confidence_threshold)
    except Exception:
        conf = 0.5

    plate_number = ''
    plate_confidence = None
    plate_bbox = None

    raw = upload.read()
    try:
        upload.seek(0)
    except Exception:
        pass

    img = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is not None:
        try:
            from hertz_studio_django_lpr.services import crop_bgr, detect_plate_candidates
        except Exception:
            detect_plate_candidates = None
            crop_bgr = None

        try:
            model_path = None
            model_id = (request.POST.get('model_id') or request.GET.get('model_id') or '').strip()
            if model_id:
                try:
                    YoloModel = apps.get_model('hertz_studio_django_yolo', 'YoloModel')
                    model = YoloModel.objects.filter(id=int(model_id)).first()
                    if model:
                        for candidate in ['model_path', 'best_model_path', 'weights_path', 'model_file', 'pt_path']:
                            if hasattr(model, candidate):
                                val = getattr(model, candidate)
                                if isinstance(val, str) and val.strip():
                                    path = val.strip()
                                    if not (path.startswith('/') or (len(path) > 2 and path[1] == ':')):
                                        from django.conf import settings as dj_settings

                                        path = str(dj_settings.BASE_DIR / path)
                                    model_path = path
                                    break
                except Exception:
                    model_path = None
            if not model_path:
                model_path = _get_enabled_yolo_model_path()
            if model_path and detect_plate_candidates and crop_bgr:
                detections = detect_plate_candidates(img, model_path=model_path, conf=conf)
                if detections:
                    rec = _get_lpr_recognizer()
                    cand = detections[0]
                    plate_bbox = cand.get('bbox')
                    crop = crop_bgr(img, plate_bbox) if plate_bbox else None
                    if crop is not None and rec is not None:
                        plate = rec.recognize_bgr(crop)
                        if plate is not None:
                            plate_number = plate.plate
                            plate_confidence = plate.confidence
        except Exception:
            plate_number = ''
            plate_confidence = None
            plate_bbox = None

    try:
        from hertz_studio_django_yolo import views as yolo_views
    except Exception as e:
        return HertzResponse.error(message='YOLO模块未安装或未就绪', error=str(e), code=500)

    resp = yolo_views.yolo_detection(request)
    try:
        payload = json.loads(resp.content.decode('utf-8'))
    except Exception:
        return resp

    data_obj = payload.get('data')
    if isinstance(data_obj, dict):
        data_obj['plate_number'] = plate_number
        data_obj['plate_confidence'] = plate_confidence
        data_obj['plate_bbox'] = plate_bbox
    else:
        payload['data'] = {
            'plate_number': plate_number,
            'plate_confidence': plate_confidence,
            'plate_bbox': plate_bbox,
        }

    detection_id = None
    if isinstance(payload.get('data'), dict):
        detection_id = (
            payload['data'].get('detection_id')
            or payload['data'].get('id')
            or payload['data'].get('record_id')
            or payload['data'].get('detection_record_id')
        )

    if detection_id and plate_number:
        try:
            from hertz_studio_django_lpr.models import PlateRecognitionRecord

            PlateRecognitionRecord.objects.create(
                detection_record_id=int(detection_id),
                user_id=getattr(user, 'user_id', None) or getattr(user, 'id', None),
                user_name=getattr(user, 'username', '') or '',
                plate_number=plate_number,
                plate_confidence=plate_confidence,
                bbox=plate_bbox or {},
            )
        except Exception:
            pass

    return HertzResponse.custom(
        success=bool(payload.get('success', True)),
        message=str(payload.get('message') or ''),
        data=payload.get('data'),
        code=int(payload.get('code') or 200),
    )


@no_login_required
@require_GET
def yolo_detections_with_plate(request):
    DetectionRecord = _get_yolo_detection_record_model()
    if DetectionRecord is None:
        return HertzResponse.error(message='YOLO模块未安装或未就绪', code=500)

    page = int(request.GET.get('page', 1) or 1)
    page_size = int(request.GET.get('page_size', 20) or 20)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)

    user_id = (request.GET.get('user_id') or '').strip()
    search = (request.GET.get('search') or '').strip()
    class_filter = (request.GET.get('class_filter') or '').strip()
    start_date = (request.GET.get('start_date') or '').strip()
    end_date = (request.GET.get('end_date') or '').strip()

    created_field = _pick_field_name(DetectionRecord, ['created_at', 'created_time', 'create_time', 'created'])
    type_field = _pick_field_name(DetectionRecord, ['detection_type', 'type', 'file_type'])
    object_count_field = _pick_field_name(DetectionRecord, ['object_count', 'objects_count', 'count'])
    avg_conf_field = _pick_field_name(DetectionRecord, ['avg_confidence', 'average_confidence'])
    model_used_field = _pick_field_name(DetectionRecord, ['model_used', 'model_name'])
    categories_field = _pick_field_name(DetectionRecord, ['detected_categories', 'categories', 'detected_classes', 'class_names'])

    qs = DetectionRecord.objects.all()
    if user_id:
        qs = _safe_filter(qs, user_id=user_id)

    if created_field and start_date:
        qs = _safe_filter(qs, **{f'{created_field}__date__gte': start_date})
    if created_field and end_date:
        qs = _safe_filter(qs, **{f'{created_field}__date__lte': end_date})

    if search:
        conditions = Q()
        for f in ['original_filename', 'result_filename', 'original_file', 'result_file', 'source_file']:
            if _pick_field_name(DetectionRecord, [f]):
                conditions |= Q(**{f'{f}__icontains': search})
        if conditions:
            qs = qs.filter(conditions)

    if class_filter and categories_field:
        qs = _safe_filter(qs, **{f'{categories_field}__icontains': class_filter})

    if created_field:
        qs = qs.order_by(f'-{created_field}')

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    records = []
    ids = []
    for record in page_obj.object_list:
        rid = getattr(record, 'id', None)
        ids.append(rid)
        records.append(
            {
                'id': rid,
                'original_file': _file_value_to_url(getattr(record, 'original_file', None)),
                'result_file': _file_value_to_url(getattr(record, 'result_file', None)),
                'original_filename': getattr(record, 'original_filename', ''),
                'result_filename': getattr(record, 'result_filename', ''),
                'detection_type': getattr(record, type_field, '') if type_field else '',
                'model_name': getattr(record, model_used_field, '') if model_used_field else '',
                'object_count': getattr(record, object_count_field, 0) if object_count_field else 0,
                'detected_categories': _parse_categories(getattr(record, categories_field, None)) if categories_field else [],
                'confidence_scores': getattr(record, 'confidence_scores', []) or [],
                'avg_confidence': getattr(record, avg_conf_field, 0) if avg_conf_field else 0,
                'processing_time': getattr(record, 'processing_time', 0) or 0,
                'created_at': getattr(record, created_field, None) if created_field else None,
            }
        )

    plate_map: dict[int, dict[str, Any]] = {}
    if ids:
        try:
            from hertz_studio_django_lpr.models import PlateRecognitionRecord

            for pr in PlateRecognitionRecord.objects.filter(detection_record_id__in=ids).order_by('-created_at'):
                did = int(pr.detection_record_id)
                if did not in plate_map:
                    plate_map[did] = {
                        'plate_number': pr.plate_number,
                        'plate_confidence': pr.plate_confidence,
                        'plate_bbox': pr.bbox,
                    }
        except Exception:
            plate_map = {}

    for r in records:
        info = plate_map.get(int(r['id'])) if r.get('id') is not None else None
        if info:
            r.update(info)
        else:
            source_record = next((obj for obj in page_obj.object_list if getattr(obj, 'id', None) == r.get('id')), None)
            backfilled = _recognize_plate_from_record(source_record) if source_record is not None else None
            if backfilled:
                r.update(backfilled)
            else:
                r.update({'plate_number': '', 'plate_confidence': None, 'plate_bbox': None})

    return HertzResponse.success(
        data={'records': records, 'total': paginator.count, 'page': page, 'page_size': page_size},
        message='获取检测记录列表成功',
    )


@no_login_required
@require_GET
def yolo_detection_detail_with_plate(request, pk: int):
    DetectionRecord = _get_yolo_detection_record_model()
    if DetectionRecord is None:
        return HertzResponse.error(message='YOLO模块未安装或未就绪', code=500)
    try:
        record = DetectionRecord.objects.get(id=pk)
    except Exception:
        return HertzResponse.not_found(message='检测记录不存在', code=404)

    created_field = _pick_field_name(DetectionRecord, ['created_at', 'created_time', 'create_time', 'created'])
    type_field = _pick_field_name(DetectionRecord, ['detection_type', 'type', 'file_type'])
    avg_conf_field = _pick_field_name(DetectionRecord, ['avg_confidence', 'average_confidence'])
    model_used_field = _pick_field_name(DetectionRecord, ['model_used', 'model_name'])
    categories_field = _pick_field_name(DetectionRecord, ['detected_categories', 'categories', 'detected_classes', 'class_names'])
    object_count_field = _pick_field_name(DetectionRecord, ['object_count', 'objects_count', 'count'])

    data = {
        'id': getattr(record, 'id', None),
        'original_file': _file_value_to_url(getattr(record, 'original_file', None)),
        'result_file': _file_value_to_url(getattr(record, 'result_file', None)),
        'original_filename': getattr(record, 'original_filename', ''),
        'result_filename': getattr(record, 'result_filename', ''),
        'detection_type': getattr(record, type_field, '') if type_field else '',
        'model_name': getattr(record, model_used_field, '') if model_used_field else '',
        'object_count': getattr(record, object_count_field, 0) if object_count_field else 0,
        'detected_categories': _parse_categories(getattr(record, categories_field, None)) if categories_field else [],
        'confidence_scores': getattr(record, 'confidence_scores', []) or [],
        'avg_confidence': getattr(record, avg_conf_field, 0) if avg_conf_field else 0,
        'processing_time': getattr(record, 'processing_time', 0) or 0,
        'created_at': getattr(record, created_field, None) if created_field else None,
    }

    try:
        from hertz_studio_django_lpr.models import PlateRecognitionRecord

        pr = PlateRecognitionRecord.objects.filter(detection_record_id=pk).order_by('-created_at').first()
        if pr:
            data.update({'plate_number': pr.plate_number, 'plate_confidence': pr.plate_confidence, 'plate_bbox': pr.bbox})
        else:
            backfilled = _recognize_plate_from_record(record)
            if backfilled:
                data.update(backfilled)
            else:
                data.update({'plate_number': '', 'plate_confidence': None, 'plate_bbox': None})
    except Exception:
        backfilled = _recognize_plate_from_record(record)
        if backfilled:
            data.update(backfilled)
        else:
            data.update({'plate_number': '', 'plate_confidence': None, 'plate_bbox': None})

    return HertzResponse.success(data=data, message='获取检测记录详情成功')


@no_login_required
def yolo_detection_stats(request):
    DetectionRecord = _get_yolo_detection_record_model()
    if DetectionRecord is None:
        return HertzResponse.error(message='YOLO模块未安装或未就绪', code=500)

    user_id = request.GET.get('user_id')

    created_field = _pick_field_name(DetectionRecord, ['created_at', 'created_time', 'create_time', 'created'])
    type_field = _pick_field_name(DetectionRecord, ['detection_type', 'type', 'file_type'])
    categories_field = _pick_field_name(DetectionRecord, ['detected_categories', 'categories', 'detected_classes', 'class_names'])

    qs = DetectionRecord.objects.all()
    if user_id:
        qs = _safe_filter(qs, user_id=user_id)

    total_detections = qs.count()
    if type_field:
        total_images = qs.filter(**{type_field: 'image'}).count()
    else:
        total_images = total_detections

    start_date = timezone.localdate() - datetime.timedelta(days=6)
    recent_activity: list[dict[str, Any]] = []
    if created_field:
        daily = (
            qs.filter(**{f'{created_field}__date__gte': start_date})
            .annotate(day=TruncDate(created_field))
            .values('day')
            .annotate(count=Count('id'))
            .order_by('day')
        )
        daily_map = {row['day'].isoformat(): int(row['count']) for row in daily if row.get('day')}
        for i in range(7):
            d = (start_date + datetime.timedelta(days=i)).isoformat()
            recent_activity.append({'date': d, 'count': daily_map.get(d, 0)})
    else:
        for i in range(7):
            d = (start_date + datetime.timedelta(days=i)).isoformat()
            recent_activity.append({'date': d, 'count': 0})

    class_counts: dict[str, int] = {}
    if categories_field:
        for raw in qs.values_list(categories_field, flat=True):
            for name in _parse_categories(raw):
                class_counts[name] = class_counts.get(name, 0) + 1

    return HertzResponse.success(
        data={
            'total_detections': total_detections,
            'total_images': total_images,
            'class_counts': class_counts,
            'recent_activity': recent_activity,
        },
        message='获取检测统计成功',
    )


@no_login_required
def yolo_detection_export(request):
    DetectionRecord = _get_yolo_detection_record_model()
    if DetectionRecord is None:
        return HertzResponse.error(message='YOLO模块未安装或未就绪', code=500)

    user_id = request.GET.get('user_id')
    if not user_id:
        return HertzResponse.validation_error(message='缺少参数 user_id', code=400)

    search = (request.GET.get('search') or '').strip()
    class_filter = (request.GET.get('class_filter') or '').strip()
    start_date = (request.GET.get('start_date') or '').strip()
    end_date = (request.GET.get('end_date') or '').strip()

    created_field = _pick_field_name(DetectionRecord, ['created_at', 'created_time', 'create_time', 'created'])
    type_field = _pick_field_name(DetectionRecord, ['detection_type', 'type', 'file_type'])
    object_count_field = _pick_field_name(DetectionRecord, ['object_count', 'objects_count', 'count'])
    avg_conf_field = _pick_field_name(DetectionRecord, ['avg_confidence', 'average_confidence'])
    model_used_field = _pick_field_name(DetectionRecord, ['model_used', 'model_name'])
    categories_field = _pick_field_name(DetectionRecord, ['detected_categories', 'categories', 'detected_classes', 'class_names'])

    qs = DetectionRecord.objects.all()
    qs = _safe_filter(qs, user_id=user_id)

    if created_field and start_date:
        qs = _safe_filter(qs, **{f'{created_field}__date__gte': start_date})
    if created_field and end_date:
        qs = _safe_filter(qs, **{f'{created_field}__date__lte': end_date})

    if search:
        conditions = Q()
        for f in ['original_filename', 'result_filename', 'original_file', 'result_file', 'source_file']:
            if _pick_field_name(DetectionRecord, [f]):
                conditions |= Q(**{f'{f}__icontains': search})
        if conditions:
            qs = qs.filter(conditions)

    if class_filter and categories_field:
        qs = _safe_filter(qs, **{f'{categories_field}__icontains': class_filter})

    if created_field:
        qs = qs.order_by(f'-{created_field}')

    try:
        from openpyxl import Workbook
    except Exception:
        return HertzResponse.error(message='导出依赖 openpyxl 未安装', code=500)

    plate_map: dict[int, dict[str, Any]] = {}
    try:
        from hertz_studio_django_lpr.models import PlateRecognitionRecord

        record_ids = [rid for rid in qs.values_list('id', flat=True) if rid is not None]
        if record_ids:
            for pr in PlateRecognitionRecord.objects.filter(detection_record_id__in=record_ids).order_by('-created_at'):
                did = int(pr.detection_record_id)
                if did not in plate_map:
                    plate_map[did] = {
                        'plate_number': pr.plate_number,
                        'plate_confidence': pr.plate_confidence,
                    }
    except Exception:
        plate_map = {}

    wb = Workbook()
    ws = wb.active
    ws.title = 'detections'

    headers = ['ID', '时间', '检测类型', '目标数', '平均置信度', '检测类别', '使用模型', '车牌号', '车牌置信度']
    ws.append(headers)

    for record in qs.iterator():
        record_id = getattr(record, 'id', '')
        created_value = getattr(record, created_field, '') if created_field else ''
        detection_type = getattr(record, type_field, '') if type_field else ''
        object_count = getattr(record, object_count_field, '') if object_count_field else ''
        avg_confidence = getattr(record, avg_conf_field, '') if avg_conf_field else ''
        categories = getattr(record, categories_field, '') if categories_field else ''
        model_used = getattr(record, model_used_field, '') if model_used_field else ''
        plate_info = plate_map.get(int(record_id)) if record_id not in ['', None] else None
        if plate_info:
            plate_number = (plate_info or {}).get('plate_number', '')
            plate_confidence = (plate_info or {}).get('plate_confidence', '')
        else:
            backfilled = _recognize_plate_from_record(record)
            plate_number = (backfilled or {}).get('plate_number', '')
            plate_confidence = (backfilled or {}).get('plate_confidence', '')

        ws.append(
            [
                _format_cell_value(record_id),
                _format_cell_value(created_value),
                _format_cell_value(detection_type),
                _format_cell_value(object_count),
                _format_cell_value(avg_confidence),
                _format_cell_value(categories),
                _format_cell_value(model_used),
                _format_cell_value(plate_number),
                _format_cell_value(plate_confidence),
            ]
        )

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"detections_{user_id}_{timezone.localdate().isoformat()}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def operation_log_list_override(request):
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return HertzResponse.unauthorized(message='未登录或登录已失效', code=401)

    try:
        from hertz_studio_django_log.models import OperationLog
    except Exception as e:
        return HertzResponse.error(message='日志模块未安装或未就绪', error=str(e), code=500)
    try:
        from django.db.utils import OperationalError, ProgrammingError
    except Exception:
        OperationalError = Exception
        ProgrammingError = Exception

    page = int(request.GET.get('page', 1) or 1)
    page_size = int(request.GET.get('page_size', 20) or 20)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)

    user_id = (request.GET.get('user_id') or '').strip()
    username = (request.GET.get('username') or '').strip()
    operation_type = (request.GET.get('operation_type') or request.GET.get('action_type') or '').strip()
    operation_module = (request.GET.get('operation_module') or request.GET.get('module') or '').strip()
    status = (request.GET.get('status') or '').strip()
    ip_address = (request.GET.get('ip_address') or '').strip()
    start_date = (request.GET.get('start_date') or '').strip()
    end_date = (request.GET.get('end_date') or '').strip()
    request_method = (request.GET.get('request_method') or '').strip()
    request_path = (request.GET.get('request_path') or '').strip()
    keyword = (request.GET.get('keyword') or '').strip()

    try:
        qs = OperationLog.objects.all()
    except (OperationalError, ProgrammingError):
        data = {
            'count': 0,
            'next': None,
            'previous': None,
            'results': [],
            'logs': [],
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': 0,
                'total_pages': 0,
                'has_next': False,
                'has_previous': False,
            },
        }
        return HertzResponse.success(data=data, message='获取操作日志列表成功')

    for field in ['created_at', 'create_time', 'created_time']:
        if _pick_field_name(OperationLog, [field]):
            qs = qs.order_by(f'-{field}')
            break
    else:
        qs = qs.order_by('-id')

    if user_id:
        qs = _safe_filter(qs, user_id=user_id)
        qs = _safe_filter(qs, user=user_id)

    if username:
        qs = _safe_filter(qs, username__icontains=username)
        qs = _safe_filter(qs, user__username__icontains=username)

    if operation_type:
        qs = _safe_filter(qs, action_type=operation_type)
        qs = _safe_filter(qs, operation_type=operation_type)

    if operation_module:
        qs = _safe_filter(qs, module__icontains=operation_module)
        qs = _safe_filter(qs, operation_module__icontains=operation_module)

    if status:
        qs = _safe_filter(qs, status=status)

    if ip_address:
        qs = _safe_filter(qs, ip_address__icontains=ip_address)

    if request_method:
        qs = _safe_filter(qs, request_method__iexact=request_method)

    if request_path:
        qs = _safe_filter(qs, request_path__icontains=request_path)

    if keyword:
        conditions = Q()
        for f in ['operation_description', 'description', 'request_path', 'request_method', 'module', 'operation_module']:
            if _pick_field_name(OperationLog, [f]):
                conditions |= Q(**{f'{f}__icontains': keyword})
        if conditions:
            qs = qs.filter(conditions)

    created_field = _pick_field_name(OperationLog, ['created_at', 'create_time', 'created_time'])
    if created_field and start_date:
        qs = _safe_filter(qs, **{f'{created_field}__gte': start_date})
    if created_field and end_date:
        qs = _safe_filter(qs, **{f'{created_field}__lte': end_date})

    try:
        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page)
    except (OperationalError, ProgrammingError):
        data = {
            'count': 0,
            'next': None,
            'previous': None,
            'results': [],
            'logs': [],
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': 0,
                'total_pages': 0,
                'has_next': False,
                'has_previous': False,
            },
        }
        return HertzResponse.success(data=data, message='获取操作日志列表成功')

    results: list[dict[str, Any]] = []
    for obj in page_obj.object_list:
        obj_user = getattr(obj, 'user', None)
        created_value = getattr(obj, created_field, None) if created_field else getattr(obj, 'created_at', None)
        results.append(
            {
                'id': getattr(obj, 'id', None) or getattr(obj, 'log_id', None),
                'log_id': getattr(obj, 'log_id', None) or getattr(obj, 'id', None),
                'user': (
                    {
                        'id': getattr(obj_user, 'id', None),
                        'username': getattr(obj_user, 'username', None),
                        'email': getattr(obj_user, 'email', None),
                    }
                    if obj_user
                    else None
                ),
                'username': getattr(obj, 'username', None) or getattr(obj_user, 'username', None),
                'operation_type': getattr(obj, 'operation_type', None) or getattr(obj, 'action_type', None),
                'action_type': getattr(obj, 'action_type', None) or getattr(obj, 'operation_type', None),
                'action_type_display': getattr(obj, 'action_type_display', None),
                'operation_module': getattr(obj, 'operation_module', None) or getattr(obj, 'module', None),
                'module': getattr(obj, 'module', None) or getattr(obj, 'operation_module', None),
                'operation_description': getattr(obj, 'operation_description', None) or getattr(obj, 'description', None),
                'description': getattr(obj, 'description', None) or getattr(obj, 'operation_description', None),
                'ip_address': getattr(obj, 'ip_address', None),
                'request_method': getattr(obj, 'request_method', None),
                'request_path': getattr(obj, 'request_path', None),
                'response_status': getattr(obj, 'response_status', None),
                'status': getattr(obj, 'status', None),
                'status_display': getattr(obj, 'status_display', None),
                'is_success': getattr(obj, 'is_success', None),
                'execution_time': getattr(obj, 'execution_time', None),
                'created_at': _format_cell_value(created_value) if created_value else None,
            }
        )

    data = {
        'count': paginator.count,
        'next': None,
        'previous': None,
        'results': results,
        'logs': results,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_count': paginator.count,
            'total_pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        },
    }
    return HertzResponse.success(data=data, message='获取操作日志列表成功')
