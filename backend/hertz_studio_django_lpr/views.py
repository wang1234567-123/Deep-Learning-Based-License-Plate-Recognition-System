import os
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from hertz_studio_django_utils.responses.HertzResponse import HertzResponse

from .models import LprDataset, LprTrainingJob
from .services import parse_training_line, safe_json_loads


def _require_auth(request):
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return None, HertzResponse.unauthorized(message='未登录或登录已失效', code=401)
    return user, None


def _ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)


def _dataset_root_dir() -> Path:
    return Path(settings.MEDIA_ROOT) / 'lpr' / 'datasets'


def _train_root_dir() -> Path:
    return Path(settings.MEDIA_ROOT) / 'lpr' / 'train'


@csrf_exempt
@require_POST
def upload_dataset(request):
    user, err = _require_auth(request)
    if err:
        return err

    upload = request.FILES.get('zip_file') or request.FILES.get('file')
    name = (request.POST.get('name') or '').strip()
    description = (request.POST.get('description') or '').strip()
    if not upload:
        return HertzResponse.validation_error(message='缺少参数 zip_file', code=400)

    if not name:
        name = Path(getattr(upload, 'name', '') or 'dataset').stem

    ds_root = _dataset_root_dir()
    _ensure_dir(str(ds_root))
    ts = timezone.now().strftime('%Y%m%d_%H%M%S')
    folder = ds_root / f'{ts}_{int(time.time() * 1000)}'
    _ensure_dir(str(folder))
    zip_path = folder / 'dataset.zip'

    with open(zip_path, 'wb') as f:
        for chunk in upload.chunks():
            f.write(chunk)

    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(folder)

    extracted_root = folder
    candidates = [p for p in folder.iterdir() if p.is_dir() and p.name not in ['__MACOSX']]
    if len(candidates) == 1:
        extracted_root = candidates[0]

    train_dir = extracted_root / 'train'
    test_dir = extracted_root / 'test'
    if not train_dir.exists():
        train_dir = extracted_root
    if not test_dir.exists():
        test_dir = extracted_root

    ds = LprDataset.objects.create(
        name=name,
        root_folder_path=str(extracted_root),
        train_folder_path=str(train_dir),
        test_folder_path=str(test_dir),
        description=description,
    )

    return HertzResponse.success(
        data={
            'id': ds.id,
            'name': ds.name,
            'root_folder_path': ds.root_folder_path,
            'train_folder_path': ds.train_folder_path,
            'test_folder_path': ds.test_folder_path,
            'description': ds.description,
            'created_at': ds.created_at,
        },
        message='数据集导入成功',
    )


@require_GET
def dataset_list(request):
    user, err = _require_auth(request)
    if err:
        return err
    rows = []
    for ds in LprDataset.objects.order_by('-id')[:200]:
        rows.append(
            {
                'id': ds.id,
                'name': ds.name,
                'root_folder_path': ds.root_folder_path,
                'train_folder_path': ds.train_folder_path,
                'test_folder_path': ds.test_folder_path,
                'description': ds.description,
                'created_at': ds.created_at,
            }
        )
    return HertzResponse.success(data=rows, message='获取数据集列表成功')


def _lpr_train_script_path() -> Path:
    return Path(settings.BASE_DIR) / 'LPRNet_Pytorch-master' / 'LPRNet_Pytorch-master' / 'train_LPRNet.py'


