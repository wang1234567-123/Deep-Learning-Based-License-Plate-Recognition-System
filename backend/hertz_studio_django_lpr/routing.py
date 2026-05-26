from django.urls import re_path

from . import consumers


websocket_urlpatterns = [
    re_path(r'^ws/yolo/live/$', consumers.YoloLiveLprConsumer.as_asgi()),
    re_path(r'^ws/lpr/train/(?P<job_id>\d+)/$', consumers.LprTrainConsumer.as_asgi()),
]

