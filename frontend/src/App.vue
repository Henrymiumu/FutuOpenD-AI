<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api } from './api/client.js'

const STORAGE_KEY = 'futu-market-ai-settings'

const loading = reactive({
  snapshot: false,
  analyze: false,
  testAi: false,
  opend: false,
})

const error = ref('')
const info = ref('')

const opend = reactive({
  host: '127.0.0.1',
  port: 11111,
  connected: false,
  detail: null,
})

const market = reactive({
  codesInput: 'HK.00700, US.AAPL, HK.09988',
  snapshots: [],
})

const providers = ref([])

const ai = reactive({
  provider: 'ollama',
  api_key: '',
  base_url: '',
  model: '',
  temperature: 0.4,
  max_tokens: 2048,
})

const analyzeForm = reactive({
  question: '請分析這些股票的近期表現、風險與觀察重點。',
  language: 'zh-TW',
  include_kline: true,
  kline_num: 30,
  kline_type: 'K_DAY',
})

const analysis = ref(null)
const testResult = ref(null)

const selectedProvider = computed(() =>
  providers.value.find((p) => p.id === ai.provider)
)

const needsApiKey = computed(() => selectedProvider.value?.requires_api_key)

function parseCodes() {
  return market.codesInput
    .split(/[\s,;]+/)
    .map((c) => c.trim())
    .filter(Boolean)
}

function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const s = JSON.parse(raw)
    if (s.opend) Object.assign(opend, s.opend)
    if (s.ai) Object.assign(ai, s.ai)
    if (s.codesInput) market.codesInput = s.codesInput
    if (s.analyzeForm) Object.assign(analyzeForm, s.analyzeForm)
  } catch {
    /* ignore */
  }
}

function saveSettings() {
  const payload = {
    opend: { host: opend.host, port: opend.port },
    ai: {
      provider: ai.provider,
      api_key: ai.api_key,
      base_url: ai.base_url,
      model: ai.model,
      temperature: ai.temperature,
      max_tokens: ai.max_tokens,
    },
    codesInput: market.codesInput,
    analyzeForm: { ...analyzeForm },
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
}

watch([ai, () => market.codesInput, analyzeForm, () => opend.host, () => opend.port], saveSettings, {
  deep: true,
})

function applyProviderDefaults(id, force = false) {
  const p = providers.value.find((x) => x.id === id)
  if (!p) return
  if (force || !ai.base_url) ai.base_url = p.base_url
  if (force || !ai.model) ai.model = p.model
}

function onProviderChange() {
  const p = selectedProvider.value
  if (!p) return
  ai.base_url = p.base_url
  ai.model = p.model
  if (!p.requires_api_key) {
    // keep key in case user switches back
  }
}

function fmtNum(v, digits = 2) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
}

function changeClass(rate) {
  const n = Number(rate)
  if (Number.isNaN(n) || n === 0) return ''
  return n > 0 ? 'up' : 'down'
}