def _spawn_train_job(job_id: int):
    job = LprTrainingJob.objects.get(id=job_id)
    dataset = job.dataset

    train_root = _train_root_dir()
    _ensure_dir(str(train_root))
    save_folder = train_root / f'job_{job_id}' / 'weights'
    _ensure_dir(str(save_folder))
    logs_path = train_root / f'job_{job_id}' / 'train.log'
    _ensure_dir(str(logs_path.parent))

    job.save_folder = str(save_folder)
    job.logs_path = str(logs_path)
    job.status = 'running'
    job.started_at = timezone.now()
    job.progress = 0.0
    job.last_metrics = {'loss': [], 'val_acc': []}
    job.save(update_fields=['save_folder', 'logs_path', 'status', 'started_at', 'progress', 'last_metrics'])

    script = _lpr_train_script_path()
    cmd = [
        os.fspath(getattr(sys, 'executable', 'python')),
        '-u',
        os.fspath(script),
        '--train_img_dirs',
        dataset.train_folder_path,
        '--test_img_dirs',
        dataset.test_folder_path,
        '--save_folder',
        str(save_folder) + os.sep,
        '--max_epoch',
        str(job.max_epoch),
        '--train_batch_size',
        str(job.train_batch_size),
        '--test_batch_size',
        str(job.test_batch_size),
        '--learning_rate',
        str(job.learning_rate),
        '--dropout_rate',
        str(job.dropout_rate),
        '--cuda',
        'True' if job.use_cuda else 'False',
    ]
    if job.pretrained_model_path:
        cmd.extend(['--pretrained_model', job.pretrained_model_path])

    proc = subprocess.Popen(
        cmd,
        cwd=os.fspath(script.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    job.pid = proc.pid
    job.save(update_fields=['pid'])

    channel_layer = get_channel_layer()
    cache_key = f'lpr:train:{job_id}:metrics'

    metrics = {'loss': [], 'val_acc': [], 'status': 'running', 'progress': 0.0}
    cache.set(cache_key, metrics, timeout=60 * 60 * 24)
    async_to_sync(channel_layer.group_send)(
        f'lpr_train_{job_id}',
        {'type': 'train.event', 'payload': {'type': 'status', 'status': 'running', 'job_id': job_id}},
    )

    last_epoch = 0
    with open(logs_path, 'a', encoding='utf-8') as logf:
        if proc.stdout is not None:
            for line in proc.stdout:
                logf.write(line)
                logf.flush()
                parsed = parse_training_line(line)
                if not parsed:
                    continue
                if parsed['type'] == 'loss':
                    last_epoch = max(last_epoch, int(parsed.get('epoch') or 0))
                    metrics['loss'].append({'epoch': int(parsed.get('epoch') or 0), 'value': float(parsed['value'])})
                elif parsed['type'] == 'val_acc':
                    metrics['val_acc'].append({'step': len(metrics['val_acc']) + 1, 'value': float(parsed['value'])})
                progress = float(min(100.0, (last_epoch / max(1, job.max_epoch)) * 100.0))
                metrics['progress'] = progress
                cache.set(cache_key, metrics, timeout=60 * 60 * 24)
                async_to_sync(channel_layer.group_send)(
                    f'lpr_train_{job_id}',
                    {'type': 'train.event', 'payload': {'type': 'metric', 'job_id': job_id, 'data': parsed, 'progress': progress}},
                )

    code = proc.wait()
    finished = timezone.now()
    if code == 0:
        status = 'completed'
        output_model = save_folder / 'Final_LPRNet_model.pth'
        job.output_model_path = str(output_model) if output_model.exists() else ''
    else:
        status = 'failed'
        job.error_message = f'训练进程退出码: {code}'

    job.status = status
    job.finished_at = finished
    job.progress = 100.0 if status == 'completed' else metrics.get('progress', 0.0)
    job.last_metrics = metrics
    job.save(update_fields=['status', 'finished_at', 'progress', 'last_metrics', 'error_message', 'output_model_path'])

    metrics['status'] = status
    cache.set(cache_key, metrics, timeout=60 * 60 * 24)
    async_to_sync(channel_layer.group_send)(
        f'lpr_train_{job_id}',
        {'type': 'train.event', 'payload': {'type': 'status', 'status': status, 'job_id': job_id}},
    )


@csrf_exempt
@require_POST
def start_training(request):
    user, err = _require_auth(request)
    if err:
        return err

    body = safe_json_loads((request.body or b'').decode('utf-8'))
    if not isinstance(body, dict):
        body = {}

    dataset_id = body.get('dataset_id') or request.POST.get('dataset_id')
    if not dataset_id:
        return HertzResponse.validation_error(message='缺少参数 dataset_id', code=400)

    try:
        dataset = LprDataset.objects.get(id=int(dataset_id))
    except Exception:
        return HertzResponse.not_found(message='数据集不存在', code=404)

    job = LprTrainingJob.objects.create(
        dataset=dataset,
        status='queued',
        max_epoch=int(body.get('max_epoch') or 15),
        train_batch_size=int(body.get('train_batch_size') or 128),
        test_batch_size=int(body.get('test_batch_size') or 120),
        learning_rate=float(body.get('learning_rate') or 0.1),
        dropout_rate=float(body.get('dropout_rate') or 0.5),
        use_cuda=bool(body.get('use_cuda', True)),
        device=str(body.get('device') or 'cuda:0'),
        pretrained_model_path=str(body.get('pretrained_model_path') or ''),
    )

    t = threading.Thread(target=_spawn_train_job, args=(job.id,), daemon=True)
    t.start()

    return HertzResponse.success(
        data={
            'id': job.id,
            'dataset_id': job.dataset_id,
            'dataset_name': dataset.name,
            'status': job.status,
            'created_at': job.created_at,
        },
        message='训练任务已创建',
    )


@require_GET
def job_list(request):
    user, err = _require_auth(request)
    if err:
        return err
    rows = []
    qs = LprTrainingJob.objects.select_related('dataset').order_by('-id')[:200]
    for job in qs:
        rows.append(
            {
                'id': job.id,
                'dataset_id': job.dataset_id,
                'dataset_name': job.dataset.name if job.dataset_id else '',
                'status': job.status,
                'progress': job.progress,
                'max_epoch': job.max_epoch,
                'train_batch_size': job.train_batch_size,
                'test_batch_size': job.test_batch_size,
                'learning_rate': job.learning_rate,
                'dropout_rate': job.dropout_rate,
                'use_cuda': job.use_cuda,
                'device': job.device,
                'pretrained_model_path': job.pretrained_model_path,
                'logs_path': job.logs_path,
                'output_model_path': job.output_model_path,
                'error_message': job.error_message,
                'created_at': job.created_at,
                'started_at': job.started_at,
                'finished_at': job.finished_at,
            }
        )
    return HertzResponse.success(data=rows, message='获取训练任务列表成功')


@require_GET
def job_detail(request, job_id: int):
    user, err = _require_auth(request)
    if err:
        return err
    try:
        job = LprTrainingJob.objects.select_related('dataset').get(id=job_id)
    except Exception:
        return HertzResponse.not_found(message='训练任务不存在', code=404)

    metrics = cache.get(f'lpr:train:{job_id}:metrics') or job.last_metrics or {}
    return HertzResponse.success(
        data={
            'id': job.id,
            'dataset_id': job.dataset_id,
            'dataset_name': job.dataset.name if job.dataset_id else '',
            'status': job.status,
            'progress': job.progress,
            'max_epoch': job.max_epoch,
            'train_batch_size': job.train_batch_size,
            'test_batch_size': job.test_batch_size,
            'learning_rate': job.learning_rate,
            'dropout_rate': job.dropout_rate,
            'use_cuda': job.use_cuda,
            'device': job.device,
            'pretrained_model_path': job.pretrained_model_path,
            'save_folder': job.save_folder,
            'logs_path': job.logs_path,
            'output_model_path': job.output_model_path,
            'error_message': job.error_message,
            'created_at': job.created_at,
            'started_at': job.started_at,
            'finished_at': job.finished_at,
            'metrics': metrics,
        },
        message='获取训练任务详情成功',
    )


@csrf_exempt
@require_POST
def cancel_job(request, job_id: int):
    user, err = _require_auth(request)
    if err:
        return err

    try:
        job = LprTrainingJob.objects.get(id=job_id)
    except Exception:
        return HertzResponse.not_found(message='训练任务不存在', code=404)

    if job.status not in ['queued', 'running']:
        return HertzResponse.fail(message='任务当前状态不支持取消', code=400)

    job.status = 'canceling'
    job.save(update_fields=['status'])

    try:
        import psutil

        if job.pid:
            p = psutil.Process(job.pid)
            p.terminate()
    except Exception:
        pass

    job.status = 'canceled'
    job.finished_at = timezone.now()
    job.save(update_fields=['status', 'finished_at'])

    cache.set(f'lpr:train:{job_id}:metrics', {'status': 'canceled'}, timeout=60 * 60 * 24)
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'lpr_train_{job_id}',
        {'type': 'train.event', 'payload': {'type': 'status', 'status': 'canceled', 'job_id': job_id}},
    )

    return HertzResponse.success(message='已取消训练任务')
