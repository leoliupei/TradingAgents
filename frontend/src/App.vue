<template>
  <el-container class="app-shell">
    <el-header class="topbar">
      <section class="brand-row">
        <div>
          <h1>TradingAgents</h1>
          <p>Local Web Console</p>
        </div>
      </section>

      <section class="current-run">
        <span class="kicker">Current Run</span>
        <h2>{{ selectedRun ? `${selectedRun.ticker} · ${selectedRun.analysis_date}` : "No run selected" }}</h2>
      </section>

      <section class="topbar-actions">
        <el-tag :type="healthOk ? 'success' : 'danger'" effect="light">
          {{ healthOk ? "API Ready" : "Offline" }}
        </el-tag>
        <div class="run-meta" v-if="selectedRun">
          <el-tag :type="statusType(selectedRun.status)" effect="dark">
            {{ selectedRun.status }}
          </el-tag>
          <span>{{ selectedRun.llm_provider }}</span>
          <span>{{ selectedRun.analysts.join(", ") }}</span>
        </div>
        <el-button type="primary" :icon="VideoPlay" @click="configDrawerOpen = true">
          New Run
        </el-button>
        <el-button :icon="Tickets" @click="eventsDrawerOpen = true">
          Events {{ events.length }}
        </el-button>
        <el-button :icon="Refresh" @click="refreshAll">Refresh</el-button>
        <el-button
          :icon="CircleClose"
          :disabled="!selectedRun || !isActive(selectedRun.status)"
          @click="stopRun"
        >
          Cancel
        </el-button>
      </section>
    </el-header>

    <el-main class="workspace">
      <section class="runs-panel panel">
        <div class="panel-heading">
          <h3>Runs</h3>
          <el-button text :icon="Refresh" @click="refreshRuns" />
        </div>
        <el-table
          :data="runs"
          height="100%"
          highlight-current-row
          :row-class-name="runRowClass"
          @row-click="selectRun"
        >
          <el-table-column prop="ticker" label="Ticker" width="88" />
          <el-table-column prop="status" label="Status" width="112">
            <template #default="{ row }">
              <el-tag size="small" :type="statusType(row.status)">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="analysis_date" label="Date" min-width="116" />
          <el-table-column prop="created_at" label="Created" min-width="146">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>
      </section>

      <section class="report-panel panel">
        <div class="panel-heading">
          <h3>Reports</h3>
          <el-segmented v-model="reportMode" :options="reportModes" />
        </div>
        <el-tabs v-model="activeReport" class="report-tabs" @tab-change="loadActiveReport">
          <el-tab-pane
            v-for="section in reportSections"
            :key="section"
            :name="section"
            :label="sectionLabel(section)"
          />
        </el-tabs>
        <article v-if="reportHtml && reportMode === 'Rendered'" class="markdown-body" v-html="reportHtml" />
        <pre v-else-if="reportContent" class="raw-report">{{ reportContent }}</pre>
        <el-empty v-else description="No report yet" />
      </section>
    </el-main>

    <el-drawer
      v-model="configDrawerOpen"
      title="New Run"
      direction="ltr"
      size="420px"
      class="config-drawer"
    >
      <el-form label-position="top" class="run-form" @submit.prevent>
        <el-form-item label="Ticker">
          <el-input v-model="form.ticker" placeholder="LI / NVDA / 700.HK" clearable />
        </el-form-item>

        <div class="two-col">
          <el-form-item label="Date">
            <el-date-picker
              v-model="form.analysis_date"
              value-format="YYYY-MM-DD"
              type="date"
              class="full-width"
            />
          </el-form-item>
          <el-form-item label="Asset">
            <el-segmented v-model="form.asset_type" :options="assetOptions" />
          </el-form-item>
        </div>

        <el-form-item label="Analysts">
          <el-checkbox-group v-model="form.analysts" class="analyst-grid">
            <el-checkbox-button
              v-for="item in options?.analysts || []"
              :key="item.value"
              :value="item.value"
            >
              {{ item.label.replace(" Analyst", "") }}
            </el-checkbox-button>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item label="Provider">
          <el-select v-model="form.llm_provider" class="full-width" filterable>
            <el-option
              v-for="item in options?.providers || []"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>

        <div class="two-col">
          <el-form-item label="Quick Model">
            <el-input v-model="form.quick_think_llm" />
          </el-form-item>
          <el-form-item label="Deep Model">
            <el-input v-model="form.deep_think_llm" />
          </el-form-item>
        </div>

        <el-form-item label="Depth">
          <el-slider v-model="form.research_depth" :min="1" :max="5" show-stops />
        </el-form-item>

        <el-collapse class="advanced">
          <el-collapse-item title="Advanced" name="advanced">
            <el-form-item label="Output Language">
              <el-select v-model="form.output_language" class="full-width">
                <el-option label="Chinese" value="Chinese" />
                <el-option label="English" value="English" />
              </el-select>
            </el-form-item>
            <el-form-item label="Backend URL">
              <el-input v-model="form.backend_url" placeholder="Optional OpenAI-compatible base URL" />
            </el-form-item>
            <el-form-item label="OpenAI Reasoning Effort">
              <el-select v-model="form.openai_reasoning_effort" class="full-width" clearable>
                <el-option label="minimal" value="minimal" />
                <el-option label="low" value="low" />
                <el-option label="medium" value="medium" />
                <el-option label="high" value="high" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-switch v-model="form.checkpoint_enabled" active-text="Checkpoint" />
            </el-form-item>
          </el-collapse-item>
        </el-collapse>

        <div class="action-row">
          <el-button type="primary" :icon="VideoPlay" :loading="creating" @click="startRun">
            Run
          </el-button>
          <el-button @click="configDrawerOpen = false">Close</el-button>
        </div>
      </el-form>
    </el-drawer>

    <el-drawer
      v-model="eventsDrawerOpen"
      title="Events"
      direction="rtl"
      size="420px"
      class="events-drawer"
    >
      <el-scrollbar class="event-list">
        <div v-for="event in events" :key="`${event.type}-${event._index}`" class="event-item">
          <div class="event-topline">
            <el-tag size="small" :type="eventType(event.type)">{{ event.type }}</el-tag>
            <time>{{ formatTime(event.timestamp) }}</time>
          </div>
          <p v-if="event.type === 'report_updated'">
            {{ sectionLabel(String(event.section || "")) }} updated · {{ event.size }} bytes
          </p>
          <p v-else-if="event.type === 'tool_call'">{{ event.name }}</p>
          <p v-else-if="event.content">{{ event.content }}</p>
          <p v-else-if="event.message">{{ event.message }}</p>
          <p v-else-if="event.decision">{{ event.decision }}</p>
        </div>
        <el-empty v-if="!events.length" description="No events yet" />
      </el-scrollbar>
    </el-drawer>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { CircleClose, Refresh, Tickets, VideoPlay } from "@element-plus/icons-vue";
