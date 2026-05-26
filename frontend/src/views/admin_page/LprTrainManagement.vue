<template>
  <div class="lpr-train-page">
    <div class="page-header">
      <h2 class="page-title">车牌识别模型管理</h2>
      <p class="page-description">导入车牌数据集并一键启动 LPRNet 训练，实时查看 Loss 与验证集识别准确率</p>
    </div>

    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :lg="10">
        <a-card title="数据集管理" class="panel-card">
          <a-form layout="vertical">
            <a-form-item label="数据集压缩包（ZIP）">
              <a-upload
                v-model:file-list="datasetFileList"
                :before-upload="beforeDatasetUpload"
                accept=".zip"
                :max-count="1"
              >
                <a-button>选择 ZIP</a-button>
              </a-upload>
            </a-form-item>
            <a-form-item label="数据集名称">
              <a-input v-model:value="datasetForm.name" placeholder="可选，不填则使用文件名" />
            </a-form-item>
            <a-form-item label="描述">
              <a-textarea v-model:value="datasetForm.description" :rows="2" placeholder="可选" />
            </a-form-item>
            <a-space>
              <a-button type="primary" :loading="uploadingDataset" :disabled="datasetFileList.length === 0" @click="uploadDataset">
                导入数据集
              </a-button>
              <a-button @click="loadDatasets" :loading="loadingDatasets">刷新</a-button>
            </a-space>
          </a-form>

          <a-divider />

          <a-table
            :columns="datasetColumns"
            :data-source="datasets"
            :loading="loadingDatasets"
            row-key="id"
            size="small"
            :pagination="{ pageSize: 5 }"
          />
        </a-card>
      </a-col>

      <a-col :xs="24" :lg="14">
        <a-card title="训练控制" class="panel-card">
          <a-form layout="vertical">
            <a-row :gutter="12">
              <a-col :xs="24" :md="12">
                <a-form-item label="选择数据集">
                  <a-select v-model:value="trainForm.dataset_id" placeholder="请选择数据集" style="width: 100%;">
                    <a-select-option v-for="ds in datasets" :key="ds.id" :value="ds.id">
                      {{ ds.name }}
                    </a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item label="训练轮数 (max_epoch)">
                  <a-input-number v-model:value="trainForm.max_epoch" :min="1" :max="200" style="width: 100%;" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="8">
                <a-form-item label="train_batch_size">
                  <a-input-number v-model:value="trainForm.train_batch_size" :min="1" :max="1024" style="width: 100%;" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="8">
                <a-form-item label="test_batch_size">
                  <a-input-number v-model:value="trainForm.test_batch_size" :min="1" :max="1024" style="width: 100%;" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="8">
                <a-form-item label="learning_rate">
                  <a-input-number v-model:value="trainForm.learning_rate" :min="0.000001" :max="10" :step="0.01" style="width: 100%;" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="8">
                <a-form-item label="dropout_rate">
                  <a-input-number v-model:value="trainForm.dropout_rate" :min="0" :max="1" :step="0.05" style="width: 100%;" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="8">
                <a-form-item label="use_cuda">
                  <a-switch v-model:checked="trainForm.use_cuda" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="8">
                <a-form-item label="device">
                  <a-input v-model:value="trainForm.device" placeholder="cuda:0 / cpu" />
                </a-form-item>
              </a-col>
              <a-col :xs="24">
                <a-form-item label="pretrained_model_path（可选）">
                  <a-input v-model:value="trainForm.pretrained_model_path" placeholder="留空则从头训练" />
                </a-form-item>
              </a-col>
            </a-row>

            <a-space>
              <a-button type="primary" :loading="startingTraining" :disabled="!trainForm.dataset_id" @click="startTraining">
                一键启动训练
              </a-button>
              <a-button danger :disabled="!currentJobId" @click="cancelTraining" :loading="cancelingTraining">
                停止训练
              </a-button>
              <a-tag v-if="trainStatus" :color="trainStatusColor">{{ trainStatus }}</a-tag>
              <a-tag v-if="typeof trainProgress === 'number'">进度 {{ trainProgress.toFixed(0) }}%</a-tag>
            </a-space>
          </a-form>
        </a-card>

        <a-row :gutter="[16, 16]" style="margin-top: 16px;">
          <a-col :xs="24" :md="12">
            <a-card title="训练损失 Loss" class="panel-card">
              <div ref="lossChartEl" class="chart"></div>
            </a-card>
          </a-col>
          <a-col :xs="24" :md="12">
            <a-card title="验证集识别准确率 Acc" class="panel-card">
              <div ref="accChartEl" class="chart"></div>
            </a-card>
          </a-col>
        </a-row>
      </a-col>
    </a-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { message } from 'ant-design-vue'