function fmtPct(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(2)}%`
}

async function refreshOpend() {
  loading.opend = true
  error.value = ''
  try {
    const data = await api.opendConfig(opend.host, opend.port)
    opend.connected = !!data.connected
    opend.detail = data
    if (!data.connected) {
      error.value = data.error || 'OpenD 未連線。請先啟動 Futu OpenD。'
    } else {
      info.value = `OpenD 已連線 ${opend.host}:${opend.port}`
    }
  } catch (e) {
    opend.connected = false
    error.value = e.message
  } finally {
    loading.opend = false
  }
}

async function fetchSnapshot() {
  const codes = parseCodes()
  if (!codes.length) {
    error.value = '請輸入至少一個股票代碼，例如 HK.00700'
    return
  }
  loading.snapshot = true
  error.value = ''
  info.value = ''
  try {
    const data = await api.snapshot(codes)
    market.snapshots = data.data || []
    info.value = `已取得 ${data.count} 筆報價`
  } catch (e) {
    error.value = e.message
  } finally {
    loading.snapshot = false
  }
}

function buildAiConfig() {
  return {
    provider: ai.provider,
    api_key: ai.api_key || null,
    base_url: ai.base_url || null,
    model: ai.model || null,
    temperature: Number(ai.temperature),
    max_tokens: Number(ai.max_tokens),
  }
}

async function testAi() {
  loading.testAi = true
  error.value = ''
  testResult.value = null
  try {
    const data = await api.testAi(buildAiConfig())
    testResult.value = data
    info.value = `AI 連線成功：${data.provider} / ${data.model}`
  } catch (e) {
    error.value = e.message
  } finally {
    loading.testAi = false
  }
}

async function runAnalyze() {
  const codes = parseCodes()
  if (!codes.length) {
    error.value = '請輸入股票代碼後再分析'
    return
  }
  loading.analyze = true
  error.value = ''
  analysis.value = null
  try {
    // refresh snapshot first for UI
    try {
      const snap = await api.snapshot(codes)
      market.snapshots = snap.data || []
    } catch {
      /* analyze endpoint will also fetch */
    }

    const data = await api.analyze({
      codes,
      include_kline: analyzeForm.include_kline,
      kline_code: codes[0],
      kline_num: Number(analyzeForm.kline_num),
      kline_type: analyzeForm.kline_type,
      question: analyzeForm.question,
      language: analyzeForm.language,
      ai: buildAiConfig(),
    })
    analysis.value = data
    info.value = `分析完成（${data.ai.provider} / ${data.ai.model}）`
  } catch (e) {
    error.value = e.message
  } finally {
    loading.analyze = false
  }
}

onMounted(async () => {
  loadSettings()
  try {
    const data = await api.providers()
    providers.value = data.providers || []
    applyProviderDefaults(ai.provider, false)
    if (!ai.model || !ai.base_url) {
      onProviderChange()
    }
  } catch (e) {
    error.value = `無法載入 AI providers：${e.message}（請確認後端已啟動）`
  }
  try {
    const st = await api.opendStatus()
    opend.connected = !!st.connected
    opend.detail = st
  } catch {
    opend.connected = false
  }
})
</script>

<template>
  <div class="page">
    <header class="header">
      <div class="brand">
        <div class="logo">F</div>
        <div>
          <h1>Futu Market AI</h1>
          <p class="muted">OpenD 市場資訊 · 多模型 LLM 分析</p>
        </div>
      </div>
      <div class="header-status">
        <span class="badge" :class="opend.connected ? 'ok' : 'err'">
          <span class="dot" />
          OpenD {{ opend.connected ? '已連線' : '未連線' }}
        </span>
        <span class="badge">{{ ai.provider }} · {{ ai.model || 'default' }}</span>
      </div>
    </header>

    <div v-if="error" class="alert error">{{ error }}</div>
    <div v-if="info && !error" class="alert info">{{ info }}</div>

    <div class="grid">
      <!-- OpenD -->
      <section class="card panel">
        <div class="panel-head">
          <h2>1. Futu OpenD</h2>
          <button class="btn btn-ghost" :disabled="loading.opend" @click="refreshOpend">
            <span v-if="loading.opend" class="spinner" />
            測試連線
          </button>
        </div>
        <div class="row-2">
          <div class="field">
            <label>Host</label>
            <input v-model="opend.host" class="mono" placeholder="127.0.0.1" />
          </div>
          <div class="field">
            <label>Port</label>
            <input v-model.number="opend.port" type="number" class="mono" />
          </div>
        </div>
        <p class="hint muted">
          請先在本機啟動 Futu OpenD（預設 11111）。需有 Futu 帳戶與行情權限。
        </p>
      </section>

      <!-- AI Settings -->
      <section class="card panel">
        <div class="panel-head">
          <h2>2. AI 模型設定</h2>
          <button class="btn btn-success" :disabled="loading.testAi" @click="testAi">
            <span v-if="loading.testAi" class="spinner" />
            測試 AI
          </button>
        </div>

        <div class="field">
          <label>Provider（使用者可選）</label>
          <select v-model="ai.provider" @change="onProviderChange">
            <option v-for="p in providers" :key="p.id" :value="p.id">
              {{ p.name }}
            </option>
          </select>
        </div>
        <p v-if="selectedProvider" class="hint muted">{{ selectedProvider.description }}</p>

        <div class="row-2">
          <div class="field">
            <label>Model</label>
            <input v-model="ai.model" class="mono" placeholder="llama3.1:8b" />
          </div>
          <div class="field">
            <label>Base URL</label>
            <input v-model="ai.base_url" class="mono" placeholder="http://127.0.0.1:11434" />
          </div>
        </div>

        <div class="field">
          <label>
            API Key
            <span v-if="needsApiKey" class="req">* 必填</span>
            <span v-else class="muted">（Ollama / 本地通常不需要）</span>
          </label>
          <input
            v-model="ai.api_key"
            type="password"
            autocomplete="off"
            placeholder="sk-... 僅存在瀏覽器 localStorage"
          />
        </div>

        <div class="row-2">
          <div class="field">
            <label>Temperature</label>
            <input v-model.number="ai.temperature" type="number" min="0" max="2" step="0.1" />
          </div>
          <div class="field">
            <label>Max Tokens</label>
            <input v-model.number="ai.max_tokens" type="number" min="64" max="8192" step="64" />
          </div>
        </div>

        <div v-if="testResult" class="test-ok muted mono">
          測試回覆：{{ (testResult.content || '').slice(0, 120) }}
        </div>
      </section>

      <!-- Market -->
      <section class="card panel span-2">
        <div class="panel-head">
          <h2>3. 市場資訊</h2>
          <div class="actions">
            <button class="btn btn-ghost" :disabled="loading.snapshot" @click="fetchSnapshot">
              <span v-if="loading.snapshot" class="spinner" />
              取得報價
            </button>
            <button class="btn btn-primary" :disabled="loading.analyze" @click="runAnalyze">
              <span v-if="loading.analyze" class="spinner" />
              AI 分析
            </button>
          </div>
        </div>

        <div class="field">
          <label>股票代碼（逗號分隔，格式：市場.代碼）</label>
          <input v-model="market.codesInput" class="mono" placeholder="HK.00700, US.AAPL, SH.600519" />
        </div>

        <div class="row-3">
          <div class="field">
            <label>分析問題</label>
            <textarea v-model="analyzeForm.question" rows="2" />
          </div>
          <div class="side-fields">
            <div class="field">
              <label>語言</label>
              <select v-model="analyzeForm.language">
                <option value="zh-TW">繁體中文</option>
                <option value="zh-CN">简体中文</option>
                <option value="en">English</option>
              </select>
            </div>
            <div class="field">
              <label>K 線</label>
              <select v-model="analyzeForm.kline_type">
                <option value="K_DAY">日K</option>
                <option value="K_60M">60分</option>
                <option value="K_WEEK">週K</option>
              </select>
            </div>
            <label class="check">
              <input v-model="analyzeForm.include_kline" type="checkbox" />
              附帶 K 線給 AI
            </label>
          </div>
        </div>

        <div v-if="market.snapshots.length" class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>代碼</th>
                <th>名稱</th>
                <th>現價</th>
                <th>漲跌幅</th>
                <th>開盤</th>
                <th>最高</th>
                <th>最低</th>
                <th>昨收</th>
                <th>成交量</th>
                <th>成交額</th>
                <th>PE</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in market.snapshots" :key="row.code">
                <td class="mono">{{ row.code }}</td>
                <td>{{ row.name || '—' }}</td>
                <td class="mono">{{ fmtNum(row.last_price) }}</td>
                <td class="mono" :class="changeClass(row.change_rate ?? row.change_rate_calc)">
                  {{ fmtPct(row.change_rate ?? row.change_rate_calc) }}
                </td>
                <td class="mono">{{ fmtNum(row.open_price) }}</td>
                <td class="mono">{{ fmtNum(row.high_price) }}</td>
                <td class="mono">{{ fmtNum(row.low_price) }}</td>
                <td class="mono">{{ fmtNum(row.prev_close_price) }}</td>
                <td class="mono">{{ fmtNum(row.volume, 0) }}</td>
                <td class="mono">{{ fmtNum(row.turnover, 0) }}</td>
                <td class="mono">{{ fmtNum(row.pe_ratio) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="hint muted">尚未載入報價。輸入代碼後按「取得報價」或直接「AI 分析」。</p>
      </section>

      <!-- Analysis result -->
      <section class="card panel span-2">
        <div class="panel-head">
          <h2>4. AI 分析結果</h2>
          <span v-if="analysis" class="badge">
            {{ analysis.ai.provider }} / {{ analysis.ai.model }}
          </span>
        </div>
        <div v-if="loading.analyze" class="loading-block">
          <span class="spinner" /> 正在向 LLM 請求分析，本地模型可能需要數十秒…
        </div>
        <div v-else-if="analysis" class="analysis-body">{{ analysis.analysis }}</div>
        <p v-else class="hint muted">分析結果會顯示在這裡。免責：僅供參考，不構成投資建議。</p>
      </section>
    </div>

    <footer class="footer muted">
      <span>Futu OpenD + Vue 3 + FastAPI · 支援 Ollama llama3.1:8b 與主流 API LLM</span>
      <span>API Key 僅存於本機瀏覽器，不會寫入伺服器磁碟</span>
    </footer>
  </div>
</template>

<style scoped>
.page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 1.5rem 1.25rem 3rem;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
}

.brand {
  display: flex;
  gap: 0.9rem;
  align-items: center;
}

.logo {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  font-weight: 800;
  font-size: 1.4rem;
  color: white;
  background: linear-gradient(135deg, #3b82f6, #06b6d4);
  box-shadow: 0 8px 24px rgba(59, 130, 246, 0.35);
}

.header h1 {
  margin: 0;
  font-size: 1.35rem;
  letter-spacing: -0.02em;
}

.header p {
  margin: 0.1rem 0 0;
  font-size: 0.9rem;
}

.header-status {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-top: 1rem;
}

.span-2 {
  grid-column: 1 / -1;
}

.panel {
  padding: 1.1rem 1.15rem 1.2rem;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.9rem;
}

.panel-head h2 {
  margin: 0;
  font-size: 1.05rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.row-3 {
  display: grid;
  grid-template-columns: 1.6fr 0.9fr;
  gap: 0.9rem;
  margin: 0.85rem 0 1rem;
}

.side-fields {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.hint {
  font-size: 0.85rem;
  margin: 0.75rem 0 0;
}

.req {
  color: var(--warn);
  margin-left: 0.25rem;
}

.check {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.9rem;
  color: var(--muted);
}

.test-ok {
  margin-top: 0.75rem;
  font-size: 0.82rem;
  padding: 0.55rem 0.7rem;
  border-radius: 8px;
  background: rgba(52, 211, 153, 0.08);
  border: 1px solid rgba(52, 211, 153, 0.2);
}

.loading-block {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  color: var(--muted);
  padding: 1rem 0;
}

.footer {
  margin-top: 1.5rem;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  font-size: 0.8rem;
}

@media (max-width: 860px) {
  .grid,
  .row-2,
  .row-3 {
    grid-template-columns: 1fr;
  }
}
</style>
