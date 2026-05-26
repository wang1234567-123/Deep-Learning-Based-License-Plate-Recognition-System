import { request } from '@/utils/hertz_request'

export interface LprDataset {
  id: number
  name: string
  root_folder_path: string
  train_folder_path: string
  test_folder_path: string
  description?: string
  created_at?: string
}

export interface LprTrainingJob {
  id: number
  dataset_id: number
  dataset_name: string
  status: 'queued' | 'running' | 'canceling' | 'completed' | 'failed' | 'canceled'
  progress: number
  max_epoch: number
  train_batch_size: number
  test_batch_size: number
  learning_rate: number
  dropout_rate: number
  use_cuda: boolean
  device: string
  pretrained_model_path?: string
  logs_path?: string
  output_model_path?: string
  error_message?: string
  created_at: string
  started_at?: string | null
  finished_at?: string | null
}

export interface StartLprTrainingPayload {
  dataset_id: number
  max_epoch?: number
  train_batch_size?: number
  test_batch_size?: number
  learning_rate?: number
  dropout_rate?: number
  use_cuda?: boolean
  device?: string
  pretrained_model_path?: string
}

export const lprApi = {
  async uploadDataset(payload: { zipFile: File; name?: string; description?: string }) {
    const form = new FormData()
    form.append('zip_file', payload.zipFile)
    if (payload.name) form.append('name', payload.name)
    if (payload.description) form.append('description', payload.description)
    return request.post('/api/lpr/datasets/upload/', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  async listDatasets(): Promise<{ success: boolean; data?: LprDataset[]; message?: string }> {
    return request.get('/api/lpr/datasets/')
  },

  async startTraining(payload: StartLprTrainingPayload): Promise<{ success: boolean; data?: any; message?: string }> {
    return request.post('/api/lpr/train/start/', payload)
  },

  async listJobs(): Promise<{ success: boolean; data?: LprTrainingJob[]; message?: string }> {
    return request.get('/api/lpr/train/jobs/')
  },

  async getJobDetail(jobId: number): Promise<{ success: boolean; data?: any; message?: string }> {
    return request.get(`/api/lpr/train/jobs/${jobId}/`)
  },

  async cancelJob(jobId: number): Promise<{ success: boolean; message?: string }> {
    return request.post(`/api/lpr/train/jobs/${jobId}/cancel/`)
  }
}