import { marked } from "marked";
import DOMPurify from "dompurify";
import dayjs from "dayjs";
import {
  cancelRun,
  createRun,
  fetchOptions,
  getEvents,
  getReport,
  getRun,
  listRuns,
  streamRun
} from "./api";
import type { OptionsPayload, RunEvent, RunInfo, RunSpec, RunStatus } from "./types";

const today = dayjs().format("YYYY-MM-DD");
const assetOptions = [
  { label: "Stock", value: "stock" },
  { label: "Crypto", value: "crypto" }
];
const reportModes = ["Rendered", "Raw"];
const FORM_STORAGE_KEY = "tradingagents.web.runForm.v1";

const options = ref<OptionsPayload | null>(null);
const runs = ref<RunInfo[]>([]);
const selectedRun = ref<RunInfo | null>(null);
const events = ref<RunEvent[]>([]);
const eventIndex = ref(0);
const activeReport = ref("market_report");
const reportContent = ref("");
const reportMode = ref("Rendered");
const creating = ref(false);
const healthOk = ref(false);
const configDrawerOpen = ref(false);
const eventsDrawerOpen = ref(false);
let source: EventSource | null = null;
let formPersistenceReady = false;

const form = reactive<RunSpec>({
  ticker: "LI",
  analysis_date: today,
  analysts: ["market"],
  research_depth: 1,
  llm_provider: "openai",
  quick_think_llm: "gpt-5.4-mini",
  deep_think_llm: "gpt-5.4",
  output_language: "Chinese",
  asset_type: "stock",
  backend_url: "",
  checkpoint_enabled: false,
  google_thinking_level: null,
  openai_reasoning_effort: null,
  anthropic_effort: null
});

const reportSections = computed(() => options.value?.report_sections || ["market_report"]);
const reportHtml = computed(() => {
  if (!reportContent.value) {
    return "";
  }
  return DOMPurify.sanitize(marked.parse(reportContent.value) as string);
});

function persistForm() {
  if (!formPersistenceReady) {
    return;
  }
  localStorage.setItem(FORM_STORAGE_KEY, JSON.stringify({ ...form }));
}

function restoreForm() {
  const raw = localStorage.getItem(FORM_STORAGE_KEY);
  if (!raw) {
    return;
  }
  try {
    const saved = JSON.parse(raw) as Partial<RunSpec>;
    Object.assign(form, {
      ...saved,
      ticker: saved.ticker || form.ticker,
      analysis_date: saved.analysis_date || form.analysis_date,
      analysts:
        Array.isArray(saved.analysts) && saved.analysts.length
          ? saved.analysts
          : form.analysts,
      research_depth: Number(saved.research_depth || form.research_depth),
      backend_url: saved.backend_url || "",
    });
  } catch {
    localStorage.removeItem(FORM_STORAGE_KEY);
  }
}

watch(form, persistForm, { deep: true });

function isActive(status: RunStatus): boolean {
  return status === "pending" || status === "running";
}