import * as echarts from 'echarts'
import { lprApi, type LprDataset, type StartLprTrainingPayload } from '@/api/lpr'
import { getWsBaseUrl } from '@/utils/hertz_url'

const datasets = ref<LprDataset[]>([])
const loadingDatasets = ref(false)
const uploadingDataset = ref(false)
const datasetFileList = ref<any[]>([])
const datasetForm = ref({ name: '', description: '' })

const startingTraining = ref(false)
const cancelingTraining = ref(false)
const currentJobId = ref<number | null>(null)
const trainStatus = ref<string>('')
const trainProgress = ref<number>(0)

const trainForm = ref<StartLprTrainingPayload>({
  dataset_id: 0,
  max_epoch: 15,
  train_batch_size: 128,
  test_batch_size: 120,
  learning_rate: 0.1,
  dropout_rate: 0.5,
  use_cuda: true,
  device: 'cuda:0',
  pretrained_model_path: ''
})

const datasetColumns = [
  { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: 'train', dataIndex: 'train_folder_path', key: 'train_folder_path', ellipsis: true },
  { title: 'test', dataIndex: 'test_folder_path', key: 'test_folder_path', ellipsis: true }
]

const beforeDatasetUpload = (file: File) => {
  const ok = (file.name || '').toLowerCase().endsWith('.zip')
  if (!ok) {
    message.error('仅支持 ZIP 数据集压缩包')
    return false
  }
  return false
}

const loadDatasets = async () => {
  loadingDatasets.value = true
  try {
    const resp: any = await lprApi.listDatasets()
    if (resp?.success) {
      datasets.value = resp.data || []
      if (!trainForm.value.dataset_id && datasets.value.length > 0) {
        trainForm.value.dataset_id = datasets.value[0].id
      }
    } else {
      message.error(resp?.message || '获取数据集失败')
    }
  } catch (e: any) {
    message.error('获取数据集失败')
  } finally {
    loadingDatasets.value = false
  }
}

const uploadDataset = async () => {
  if (datasetFileList.value.length === 0) return
  const file = datasetFileList.value[0]?.originFileObj || datasetFileList.value[0]
  if (!file) return
  uploadingDataset.value = true
  try {
    const resp: any = await lprApi.uploadDataset({
      zipFile: file,
      name: datasetForm.value.name || undefined,
      description: datasetForm.value.description || undefined
    })
    if (resp?.success) {
      message.success('数据集导入成功')
      datasetFileList.value = []
      datasetForm.value = { name: '', description: '' }
      await loadDatasets()
    } else {
      message.error(resp?.message || '数据集导入失败')
    }
  } catch (e: any) {
    message.error('数据集导入失败')
  } finally {
    uploadingDataset.value = false
  }
}

let ws: WebSocket | null = null

const lossChartEl = ref<HTMLDivElement | null>(null)
const accChartEl = ref<HTMLDivElement | null>(null)
let lossChart: echarts.ECharts | null = null
let accChart: echarts.ECharts | null = null

const lossSeries = ref<Array<{ epoch: number; value: number }>>([])
const accSeries = ref<Array<{ step: number; value: number }>>([])

const trainStatusColor = computed(() => {
  if (trainStatus.value === 'running') return 'processing'
  if (trainStatus.value === 'completed') return 'success'
  if (trainStatus.value === 'failed') return 'error'
  if (trainStatus.value === 'canceled') return 'default'
  return 'default'
})

