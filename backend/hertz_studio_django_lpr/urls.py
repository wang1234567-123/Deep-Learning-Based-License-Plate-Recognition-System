from django.urls import path

from . import views


urlpatterns = [
    path('datasets/upload/', views.upload_dataset, name='lpr_dataset_upload'),
    path('datasets/', views.dataset_list, name='lpr_dataset_list'),
    path('train/start/', views.start_training, name='lpr_train_start'),
    path('train/jobs/', views.job_list, name='lpr_job_list'),
    path('train/jobs/<int:job_id>/', views.job_detail, name='lpr_job_detail'),
    path('train/jobs/<int:job_id>/cancel/', views.cancel_job, name='lpr_job_cancel'),
]