function statusType(status: RunStatus): "" | "success" | "warning" | "danger" | "info" {
  if (status === "completed") return "success";
  if (status === "running") return "warning";
  if (status === "failed") return "danger";
  if (status === "canceled") return "info";
  return "";
}

function eventType(type: string): "" | "success" | "warning" | "danger" | "info" {
  if (type === "error") return "danger";
  if (type.includes("completed")) return "success";
  if (type.includes("report")) return "warning";
  if (type.includes("tool")) return "info";
  return "";
}

function sectionLabel(section: string): string {
  return section
    .replace(/_/g, " ")
    .replace(/\b\w/g, (value) => value.toUpperCase());
}

function formatTime(value?: string | null): string {
  if (!value) return "";
  return dayjs(value).format("MM-DD HH:mm:ss");
}

function runRowClass({ row }: { row: RunInfo }): string {
  return selectedRun.value?.id === row.id ? "selected-row" : "";
}

function appendEvents(nextEvents: RunEvent[]) {
  const seen = new Set(events.value.map((event) => event._index ?? `${event.type}-${event.timestamp}`));
  for (const event of nextEvents) {
    const key = event._index ?? `${event.type}-${event.timestamp}`;
    if (!seen.has(key)) {
      events.value.push(event);
    }
  }
  events.value = events.value.slice(-300);
}

function showLoadError(scope: string, error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  ElMessage.error(`${scope} load failed: ${message || "unknown error"}`);
}

function cachedReport(section: string): string {
  return selectedRun.value?.reports?.[section]?.content || "";
}

async function refreshRuns() {
  runs.value = await listRuns();
  if (!selectedRun.value && runs.value.length) {
    await selectRun(runs.value[0]);
  } else if (selectedRun.value) {
    const fresh = runs.value.find((run) => run.id === selectedRun.value?.id);
    if (fresh) {
      selectedRun.value = fresh;
    }
  }
}

async function refreshAll() {
  await refreshRuns();
  if (selectedRun.value) {
    await loadActiveReport();
  }
}

async function selectRun(run: RunInfo) {
  selectedRun.value = run;
  reportContent.value = "";
  events.value = [];
  eventIndex.value = 0;
  if (source) {
    source.close();
    source = null;
  }
  if (run.events?.length) {
    appendEvents(run.events);
    eventIndex.value = run.event_next ?? run.events.length;
  }
  try {
    await loadActiveReport();
  } catch (error) {
    showLoadError("Report", error);
  }
  try {
    const payload = await getEvents(run.id);
    appendEvents(payload.events);
    eventIndex.value = payload.next;
  } catch (error) {
    console.warn("Events load failed", error);
  }
  if (isActive(run.status)) {
    source = streamRun(run.id, eventIndex.value, async (event) => {
      appendEvents([event]);
      eventIndex.value = Math.max(eventIndex.value, (event._index ?? eventIndex.value) + 1);
      if (event.type === "report_updated" && event.section === activeReport.value) {
        await loadActiveReport();
      }
      if (["run_completed", "run_canceled", "error"].includes(event.type)) {
        await refreshRuns();
        source?.close();
        source = null;
      }
    });
  }
}

async function loadActiveReport() {
  if (!selectedRun.value) {
    reportContent.value = "";
    return;
  }
  const cached = cachedReport(activeReport.value);
  if (cached) {
    reportContent.value = cached;
  }
  try {
    reportContent.value = await getReport(selectedRun.value.id, activeReport.value);
  } catch (error) {
    if (!cached) {
      throw error;
    }
    console.warn("Report endpoint failed; using run payload content", error);
  }
}

async function startRun() {
  if (!form.ticker.trim()) {
    ElMessage.warning("Ticker is required");
    return;
  }
  if (!form.analysts.length) {
    ElMessage.warning("Select at least one analyst");
    return;
  }
  creating.value = true;
  persistForm();
  try {
    const run = await createRun({
      ...form,
      ticker: form.ticker.trim(),
      backend_url: form.backend_url || null
    });
    await refreshRuns();
    await selectRun(run);
    configDrawerOpen.value = false;
    ElMessage.success("Run started");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : String(error));
  } finally {
    creating.value = false;
  }
}

async function stopRun() {
  if (!selectedRun.value) return;
  await cancelRun(selectedRun.value.id);
  await refreshRuns();
  ElMessage.info("Run canceled");
}

onMounted(async () => {
  try {
    options.value = await fetchOptions();
    form.research_depth = options.value.defaults.research_depth;
    form.llm_provider = options.value.defaults.llm_provider;
    form.quick_think_llm = options.value.defaults.quick_think_llm;
    form.deep_think_llm = options.value.defaults.deep_think_llm;
    form.output_language = options.value.defaults.output_language;
    restoreForm();
    formPersistenceReady = true;
    healthOk.value = true;
    await refreshRuns();
  } catch (error) {
    healthOk.value = false;
    ElMessage.error(error instanceof Error ? error.message : String(error));
  }
});

onBeforeUnmount(() => {
  source?.close();
});
</script>