const renderCharts = () => {
  if (lossChart && lossChartEl.value) {
    lossChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: lossSeries.value.map(i => String(i.epoch)) },
      yAxis: { type: 'value' },
      series: [{ type: 'line', smooth: true, data: lossSeries.value.map(i => i.value), name: 'loss' }]
    })
  }
  if (accChart && accChartEl.value) {
    accChart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: accSeries.value.map(i => String(i.step)) },
      yAxis: { type: 'value', min: 0, max: 1 },
      series: [{ type: 'line', smooth: true, data: accSeries.value.map(i => i.value), name: 'val_acc' }]
    })
  }
}

const connectTrainWs = (jobId: number) => {
  if (ws) {
    try { ws.close() } catch {}
    ws = null
  }
  const url = `${getWsBaseUrl()}/ws/lpr/train/${jobId}/`
  ws = new WebSocket(url)
  ws.onopen = () => {}
  ws.onerror = () => {
    message.error('训练推送连接失败')
  }
  ws.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data)
      if (msg.type === 'sync' && msg.data) {
        const m = msg.data
        lossSeries.value = Array.isArray(m.loss) ? m.loss : []
        accSeries.value = Array.isArray(m.val_acc) ? m.val_acc : []
        if (typeof m.progress === 'number') trainProgress.value = m.progress
        if (typeof m.status === 'string') trainStatus.value = m.status
        renderCharts()
        return
      }
      if (msg.type === 'metric') {
        const d = msg.data
        if (d?.type === 'loss') {
          lossSeries.value = [...lossSeries.value, { epoch: d.epoch, value: d.value }]
        } else if (d?.type === 'val_acc') {
          accSeries.value = [...accSeries.value, { step: accSeries.value.length + 1, value: d.value }]
        }
        if (typeof msg.progress === 'number') trainProgress.value = msg.progress
        renderCharts()
        return
      }
      if (msg.type === 'status') {
        trainStatus.value = msg.status || ''
        renderCharts()
        return
      }
    } catch {}
  }
  ws.onclose = () => {
    ws = null
  }
}

const startTraining = async () => {
  if (!trainForm.value.dataset_id) {
    message.warning('请选择数据集')
    return
  }
  startingTraining.value = true
  try {
    const resp: any = await lprApi.startTraining(trainForm.value)
    if (resp?.success && resp.data?.id) {
      const jobId = Number(resp.data.id)
      currentJobId.value = jobId
      trainStatus.value = 'queued'
      trainProgress.value = 0
      lossSeries.value = []
      accSeries.value = []
      renderCharts()
      connectTrainWs(jobId)
      message.success('训练任务已启动')
    } else {
      message.error(resp?.message || '启动训练失败')
    }
  } catch (e: any) {
    message.error('启动训练失败')
  } finally {
    startingTraining.value = false
  }
}

const cancelTraining = async () => {
  if (!currentJobId.value) return
  cancelingTraining.value = true
  try {
    const resp: any = await lprApi.cancelJob(currentJobId.value)
    if (resp?.success) {
      trainStatus.value = 'canceled'
      message.success('已停止训练')
      try { ws?.close() } catch {}
      ws = null
    } else {
      message.error(resp?.message || '停止训练失败')
    }
  } catch (e: any) {
    message.error('停止训练失败')
  } finally {
    cancelingTraining.value = false
  }
}

onMounted(async () => {
  await loadDatasets()
  if (lossChartEl.value) lossChart = echarts.init(lossChartEl.value)
  if (accChartEl.value) accChart = echarts.init(accChartEl.value)
  renderCharts()
  window.addEventListener('resize', resizeCharts)
})

const resizeCharts = () => {
  try { lossChart?.resize() } catch {}
  try { accChart?.resize() } catch {}
}

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  try { ws?.close() } catch {}
  ws = null
  try { lossChart?.dispose() } catch {}
  try { accChart?.dispose() } catch {}
  lossChart = null
  accChart = null
})
</script>

<style scoped lang="scss">
.lpr-train-page {
  padding: 0;
}
.page-header {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  padding: 32px 28px;
  margin-bottom: 24px;
  border-bottom: 0.5px solid rgba(0, 0, 0, 0.08);
  .page-title {
    margin: 0 0 4px 0;
    font-size: 24px;
    font-weight: 600;
    color: #1d1d1f;
  }
  .page-description {
    margin: 0;
    color: #86868b;
    font-size: 14px;
  }
}
.panel-card {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border: 0.5px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
}
.chart {
  width: 100%;
  height: 320px;
}
</style>

