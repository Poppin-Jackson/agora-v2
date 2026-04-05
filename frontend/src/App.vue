<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import api, {
  wsUrl,
  createPlan,
  copyPlan,
  getRoom,
  getPlan,
  listPlans,
  listTasks,
  createTask,
  updateTask,
  updateTaskProgress,
  getTaskMetrics,
  getRoomsByPlan,
  addParticipant,
  getPhase,
  transitionPhase,
  addSpeech,
  getApproval,
  startApproval,
  approvalAction,
  getApprovalLevels,
  getVersionPlanJson,
  listSnapshots,
  getSnapshot,
  listDecisions,
  createDecision,
  updateDecision,
  listEdicts,
  createEdict,
  updateEdict,
  deleteEdict,
  acknowledgeEdict,
  listEdictAcknowledgments,
  deleteEdictAcknowledgment,
  listRisks,
  createRisk,
  updateRisk,
  deleteRisk,
  listConstraints,
  createConstraint,
  updateConstraint,
  deleteConstraint,
  listStakeholders,
  createStakeholder,
  updateStakeholder,
  deleteStakeholder,
  listRequirements,
  createRequirement,
  updateRequirement,
  deleteRequirement,
  listActivities,
  getActivityStats,
  getActivity,
  listRoomActivities,
  listVersionActivities,
  getParticipantActivity,
  listPlanParticipants,
  searchRoomMessages,
  listNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  getUnreadNotificationCount,
  deleteNotification,
  getDebateState,
  getRoomPhaseTimeline,
  createDebatePoint,
  submitDebatePosition,
  submitDebateExchange,
  advanceDebateRound,
  Notification,
  getRoomHierarchy,
  linkRoom,
  concludeRoom,
  getTaskDependencyGraph,
  getBlockedTasks,
  validateTaskDependencies,
  escalateRoom,
  getEscalationPath,
  getPlanEscalations,
  getEscalation,
  updateEscalation,
  getProblems,
  getProblem,
  analyzeProblem,
  discussProblem,
  updatePlan,
  resumeExecution,
  listTaskComments,
  createTaskComment,
  listTaskCheckpoints,
  createTaskCheckpoint,
  createTimeEntry,
  listTimeEntries,
  getTimeSummary,
  deleteTimeEntry,
  exportPlanMarkdown,
  exportVersionMarkdown,
  listRoomTemplates,
  createRoomTemplate,
  updateRoomTemplate,
  deleteRoomTemplate,
  createRoomFromTemplate,
  listPlanTemplates,
  createPlanTemplate,
  updatePlanTemplate,
  deletePlanTemplate,
  createPlanFromTemplate,
  listTaskTemplates,
  createTaskTemplate,
  updateTaskTemplate,
  deleteTaskTemplate,
  createTaskFromTemplate,
  getDashboardStats,
  getRoomTags,
  updateRoomTags,
  addRoomTags,
  removeRoomTags,
  createActionItem,
  listRoomActionItems,
  listPlanActionItems,
  getActionItem,
  updateActionItem,
  completeActionItem,
  deleteActionItem,
  createMeetingMinutes,
  listRoomMeetingMinutes,
  listPlanMeetingMinutes,
  getMeetingMinutes,
  updateMeetingMinutes,
  deleteMeetingMinutes,
  generateMeetingMinutes,
} from './api'

// ─── View State ──────────────────────────────────────────
// home = plan list dashboard, plan_detail = plan detail, room = discussion
type View = 'home' | 'plan_detail' | 'room'
const view = ref<View>('home')

// ─── Home/Dashboard State ───────────────────────────────
const plans = ref<any[]>([])
const searchQuery = ref('')
const sortBy = ref<'recent' | 'name'>('recent')
const selectedPlanStatuses = ref<string[]>([])
const showCreatePlan = ref(false)
const newPlanForm = reactive({ title: '', topic: '' })
const dashboardStats = ref<any>(null)
const dashboardLoading = ref(false)

// ─── Plan Detail State ──────────────────────────────────
const currentPlan = ref<any>(null)
const planVersions = ref<any[]>([])
const showVersionCompare = ref(false)
const compareVersionA = ref('')
const compareVersionB = ref('')
const compareDataA = ref<any>(null)
const compareDataB = ref<any>(null)
const compareLoading = ref(false)
const planRooms = ref<any[]>([])
const planMetrics = ref<any>(null)
const planTasks = ref<any[]>([])
const activePlanTab = ref<'overview' | 'rooms' | 'tasks' | 'decisions' | 'edicts' | 'approvals' | 'versions' | 'risks' | 'constraints' | 'stakeholders' | 'requirements' | 'participants' | 'activities' | 'analytics' | 'snapshots' | 'escalations' | 'action_items' | 'meeting_minutes'>('overview')
const planDetailActiveVersion = ref<string>('')
const exportLoading = ref(false)

// ─── Room Templates State ───────────────────────────────
const roomTemplates = ref<any[]>([])
const showRoomTemplates = ref(false)
const showCreateTemplate = ref(false)
const newTemplateForm = reactive({
  name: '',
  description: '',
  purpose: 'initial_discussion',
  mode: 'hierarchical',
  default_phase: 'selecting',
  settings: {} as Record<string, any>,
  is_shared: false,
})
const editingTemplate = ref<any>(null)

// ─── Plan Templates State ────────────────────────────────
const planTemplates = ref<any[]>([])
const showPlanTemplates = ref(false)
const showCreatePlanTemplate = ref(false)
const newPlanTemplateForm = reactive({
  name: '',
  description: '',
  plan_content: {} as Record<string, any>,
  tags: [] as string[],
  is_shared: false,
  _tagsInput: '',
})
const editingPlanTemplate = ref<any>(null)

// ─── Step 73: Task Templates State ────────────────────────
const taskTemplates = ref<any[]>([])
const showTaskTemplates = ref(false)
const showCreateTaskTemplate = ref(false)
const newTaskTemplateForm = reactive({
  name: '',
  description: '',
  default_title: '',
  default_description: '',
  priority: 'medium',
  difficulty: 'medium',
  estimated_hours: null as number | null,
  owner_level: null as number | null,
  owner_role: '',
  tags: [] as string[],
  created_by: '',
  is_shared: false,
  _tagsInput: '',
})
const editingTaskTemplate = ref<any>(null)

// ─── Decisions State ─────────────────────────────────────
const planDecisions = ref<any[]>([])
const showAddDecision = ref(false)
const newDecisionForm = reactive({
  title: '',
  decision_text: '',
  description: '',
  rationale: '',
  alternatives_considered: '',
  agreed_by: '',
  disagreed_by: '',
  decided_by: '',
  room_id: '',
})
const editingDecisionId = ref<string | null>(null)

// ─── Edicts State ──────────────────────────────────────
const planEdicts = ref<any[]>([])
const showAddEdict = ref(false)
const newEdictForm = reactive({
  title: '',
  content: '',
  issued_by: '',
  effective_from: '',
  recipients: '',
  status: 'draft',
})
const editingEdictId = ref<string | null>(null)
const edictAcknowledgments = ref<Record<string, any[]>>({})
const showAckForm = ref(false)
const ackForm = reactive({ acknowledged_by: '', level: 5, comment: '' })
const ackEdictId = ref<string | null>(null)

// ─── Approvals State ─────────────────────────────────────
const approvalFlow = ref<any>(null)
const approvalLevels = ref<any[]>([])
const showStartApproval = ref(false)
const startApprovalForm = reactive({ initiator_id: 'user-1', initiator_name: '当前用户', skip_levels: [] as number[] })
const approvalActionComment = ref<Record<number, string>>({})
const loadingApproval = ref(false)
const skipLevelsInput = ref('')

// ─── Risks State ────────────────────────────────────────
const planRisks = ref<any[]>([])
const showAddRisk = ref(false)
const editingRiskId = ref<string | null>(null)
const newRiskForm = reactive({
  title: '',
  description: '',
  probability: 'medium' as string,
  impact: 'medium' as string,
  mitigation: '',
  contingency: '',
  status: 'identified',
})

// ─── Constraints State ────────────────────────────────────
const planConstraints = ref<any[]>([])
const showAddConstraint = ref(false)
const editingConstraintId = ref<string | null>(null)
const newConstraintForm = reactive({
  type: 'budget' as string,
  value: '',
  unit: '',
  description: '',
})

// ─── Stakeholders State ──────────────────────────────────
const planStakeholders = ref<any[]>([])
const showAddStakeholder = ref(false)
const editingStakeholderId = ref<string | null>(null)
const newStakeholderForm = reactive({
  name: '',
  level: 5 as number,
  interest: '',
  influence: '',
  description: '',
})

// ─── Requirements State ─────────────────────────────────
const planRequirements = ref<any[]>([])
const showAddRequirement = ref(false)
const editingRequirementId = ref<string | null>(null)
const newRequirementForm = reactive({
  description: '',
  priority: 'medium' as string,
  category: 'other' as string,
  status: 'pending' as string,
  notes: '',
})

// ─── Activities State ───────────────────────────────────
const planActivities = ref<any[]>([])
const activityStats = ref<any>(null)
const selectedActivity = ref<any>(null)
const activityFilterType = ref<string>('')
type ActivityScope = 'plan' | 'room' | 'version'
const activityScope = ref<ActivityScope>('plan')
const activityScopeRoomId = ref<string>('')
const activityScopeVersion = ref<string>('')

// ─── Participants State ──────────────────────────────────
const participantActivity = ref<any[]>([])
const planParticipants = ref<any[]>([])

// ─── Snapshots State ─────────────────────────────────────
const planSnapshots = ref<any[]>([])
const selectedSnapshot = ref<any>(null)

// ─── Escalations State ──────────────────────────────────
const planEscalations = ref<any[]>([])
const selectedEscalation = ref<any>(null)
const escalationActionLoading = ref(false)
const escalationActionForm = reactive({
  action: '',
  actor_id: '',
  actor_name: '',
  comment: ''
})
const showEscalationAction = ref(false)

// ─── Action Items State ─────────────────────────────────
const planActionItems = ref<any[]>([])
const roomActionItems = ref<any[]>([])
const actionItemFilter = ref<string>('')
const showAddActionItem = ref(false)
const editingActionItemId = ref<string | null>(null)
const actionItemLoading = ref(false)
const selectedActionItem = ref<any>(null)
const newActionItemForm = reactive({
  title: '',
  description: '',
  assignee: '',
  assignee_level: undefined as number | undefined,
  priority: 'medium',
  due_date: '',
  created_by: '',
})

// ─── Meeting Minutes State ──────────────────────────────
const planMeetingMinutes = ref<any[]>([])
const roomMeetingMinutes = ref<any[]>([])
const meetingMinutesLoading = ref(false)
const showAddMeetingMinutes = ref(false)
const selectedMeetingMinutes = ref<any>(null)
const showGenerateMeetingMinutes = ref(false)
const newMeetingMinutesForm = reactive({
  title: '',
  content: '',
  summary: '',
  decisions_summary: '',
  action_items_summary: '',
  participants_list: [] as string[],
  held_at: '',
  duration_minutes: undefined as number | undefined,
  created_by: '',
})
const generateMeetingMinutesForm = reactive({
  title: '',
  include_decisions: true,
  include_action_items: true,
  include_timeline: true,
  include_messages: false,
})

// ─── Room State ─────────────────────────────────────────
const currentRoom = ref<any>(null)
const currentPhase = ref<any>(null)
const messages = ref<any[]>([])
const participants = ref<any[]>([])
const newMessage = reactive({ agent_id: 'user-1', content: '' })
const agentInfo = reactive({ agent_id: 'user-1', name: '访客', level: 5, role: 'Member' })
const showAddParticipant = ref(false)
const newParticipant = reactive({ name: '', agent_id: '', role: 'Member', level: 5 })
// Message search
const messageSearchQuery = ref('')
const messageSearchResults = ref<any[]>([])
const messageSearchLoading = ref(false)
const messageSearchActive = ref(false)

// ─── Task State ─────────────────────────────────────────
const tasks = ref<any[]>([])
const taskMetrics = ref<any>(null)
const showAddTask = ref(false)
const showGanttView = ref(false)
const newTask = reactive<{ title: string; description: string; priority: 'low' | 'medium' | 'high' | 'critical'; assigned_to: string }>({ title: '', description: '', priority: 'medium', assigned_to: '' })
const activeTaskTab = ref<'list' | 'add'>('list')

// ─── Task Dependencies State ─────────────────────────────
const showTaskDependencies = ref(false)
const dependencyGraph = ref<any>(null)
const blockedTasks = ref<any[]>([])
const dependencyLoading = ref(false)

// ─── Task Detail Modal State ──────────────────────────────
const showTaskDetail = ref(false)
const selectedTaskForDetail = ref<any>(null)
const taskDetailComments = ref<any[]>([])
const taskDetailCheckpoints = ref<any[]>([])
const taskDetailActiveTab = ref<'comments' | 'checkpoints' | 'timetracking'>('comments')
const newCommentForm = reactive({ author_name: '', content: '' })
const newCheckpointForm = reactive({ name: '', status: 'pending' })
const taskDetailLoading = ref(false)
const taskTimeEntries = ref<any[]>([])
const taskTimeSummary = ref<any>(null)
const newTimeEntryForm = reactive({ user_name: '', hours: '', description: '' })
const taskTimeLoading = ref(false)

// ─── Debate State ───────────────────────────────────────
const debateState = ref<any>(null)
const showAddDebatePoint = ref(false)
const newDebatePoint = reactive({ content: '', point_type: 'proposal' })
const debatePositions = reactive<Record<string, 'support' | 'oppose'>>({})
const showAddExchange = ref(false)
const newExchange = reactive({
  exchange_type: 'challenge' as 'challenge' | 'response' | 'evidence' | 'update_position' | 'consensus_building',
  from_agent: '',
  target_agent: '',
  content: '',
})
const exchangeLoading = ref(false)
const roundAdvancing = ref(false)
// ─── Phase Timeline (Step 63) ───────────────────────────
const phaseTimeline = ref<any[]>([])

// ─── Room Activity Stream (Step 64) ────────────────────
const roomActivityStream = ref<any[]>([])
const showActivityStream = ref(false)

const wsStatus = ref<'connecting' | 'connected' | 'disconnected'>('disconnected')

// ─── Escalation State ─────────────────────────────────────
const showEscalationModal = ref(false)
const escalationForm = reactive({
  from_level: 5,
  to_level: 6,
  mode: 'level_by_level',
  reason: '',
  notes: '',
})
const escalationLoading = ref(false)
const escalationPathPreview = ref<any>(null)
const escalationPathLoading = ref(false)

// ─── Problem Management State ──────────────────────────────────────
const problemStates = ['PROBLEM_DETECTED', 'PROBLEM_ANALYSIS', 'PROBLEM_DISCUSSION', 'PLAN_UPDATE', 'RESUMING']
const currentProblem = ref<any>(null)
const problemAnalysis = ref<any>(null)
const problemDiscussion = ref<any>(null)
const showReportProblem = ref(false)
const reportProblemForm = reactive({
  type: 'execution_blocker',
  title: '',
  description: '',
  severity: 'medium',
  affected_tasks: [] as string[],
  progress_delay: '',
  related_context: '',
})
const reportProblemLoading = ref(false)
const analyzeForm = reactive({
  root_cause: '',
  root_cause_confidence: 0.8,
  impact_scope: '',
  affected_tasks: [] as string[],
  progress_impact: '',
  severity_reassessment: '',
  solution_options: [] as Array<{ description: string; pros: string[]; cons: string[] }>,
  recommended_option: 0,
  requires_discussion: false,
  discussion_needed_aspects: [] as string[],
})
const discussForm = reactive({
  participants: [] as Array<{ id: string; name: string; level: number }>,
  discussion_focus: [] as Array<{ aspect: string; notes: string }>,
  proposed_solutions: [] as Array<{ solution: string; proposed_by: string }>,
  votes: {} as Record<string, string>,
})
const planUpdateForm = reactive({
  new_version: '',
  parent_version: '',
  update_type: 'problem_recovery',
  description: '',
  changes: {} as Record<string, unknown>,
  task_updates: [] as Array<{ task_id: string; status: string }>,
})
const resumingForm = reactive({
  new_version: '',
  resuming_from_task: 0,
  checkpoint: '',
  resume_instructions: {} as Record<string, unknown>,
})
const problemActionLoading = ref(false)
const isProblemPhase = computed(() => {
  const phase = currentPhase.value?.current_phase
  return phase && problemStates.includes(phase)
})

const isHierarchicalReviewPhase = computed(() => {
  return currentPhase.value?.current_phase === 'HIERARCHICAL_REVIEW'
})
const isConvergingPhase = computed(() => {
  return currentPhase.value?.current_phase === 'CONVERGING'
})
const hierarchicalReviewData = ref<any>(null)
const reviewNotes = ref<Record<string, string>>({})

// ─── Create Room State ──────────────────────────────────
const showCreateRoom = ref(false)
const newRoomForm = reactive({ topic: '', title: '', mode: 'hierarchical' as string })

// ─── Room Hierarchy State ────────────────────────────────
const showRoomHierarchy = ref(false)
const selectedRoomForHierarchy = ref<any>(null)
const roomHierarchyData = ref<any>(null)
const hierarchyLoading = ref(false)
const hierarchyLinkForm = reactive({
  parent_room_id: '',
  child_rooms: [] as string[],
  related_rooms: [] as string[],
})
const hierarchyConcludeForm = reactive({
  summary: '',
  conclusion: '',
})
const hierarchyActiveTab = ref<'view' | 'link' | 'conclude'>('view')
const hierarchyActionLoading = ref(false)

// ─── Notifications State ─────────────────────────────────
const notifications = ref<Notification[]>([])
const unreadCount = ref(0)

// ─── Room Tags State ──────────────────────────────────────
const showRoomTagsModal = ref(false)
const roomTagsForm = reactive({
  newTag: '',
})
const roomTagsLoading = ref(false)
const showNotifications = ref(false)
const currentUser = reactive({ user_id: 'user-1', name: '访客', level: 5 })

const notificationTypeLabel: Record<string, string> = {
  task_assigned: '📋 任务分配',
  task_completed: '✅ 任务完成',
  task_blocked: '🚫 任务阻塞',
  problem_reported: '⚠️ 问题报告',
  problem_resolved: '✔️ 问题解决',
  approval_requested: '📨 审批请求',
  approval_completed: '📗 审批完成',
  edict_published: '📜 圣旨颁布',
  escalation_received: '🔺 升级通知',
}

const notificationTypeColor: Record<string, string> = {
  task_assigned: '#3b82f6',
  task_completed: '#22c55e',
  task_blocked: '#ef4444',
  problem_reported: '#f59e0b',
  problem_resolved: '#10b981',
  approval_requested: '#8b5cf6',
  approval_completed: '#14b8a6',
  edict_published: '#f59e0b',
  escalation_received: '#dc2626',
}

async function loadNotifications() {
  try {
    const res = await listNotifications({ recipient_id: currentUser.user_id, limit: 50 })
    notifications.value = res.data?.notifications || []
  } catch (e) {
    console.error('loadNotifications failed', e)
  }
}

async function loadUnreadCount() {
  try {
    const res = await getUnreadNotificationCount(currentUser.user_id)
    unreadCount.value = res.data?.count || 0
  } catch (e) {
    console.error('loadUnreadCount failed', e)
  }
}

async function handleMarkRead(notificationId: string) {
  try {
    await markNotificationRead(notificationId)
    const n = notifications.value.find(n => n.notification_id === notificationId)
    if (n) n.read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch (e) {
    console.error('markNotificationRead failed', e)
  }
}

async function handleMarkAllRead() {
  try {
    await markAllNotificationsRead(currentUser.user_id)
    notifications.value.forEach(n => { n.read = true })
    unreadCount.value = 0
  } catch (e) {
    console.error('markAllNotificationsRead failed', e)
  }
}

async function handleDeleteNotification(notificationId: string) {
  try {
    await deleteNotification(notificationId)
    const idx = notifications.value.findIndex(n => n.notification_id === notificationId)
    if (idx !== -1) {
      if (!notifications.value[idx].read) unreadCount.value = Math.max(0, unreadCount.value - 1)
      notifications.value.splice(idx, 1)
    }
  } catch (e) {
    console.error('deleteNotification failed', e)
  }
}

function toggleNotifications() {
  showNotifications.value = !showNotifications.value
  if (showNotifications.value && notifications.value.length === 0) {
    loadNotifications()
  }
}

function closeNotifications(e: MouseEvent) {
  const panel = document.querySelector('.notification-panel')
  const bell = document.querySelector('.notification-bell')
  if (panel && bell && !panel.contains(e.target as Node) && !bell.contains(e.target as Node)) {
    showNotifications.value = false
  }
}

// ─── WebSocket ──────────────────────────────────────────
let ws: WebSocket | null = null
let phasePollInterval: ReturnType<typeof setInterval> | null = null
let homePollInterval: ReturnType<typeof setInterval> | null = null
// WebSocket auto-reconnect state
let wsCurrentRoom: string | null = null
let wsReconnectAttempt = 0
const WS_MAX_RECONNECT = 5
const WS_BASE_DELAY = 1000   // 1 second
const WS_MAX_DELAY = 30000  // 30 seconds
const wsReconnectTimers: ReturnType<typeof setTimeout>[] = []

// ─── Computed ──────────────────────────────────────────
const phaseColors: Record<string, string> = {
  initiated: '#6b7280',
  selecting: '#3b82f6',
  thinking: '#8b5cf6',
  sharing: '#f59e0b',
  debate: '#ef4444',
  converging: '#10b981',
  hierarchical_review: '#6366f1',
  decision: '#14b8a6',
  executing: '#0ea5e9',
  completed: '#22c55e',
  problem_detected: '#dc2626',
  problem_analysis: '#f59e0b',
  problem_discussion: '#a78bfa',
  plan_update: '#3b82f6',
  resuming: '#10b981',
}

const phaseLabel: Record<string, string> = {
  initiated: '初始化',
  selecting: '选择中',
  thinking: '思考中',
  sharing: '分享中',
  debate: '辩论中',
  converging: '收敛中',
  hierarchical_review: '层级评审',
  decision: '决策中',
  executing: '执行中',
  completed: '已完成',
  problem_detected: '问题',
  problem_analysis: '问题分析',
  problem_discussion: '问题讨论',
  plan_update: '计划更新',
  resuming: '恢复执行',
}

const statusLabel: Record<string, string> = {
  pending: '⏳ 待处理',
  in_progress: '🔄 进行中',
  completed: '✅ 完成',
  blocked: '🚫 阻塞',
  cancelled: '❌ 已取消',
}

const priorityLabel: Record<string, string> = {
  low: '低',
  medium: '中',
  high: '高',
  critical: '紧急',
}

const filteredPlans = computed(() => {
  let result = plans.value
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter(p =>
      (p.title || '').toLowerCase().includes(q) ||
      (p.topic || '').toLowerCase().includes(q) ||
      (p.plan_number || '').toLowerCase().includes(q)
    )
  }
  if (sortBy.value === 'recent') {
    result = [...result].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
  }
  return result
})

const filteredActivities = computed(() => {
  if (!activityFilterType.value) return planActivities.value
  return planActivities.value.filter(a =>
    (a.action_type || '').includes(activityFilterType.value)
  )
})

// ─── Gantt Chart Computed ─────────────────────────────
const ganttTodayStr = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`
})

const ganttDateRange = computed(() => {
  const tasks = planTasks.value
  if (!tasks || tasks.length === 0) return []
  const today = new Date()
  today.setHours(0,0,0,0)
  let earliest: Date | null = null
  let latest: Date | null = null
  for (const t of tasks) {
    if (t.started_at) {
      const s = new Date(t.started_at)
      s.setHours(0,0,0,0)
      if (!earliest || s < earliest) earliest = s
      if (!latest || s > latest) latest = s
    }
    if (t.deadline) {
      const dl = new Date(t.deadline)
      dl.setHours(0,0,0,0)
      if (!earliest || dl < earliest) earliest = dl
      if (!latest || dl > latest) latest = dl
    }
  }
  if (!earliest) earliest = today
  if (!latest) latest = new Date(today.getTime() + 30*86400000)
  // Ensure at least 7 days visible
  const span = latest.getTime() - earliest.getTime()
  if (span < 7*86400000) {
    latest = new Date(earliest.getTime() + 7*86400000)
  }
  const days: string[] = []
  const cur = new Date(earliest)
  while (cur <= latest) {
    days.push(`${cur.getFullYear()}-${String(cur.getMonth()+1).padStart(2,'0')}-${String(cur.getDate()).padStart(2,'0')}`)
    cur.setDate(cur.getDate() + 1)
  }
  return days
})

const ganttTodayOffset = computed(() => {
  const days = ganttDateRange.value
  if (!days.length) return -1
  const today = ganttTodayStr.value
  const idx = days.indexOf(today)
  return idx >= 0 ? (idx / (days.length - 1)) * 100 : -1
})

const ganttTasks = computed(() => {
  const tasks = planTasks.value
  const days = ganttDateRange.value
  if (!tasks || !days.length) return []
  const earliest = new Date(days[0])
  const totalMs = new Date(days[days.length-1]).getTime() - earliest.getTime()
  const taskIdxMap: Record<string, number> = {}
  tasks.forEach((t, i) => { taskIdxMap[t.task_id] = i })

  return tasks.map(task => {
    let startDate: Date | null = null
    let endDate: Date | null = null
    if (task.started_at) {
      startDate = new Date(task.started_at)
      startDate.setHours(0,0,0,0)
    }
    if (task.deadline) {
      endDate = new Date(task.deadline)
      endDate.setHours(0,0,0,0)
    }
    // If no start but has end and estimated_hours, back-calculate start
    if (!startDate && endDate && task.estimated_hours) {
      // assume 8h/day
      const daysBack = Math.ceil(task.estimated_hours / 8)
      startDate = new Date(endDate.getTime() - daysBack * 86400000)
    }
    // Default: if no dates, use today for start, +7 days for end
    if (!startDate) {
      startDate = new Date()
      startDate.setHours(0,0,0,0)
    }
    if (!endDate) {
      endDate = new Date(startDate.getTime() + (task.estimated_hours ? (task.estimated_hours/8) * 86400000 : 7*86400000))
    }

    const startMs = Math.max(startDate.getTime(), earliest.getTime())
    const endMs = endDate.getTime()
    const left = totalMs > 0 ? ((startMs - earliest.getTime()) / totalMs) * 100 : 0
    const width = totalMs > 0 ? Math.max(((endMs - startMs) / totalMs) * 100, 2) : 2

    // Dependency arrows
    const depArrows: {x1: number, x2: number, targetIdx: number, depId: string}[] = []
    const deps = task.dependencies || []
    const depList = Array.isArray(deps) ? deps : (deps ? [deps] : [])
    for (const depId of depList) {
      const depIdx = taskIdxMap[depId as string]
      if (depIdx !== undefined) {
        const depTask = tasks[depIdx]
        let depEndDate: Date | null = null
        if (depTask.deadline) {
          depEndDate = new Date(depTask.deadline)
          depEndDate.setHours(0,0,0,0)
        } else if (depTask.started_at) {
          const ds = new Date(depTask.started_at)
          ds.setHours(0,0,0,0)
          depEndDate = new Date(ds.getTime() + (depTask.estimated_hours ? (depTask.estimated_hours/8)*86400000 : 7*86400000))
        }
        if (depEndDate) {
          const depEndMs = Math.min(depEndDate.getTime(), earliest.getTime() + totalMs)
          const x1 = totalMs > 0 ? ((depEndMs - earliest.getTime()) / totalMs) * 100 : 0
          const x2 = left
          depArrows.push({ x1, x2, targetIdx: depIdx, depId: depId as string })
        }
      }
    }

    return { ...task, barLeft: left, barWidth: width, depArrows }
  })
})

const tasksWithId = computed(() => {
  const m: Record<string, any> = {}
  for (const t of planTasks.value) {
    m[t.task_id] = t
  }
  return m
})

const ganttAllArrows = computed(() => {
  const arrows: {x1: number, y1: number, x2: number, y2: number}[] = []
  const ROW_H = 48
  const LABEL_W = 200 // px, approximate label column width in the SVG coordinate system (not used for x calcs)
  for (let i = 0; i < ganttTasks.value.length; i++) {
    const task = ganttTasks.value[i]
    for (const arrow of task.depArrows) {
      const targetIdx = arrow.targetIdx
      // x positions as percentages of timeline width
      const x1 = arrow.x1
      const x2 = arrow.x2
      // y positions: source task row (end of bar) to target task row (start of bar)
      // We add ROW_H/2 to center on the row
      const y1 = targetIdx * ROW_H + ROW_H / 2
      const y2 = i * ROW_H + ROW_H / 2
      arrows.push({ x1, y1, x2, y2 })
    }
  }
  return arrows
})

// ─── Home/Dashboard Actions ─────────────────────────────
async function loadPlans() {
  try {
    const res = await listPlans()
    plans.value = res.data || []
  } catch (e) {
    console.error('loadPlans failed', e)
  }
}

async function loadDashboardStats() {
  dashboardLoading.value = true
  try {
    const res = await getDashboardStats()
    dashboardStats.value = res.data
  } catch (e) {
    console.error('loadDashboardStats failed', e)
  } finally {
    dashboardLoading.value = false
  }
}

async function handleCreatePlan() {
  if (!newPlanForm.topic.trim()) return
  try {
    const res = await createPlan({
      title: newPlanForm.title || newPlanForm.topic,
      topic: newPlanForm.topic,
      requirements: [],
    })
    const plan = res.data
    newPlanForm.topic = ''
    newPlanForm.title = ''
    showCreatePlan.value = false
    // Navigate to the new plan's detail
    await openPlanDetail(plan.plan_id)
  } catch (e) {
    console.error('createPlan failed', e)
  }
}

async function handleCopyPlan(planId: string) {
  try {
    const res = await copyPlan(planId, { performed_by: currentUser.name || 'anonymous' })
    const newPlan = res.data?.plan
    if (newPlan) {
      // Refresh plans list and navigate to the new copy
      await loadPlans()
      await openPlanDetail(newPlan.plan_id)
    }
  } catch (e) {
    console.error('handleCopyPlan failed', e)
  }
}

async function openPlanDetail(planId: string) {
  try {
    const [planRes, versionsRes, roomsRes, metricsRes] = await Promise.all([
      getPlan(planId),
      api.get(`/plans/${planId}/versions`),
      getRoomsByPlan(planId),
      api.get(`/plans/${planId}/analytics`),
    ])
    currentPlan.value = planRes.data
    planVersions.value = versionsRes.data?.versions || []
    planRooms.value = roomsRes.data?.rooms || []
    planMetrics.value = metricsRes.data
    planDetailActiveVersion.value = planRes.data.current_version || planRes.data.version || 'v1.0'

    // Load tasks, decisions, edicts, risks, constraints, stakeholders, requirements for current version
    try {
      const version = planDetailActiveVersion.value
      const [tasksRes, metricsR, decisionsRes, edictsRes, risksRes, constraintsRes, stakeholdersRes, requirementsRes, activitiesRes, statsRes] = await Promise.all([
        listTasks(planId, version),
        getTaskMetrics(planId, version),
        listDecisions(planId, version),
        listEdicts(planId, version),
        listRisks(planId, version),
        listConstraints(planId),
        listStakeholders(planId),
        listRequirements(planId),
        listActivities(planId),
        getActivityStats(planId),
      ])
      planTasks.value = tasksRes.data?.tasks || []
      planMetrics.value = metricsR.data
      planDecisions.value = decisionsRes.data?.decisions || []
      planEdicts.value = edictsRes.data?.edicts || []
      planRisks.value = risksRes.data?.risks || []
      planConstraints.value = constraintsRes.data?.constraints || []
      planStakeholders.value = stakeholdersRes.data?.stakeholders || []
      planRequirements.value = requirementsRes.data || []
      planActivities.value = activitiesRes.data?.activities || []
      activityStats.value = statsRes.data
    } catch {}

    view.value = 'plan_detail'
  } catch (e) {
    console.error('openPlanDetail failed', e)
  }
}

async function switchPlanVersion(version: string) {
  planDetailActiveVersion.value = version
  try {
    const [tasksRes, metricsRes, decisionsRes, edictsRes, risksRes, constraintsRes, stakeholdersRes, requirementsRes] = await Promise.all([
      listTasks(currentPlan.value.plan_id, version),
      getTaskMetrics(currentPlan.value.plan_id, version),
      listDecisions(currentPlan.value.plan_id, version),
      listEdicts(currentPlan.value.plan_id, version),
      listRisks(currentPlan.value.plan_id, version),
      listConstraints(currentPlan.value.plan_id),
      listStakeholders(currentPlan.value.plan_id),
      listRequirements(currentPlan.value.plan_id),
    ])
    planTasks.value = tasksRes.data?.tasks || []
    planMetrics.value = metricsRes.data
    planDecisions.value = decisionsRes.data?.decisions || []
    planEdicts.value = edictsRes.data?.edicts || []
    planRisks.value = risksRes.data?.risks || []
    planConstraints.value = constraintsRes.data?.constraints || []
    planStakeholders.value = stakeholdersRes.data?.stakeholders || []
    planRequirements.value = requirementsRes.data || []
    // If activities tab scope is version, update version and reload
    if (activityScope.value === 'version') {
      activityScopeVersion.value = version
      const [activitiesRes] = await Promise.all([
        listVersionActivities(currentPlan.value.plan_id, version),
      ])
      planActivities.value = activitiesRes.data?.activities || []
      activityStats.value = null
    } else {
      // Activities are plan-level, reload on version switch
      const [activitiesRes, statsRes] = await Promise.all([
        listActivities(currentPlan.value.plan_id),
        getActivityStats(currentPlan.value.plan_id),
      ])
      planActivities.value = activitiesRes.data?.activities || []
      activityStats.value = statsRes.data
    }
    // Snapshots are version-level, reload on version switch
    await loadPlanSnapshots()
  } catch (e) {
    console.error('switchPlanVersion failed', e)
  }
}

async function loadVersionCompare() {
  if (!currentPlan.value || !compareVersionA.value || !compareVersionB.value) return
  compareLoading.value = true
  try {
    const [resA, resB] = await Promise.all([
      getVersionPlanJson(currentPlan.value.plan_id, compareVersionA.value),
      getVersionPlanJson(currentPlan.value.plan_id, compareVersionB.value),
    ])
    compareDataA.value = resA.data
    compareDataB.value = resB.data
  } catch (e) {
    console.error('loadVersionCompare failed', e)
  } finally {
    compareLoading.value = false
  }
}

function openVersionCompare() {
  if (planVersions.value.length < 2) return
  showVersionCompare.value = true
  compareVersionA.value = planVersions.value[planVersions.value.length - 2] || ''
  compareVersionB.value = planVersions.value[planVersions.value.length - 1] || ''
  compareDataA.value = null
  compareDataB.value = null
}

function closeVersionCompare() {
  showVersionCompare.value = false
  compareDataA.value = null
  compareDataB.value = null
}

// ─── Phase Timeline Helpers (Step 63) ───────────────────────
function formatTime(isoString: string | null | undefined): string {
  if (!isoString) return '-'
  try {
    const d = new Date(isoString)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return '-'
  }
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '-'
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m < 60) return s > 0 ? `${m}m ${s}s` : `${m}m`
  const h = Math.floor(m / 60)
  const rem = m % 60
  return rem > 0 ? `${h}h ${rem}m` : `${h}h`
}

async function loadPlanDecisions() {
  if (!currentPlan.value) return
  try {
    const res = await listDecisions(currentPlan.value.plan_id, planDetailActiveVersion.value)
    planDecisions.value = res.data?.decisions || []
  } catch (e) {
    console.error('loadPlanDecisions failed', e)
  }
}

async function loadPlanActivities() {
  if (!currentPlan.value) return
  try {
    let actsRes: any
    if (activityScope.value === 'room' && activityScopeRoomId.value) {
      actsRes = await listRoomActivities(activityScopeRoomId.value)
    } else if (activityScope.value === 'version' && activityScopeVersion.value) {
      actsRes = await listVersionActivities(currentPlan.value.plan_id, activityScopeVersion.value)
    } else {
      actsRes = await listActivities(currentPlan.value.plan_id)
    }
    // Stats only available for plan scope
    if (activityScope.value === 'plan') {
      const statsRes = await getActivityStats(currentPlan.value.plan_id)
      activityStats.value = statsRes.data
    } else {
      activityStats.value = null
    }
    planActivities.value = actsRes.data?.activities || []
  } catch (e) {
    console.error('loadPlanActivities failed', e)
  }
}

async function loadPlanSnapshots() {
  if (!currentPlan.value || !planDetailActiveVersion.value) return
  try {
    const res = await listSnapshots(currentPlan.value.plan_id, planDetailActiveVersion.value)
    planSnapshots.value = res.data?.snapshots || []
  } catch (e) {
    console.error('loadPlanSnapshots failed', e)
  }
}

async function loadPlanEscalations() {
  if (!currentPlan.value) return
  try {
    const res = await getPlanEscalations(currentPlan.value.plan_id)
    planEscalations.value = res.data?.escalations || []
  } catch (e) {
    console.error('loadPlanEscalations failed', e)
  }
}

async function loadPlanActionItems(status?: string) {
  if (!currentPlan.value) return
  actionItemLoading.value = true
  try {
    const res = await listPlanActionItems(currentPlan.value.plan_id, status || undefined)
    planActionItems.value = res.data?.items || res.data || []
  } catch (e) {
    console.error('loadPlanActionItems failed', e)
  } finally {
    actionItemLoading.value = false
  }
}

async function loadRoomActionItems(roomId: string, status?: string) {
  try {
    const res = await listRoomActionItems(roomId, status || undefined)
    roomActionItems.value = res.data?.items || res.data || []
  } catch (e) {
    console.error('loadRoomActionItems failed', e)
  }
}

async function handleCreateActionItem(roomId: string) {
  if (!newActionItemForm.title) return
  actionItemLoading.value = true
  try {
    await createActionItem(roomId, {
      title: newActionItemForm.title,
      description: newActionItemForm.description,
      assignee: newActionItemForm.assignee || undefined,
      assignee_level: newActionItemForm.assignee_level || undefined,
      priority: newActionItemForm.priority,
      due_date: newActionItemForm.due_date || undefined,
      created_by: newActionItemForm.created_by || currentUser.name,
    })
    newActionItemForm.title = ''
    newActionItemForm.description = ''
    newActionItemForm.assignee = ''
    newActionItemForm.assignee_level = undefined
    newActionItemForm.priority = 'medium'
    newActionItemForm.due_date = ''
    showAddActionItem.value = false
    await loadRoomActionItems(roomId)
  } catch (e) {
    console.error('handleCreateActionItem failed', e)
  } finally {
    actionItemLoading.value = false
  }
}

async function handleUpdateActionItem(itemId: string, roomId: string) {
  actionItemLoading.value = true
  try {
    await updateActionItem(itemId, {
      title: editingActionItemId.value ? newActionItemForm.title : undefined,
      description: editingActionItemId.value ? newActionItemForm.description : undefined,
      assignee: editingActionItemId.value ? newActionItemForm.assignee : undefined,
      assignee_level: editingActionItemId.value ? newActionItemForm.assignee_level : undefined,
      priority: editingActionItemId.value ? newActionItemForm.priority : undefined,
      due_date: editingActionItemId.value ? newActionItemForm.due_date : undefined,
    })
    editingActionItemId.value = null
    showAddActionItem.value = false
    await loadRoomActionItems(roomId)
    if (currentPlan.value) await loadPlanActionItems()
  } catch (e) {
    console.error('handleUpdateActionItem failed', e)
  } finally {
    actionItemLoading.value = false
  }
}

async function handleCompleteActionItem(itemId: string, roomId: string) {
  actionItemLoading.value = true
  try {
    await completeActionItem(itemId)
    await loadRoomActionItems(roomId)
    if (currentPlan.value) await loadPlanActionItems()
  } catch (e) {
    console.error('handleCompleteActionItem failed', e)
  } finally {
    actionItemLoading.value = false
  }
}

async function handleDeleteActionItem(itemId: string, roomId: string) {
  actionItemLoading.value = true
  try {
    await deleteActionItem(itemId)
    await loadRoomActionItems(roomId)
    if (currentPlan.value) await loadPlanActionItems()
  } catch (e) {
    console.error('handleDeleteActionItem failed', e)
  } finally {
    actionItemLoading.value = false
  }
}

function startEditActionItem(item: any) {
  editingActionItemId.value = item.action_item_id
  newActionItemForm.title = item.title
  newActionItemForm.description = item.description || ''
  newActionItemForm.assignee = item.assignee || ''
  newActionItemForm.assignee_level = item.assignee_level || undefined
  newActionItemForm.priority = item.priority || 'medium'
  newActionItemForm.due_date = item.due_date ? item.due_date.split('T')[0] : ''
  showAddActionItem.value = true
}

function resetActionItemForm() {
  editingActionItemId.value = null
  newActionItemForm.title = ''
  newActionItemForm.description = ''
  newActionItemForm.assignee = ''
  newActionItemForm.assignee_level = undefined
  newActionItemForm.priority = 'medium'
  newActionItemForm.due_date = ''
  showAddActionItem.value = false
}

// ─── Meeting Minutes Functions ─────────────────────────────────────
async function loadPlanMeetingMinutes() {
  if (!currentPlan.value) return
  meetingMinutesLoading.value = true
  try {
    const res = await listPlanMeetingMinutes(currentPlan.value.plan_id)
    planMeetingMinutes.value = res.data || []
  } catch (e) {
    console.error('loadPlanMeetingMinutes failed', e)
  } finally {
    meetingMinutesLoading.value = false
  }
}

async function loadRoomMeetingMinutes(roomId: string) {
  try {
    const res = await listRoomMeetingMinutes(roomId)
    roomMeetingMinutes.value = res.data || []
  } catch (e) {
    console.error('loadRoomMeetingMinutes failed', e)
  }
}

async function handleGenerateMeetingMinutes(roomId: string) {
  meetingMinutesLoading.value = true
  try {
    await generateMeetingMinutes(roomId, {
      title: generateMeetingMinutesForm.title || undefined,
      include_decisions: generateMeetingMinutesForm.include_decisions,
      include_action_items: generateMeetingMinutesForm.include_action_items,
      include_timeline: generateMeetingMinutesForm.include_timeline,
      include_messages: generateMeetingMinutesForm.include_messages,
    })
    generateMeetingMinutesForm.title = ''
    generateMeetingMinutesForm.include_decisions = true
    generateMeetingMinutesForm.include_action_items = true
    generateMeetingMinutesForm.include_timeline = true
    generateMeetingMinutesForm.include_messages = false
    showGenerateMeetingMinutes.value = false
    await loadRoomMeetingMinutes(roomId)
    if (currentPlan.value) await loadPlanMeetingMinutes()
  } catch (e) {
    console.error('handleGenerateMeetingMinutes failed', e)
  } finally {
    meetingMinutesLoading.value = false
  }
}

async function handleDeleteMeetingMinutes(minutesId: string) {
  meetingMinutesLoading.value = true
  try {
    await deleteMeetingMinutes(minutesId)
    if (currentPlan.value) await loadPlanMeetingMinutes()
  } catch (e) {
    console.error('handleDeleteMeetingMinutes failed', e)
  } finally {
    meetingMinutesLoading.value = false
  }
}

async function openMeetingMinutesDetail(minutes: any) {
  selectedMeetingMinutes.value = minutes
}

function resetMeetingMinutesForm() {
  newMeetingMinutesForm.title = ''
  newMeetingMinutesForm.content = ''
  newMeetingMinutesForm.summary = ''
  newMeetingMinutesForm.decisions_summary = ''
  newMeetingMinutesForm.action_items_summary = ''
  newMeetingMinutesForm.participants_list = []
  newMeetingMinutesForm.held_at = ''
  newMeetingMinutesForm.duration_minutes = undefined
  showAddMeetingMinutes.value = false
  selectedMeetingMinutes.value = null
}

async function openEscalationAction(esc: any) {
  selectedEscalation.value = esc
  escalationActionForm.action = ''
  escalationActionForm.actor_name = currentUser.name
  escalationActionForm.comment = ''
  showEscalationAction.value = true
}

async function handleEscalationAction() {
  if (!selectedEscalation.value || !escalationActionForm.action) return
  escalationActionLoading.value = true
  try {
    await updateEscalation(selectedEscalation.value.escalation_id, {
      action: escalationActionForm.action,
      actor_id: currentUser.user_id,
      actor_name: escalationActionForm.actor_name,
      comment: escalationActionForm.comment
    })
    showEscalationAction.value = false
    await loadPlanEscalations()
  } catch (e) {
    console.error('handleEscalationAction failed', e)
  } finally {
    escalationActionLoading.value = false
  }
}

async function viewSnapshot(snap: any) {
  if (!currentPlan.value || !planDetailActiveVersion.value) return
  try {
    const res = await getSnapshot(currentPlan.value.plan_id, planDetailActiveVersion.value, snap.snapshot_id)
    selectedSnapshot.value = res.data?.snapshot || res.data || snap
  } catch (e) {
    // fallback to basic data if full fetch fails
    selectedSnapshot.value = snap
    console.error('viewSnapshot failed', e)
  }
}

async function loadAnalyticsData() {
  if (!currentPlan.value) return
  try {
    const res = await api.get(`/plans/${currentPlan.value.plan_id}/analytics`)
    planMetrics.value = res.data
  } catch (e) {
    console.error('loadAnalyticsData failed', e)
  }
}

async function loadTasks() {
  if (!currentPlan.value) return
  const version = planDetailActiveVersion.value || 'v1.0'
  try {
    const [tasksRes, metricsRes] = await Promise.all([
      listTasks(currentPlan.value.plan_id, version),
      getTaskMetrics(currentPlan.value.plan_id, version),
    ])
    planTasks.value = tasksRes.data?.tasks || []
    planMetrics.value = metricsRes.data
  } catch (e) {
    console.error('loadTasks failed', e)
  }
}

async function loadParticipantActivity() {
  if (!currentPlan.value) return
  try {
    const [actRes, partRes] = await Promise.all([
      getParticipantActivity(currentPlan.value.plan_id),
      listPlanParticipants(currentPlan.value.plan_id),
    ])
    participantActivity.value = actRes.data || []
    planParticipants.value = partRes.data || []
  } catch (e) {
    console.error('loadParticipantActivity failed', e)
  }
}

// Watch tab switch to load snapshots when entering the tab
watch(activePlanTab, (newTab) => {
  if (newTab === 'snapshots') {
    loadPlanSnapshots()
  }
  if (newTab === 'approvals') {
    loadApprovalFlow()
  }
  if (newTab === 'analytics') {
    loadAnalyticsData()
  }
  if (newTab === 'escalations') {
    loadPlanEscalations()
  }
  if (newTab === 'participants') {
    loadParticipantActivity()
  }
  if (newTab === 'activities') {
    // Reset scope to plan and initialize version from current
    activityScope.value = 'plan'
    activityScopeVersion.value = planDetailActiveVersion.value || ''
    activityScopeRoomId.value = ''
    loadPlanActivities()
  }
  if (newTab === 'action_items') {
    loadPlanActionItems()
  }
  if (newTab === 'meeting_minutes') {
    loadPlanMeetingMinutes()
  }
})

// Watch escalation form to load path preview
watch([() => escalationForm.from_level, () => escalationForm.to_level, () => escalationForm.mode], async () => {
  if (!showEscalationModal.value || !currentRoom.value) return
  if (escalationForm.to_level <= escalationForm.from_level) {
    escalationPathPreview.value = null
    return
  }
  escalationPathLoading.value = true
  try {
    const res = await getEscalationPath(currentRoom.value.room_id, escalationForm.from_level, escalationForm.mode)
    escalationPathPreview.value = res.data
  } catch {
    escalationPathPreview.value = null
  } finally {
    escalationPathLoading.value = false
  }
})

async function handleCreateDecision() {
  if (!newDecisionForm.title.trim() || !currentPlan.value) return
  const planId = currentPlan.value.plan_id
  const version = planDetailActiveVersion.value
  try {
    const data: any = {
      title: newDecisionForm.title,
      decision_text: newDecisionForm.decision_text,
    }
    if (newDecisionForm.description) data.description = newDecisionForm.description
    if (newDecisionForm.rationale) data.rationale = newDecisionForm.rationale
    if (newDecisionForm.alternatives_considered) data.alternatives_considered = newDecisionForm.alternatives_considered.split('\n').filter(Boolean)
    if (newDecisionForm.agreed_by) data.agreed_by = newDecisionForm.agreed_by.split(',').map(s => s.trim()).filter(Boolean)
    if (newDecisionForm.disagreed_by) data.disagreed_by = newDecisionForm.disagreed_by.split(',').map(s => s.trim()).filter(Boolean)
    if (newDecisionForm.decided_by) data.decided_by = newDecisionForm.decided_by
    if (newDecisionForm.room_id) data.room_id = newDecisionForm.room_id

    const res = await createDecision(planId, version, data)
    planDecisions.value.push(res.data)
    // Reset form
    newDecisionForm.title = ''
    newDecisionForm.decision_text = ''
    newDecisionForm.description = ''
    newDecisionForm.rationale = ''
    newDecisionForm.alternatives_considered = ''
    newDecisionForm.agreed_by = ''
    newDecisionForm.disagreed_by = ''
    newDecisionForm.decided_by = ''
    newDecisionForm.room_id = ''
    showAddDecision.value = false
    editingDecisionId.value = null
  } catch (e) {
    console.error('handleCreateDecision failed', e)
  }
}

async function handleUpdateDecision(decisionId: string) {
  if (!currentPlan.value) return
  const planId = currentPlan.value.plan_id
  const version = planDetailActiveVersion.value
  const data: any = {}
  if (newDecisionForm.title) data.title = newDecisionForm.title
  if (newDecisionForm.decision_text) data.decision_text = newDecisionForm.decision_text
  if (newDecisionForm.description) data.description = newDecisionForm.description
  if (newDecisionForm.rationale) data.rationale = newDecisionForm.rationale
  try {
    await updateDecision(planId, version, decisionId, data)
    // Reload decisions
    await loadPlanDecisions()
    showAddDecision.value = false
    editingDecisionId.value = null
  } catch (e) {
    console.error('handleUpdateDecision failed', e)
  }
}

function startEditDecision(decision: any) {
  newDecisionForm.title = decision.title || ''
  newDecisionForm.decision_text = decision.decision_text || ''
  newDecisionForm.description = decision.description || ''
  newDecisionForm.rationale = decision.rationale || ''
  newDecisionForm.alternatives_considered = (decision.alternatives_considered || []).join('\n')
  newDecisionForm.agreed_by = (decision.agreed_by || []).join(', ')
  newDecisionForm.disagreed_by = (decision.disagreed_by || []).join(', ')
  newDecisionForm.decided_by = decision.decided_by || ''
  newDecisionForm.room_id = decision.room_id || ''
  editingDecisionId.value = decision.decision_id
  showAddDecision.value = true
}

function cancelEditDecision() {
  showAddDecision.value = false
  editingDecisionId.value = null
  newDecisionForm.title = ''
  newDecisionForm.decision_text = ''
  newDecisionForm.description = ''
  newDecisionForm.rationale = ''
  newDecisionForm.alternatives_considered = ''
  newDecisionForm.agreed_by = ''
  newDecisionForm.disagreed_by = ''
  newDecisionForm.decided_by = ''
  newDecisionForm.room_id = ''
}

// ─── Edicts Functions ───────────────────────────────────
async function loadPlanEdicts() {
  if (!currentPlan.value) return
  try {
    const res = await listEdicts(currentPlan.value.plan_id, planDetailActiveVersion.value)
    planEdicts.value = res.data?.edicts || []
    // 加载每个圣旨的签收记录
    for (const edict of planEdicts.value) {
      await loadEdictAcks(edict.edict_id)
    }
  } catch (e) {
    console.error('loadPlanEdicts failed', e)
  }
}

async function handleCreateEdict() {
  if (!newEdictForm.title.trim() || !newEdictForm.content.trim() || !currentPlan.value) return
  const planId = currentPlan.value.plan_id
  const version = planDetailActiveVersion.value
  try {
    const data: any = {
      title: newEdictForm.title,
      content: newEdictForm.content,
    }
    if (newEdictForm.issued_by) data.issued_by = newEdictForm.issued_by
    if (newEdictForm.recipients) data.recipients = newEdictForm.recipients.split(',').map((s: string) => s.trim()).filter(Boolean)
    if (newEdictForm.effective_from) data.effective_from = newEdictForm.effective_from
    if (newEdictForm.status) data.status = newEdictForm.status
    const res = await createEdict(planId, version, data)
    planEdicts.value.push(res.data)
    newEdictForm.title = ''
    newEdictForm.content = ''
    newEdictForm.issued_by = ''
    newEdictForm.recipients = ''
    newEdictForm.effective_from = ''
    newEdictForm.status = 'draft'
    showAddEdict.value = false
    editingEdictId.value = null
  } catch (e) {
    console.error('handleCreateEdict failed', e)
  }
}

async function handleUpdateEdict(edictId: string) {
  if (!currentPlan.value) return
  const planId = currentPlan.value.plan_id
  const version = planDetailActiveVersion.value
  const data: any = {}
  if (newEdictForm.title) data.title = newEdictForm.title
  if (newEdictForm.content) data.content = newEdictForm.content
  if (newEdictForm.issued_by) data.issued_by = newEdictForm.issued_by
  if (newEdictForm.recipients) data.recipients = newEdictForm.recipients.split(',').map((s: string) => s.trim()).filter(Boolean)
  if (newEdictForm.effective_from) data.effective_from = newEdictForm.effective_from
  if (newEdictForm.status) data.status = newEdictForm.status
  try {
    await updateEdict(planId, version, edictId, data)
    await loadPlanEdicts()
    showAddEdict.value = false
    editingEdictId.value = null
  } catch (e) {
    console.error('handleUpdateEdict failed', e)
  }
}

async function handleDeleteEdict(edictId: string) {
  if (!currentPlan.value) return
  if (!confirm('确认删除此圣旨？')) return
  const planId = currentPlan.value.plan_id
  const version = planDetailActiveVersion.value
  try {
    await deleteEdict(planId, version, edictId)
    planEdicts.value = planEdicts.value.filter(e => e.edict_id !== edictId)
  } catch (e) {
    console.error('handleDeleteEdict failed', e)
  }
}

function startEditEdict(edict: any) {
  newEdictForm.title = edict.title || ''
  newEdictForm.content = edict.content || ''
  newEdictForm.issued_by = edict.issued_by || ''
  newEdictForm.recipients = edict.recipients ? (Array.isArray(edict.recipients) ? edict.recipients.join(', ') : edict.recipients) : ''
  newEdictForm.effective_from = edict.effective_from || ''
  newEdictForm.status = edict.status || 'draft'
  editingEdictId.value = edict.edict_id
  showAddEdict.value = true
}

function cancelEditEdict() {
  showAddEdict.value = false
  editingEdictId.value = null
  newEdictForm.title = ''
  newEdictForm.content = ''
  newEdictForm.issued_by = ''
  newEdictForm.recipients = ''
  newEdictForm.effective_from = ''
  newEdictForm.status = 'draft'
}

async function loadEdictAcks(edictId: string) {
  if (!currentPlan.value) return
  const planId = currentPlan.value.plan_id
  const version = planDetailActiveVersion.value
  try {
    const res = await listEdictAcknowledgments(planId, version, edictId)
    edictAcknowledgments.value[edictId] = res.data?.acknowledgments || []
  } catch (e) {
    console.error('loadEdictAcks failed', e)
  }
}

function startAckEdict(edictId: string) {
  ackEdictId.value = edictId
  ackForm.acknowledged_by = ''
  ackForm.level = 5
  ackForm.comment = ''
  showAckForm.value = true
  loadEdictAcks(edictId)
}

async function handleAcknowledgeEdict() {
  if (!ackForm.acknowledged_by.trim() || !ackEdictId.value || !currentPlan.value) return
  const planId = currentPlan.value.plan_id
  const version = planDetailActiveVersion.value
  try {
    await acknowledgeEdict(planId, version, ackEdictId.value, {
      acknowledged_by: ackForm.acknowledged_by,
      level: ackForm.level,
      comment: ackForm.comment || undefined,
    })
    await loadEdictAcks(ackEdictId.value)
    ackForm.acknowledged_by = ''
    ackForm.level = 5
    ackForm.comment = ''
    showAckForm.value = false
    ackEdictId.value = null
  } catch (e) {
    console.error('handleAcknowledgeEdict failed', e)
  }
}

async function handleDeleteAck(edictId: string, ackId: string) {
  if (!currentPlan.value) return
  const planId = currentPlan.value.plan_id
  const version = planDetailActiveVersion.value
  try {
    await deleteEdictAcknowledgment(planId, version, edictId, ackId)
    await loadEdictAcks(edictId)
  } catch (e) {
    console.error('handleDeleteAck failed', e)
  }
}

async function loadPlanRisks() {
  if (!currentPlan.value) return
  try {
    const res = await listRisks(currentPlan.value.plan_id, planDetailActiveVersion.value)
    planRisks.value = res.data?.risks || []
  } catch (e) {
    console.error('loadPlanRisks failed', e)
  }
}

async function handleCreateRisk() {
  if (!newRiskForm.title.trim() || !currentPlan.value) return
  const planId = currentPlan.value.plan_id
  const version = planDetailActiveVersion.value
  try {
    const data: any = {
      title: newRiskForm.title,
    }
    if (newRiskForm.description) data.description = newRiskForm.description
    if (newRiskForm.probability) data.probability = newRiskForm.probability
    if (newRiskForm.impact) data.impact = newRiskForm.impact
    if (newRiskForm.mitigation) data.mitigation = newRiskForm.mitigation
    if (newRiskForm.contingency) data.contingency = newRiskForm.contingency
    if (newRiskForm.status) data.status = newRiskForm.status
    const res = await createRisk(planId, version, data)
    planRisks.value.push(res.data)
    newRiskForm.title = ''
    newRiskForm.description = ''
    newRiskForm.probability = 'medium'
    newRiskForm.impact = 'medium'
    newRiskForm.mitigation = ''
    newRiskForm.contingency = ''
    newRiskForm.status = 'identified'
    showAddRisk.value = false
    editingRiskId.value = null
  } catch (e) {
    console.error('handleCreateRisk failed', e)
  }
}

async function handleUpdateRisk(riskId: string) {
  if (!currentPlan.value) return
  const planId = currentPlan.value.plan_id
  const version = planDetailActiveVersion.value
  const data: any = {}
  if (newRiskForm.title) data.title = newRiskForm.title
  if (newRiskForm.description !== undefined) data.description = newRiskForm.description
  if (newRiskForm.probability) data.probability = newRiskForm.probability
  if (newRiskForm.impact) data.impact = newRiskForm.impact
  if (newRiskForm.mitigation !== undefined) data.mitigation = newRiskForm.mitigation
  if (newRiskForm.contingency !== undefined) data.contingency = newRiskForm.contingency
  if (newRiskForm.status) data.status = newRiskForm.status
  try {
    await updateRisk(planId, version, riskId, data)
    await loadPlanRisks()
    showAddRisk.value = false
    editingRiskId.value = null
  } catch (e) {
    console.error('handleUpdateRisk failed', e)
  }
}

async function handleDeleteRisk(riskId: string) {
  if (!currentPlan.value) return
  if (!confirm('确认删除此风险？')) return
  const planId = currentPlan.value.plan_id
  const version = planDetailActiveVersion.value
  try {
    await deleteRisk(planId, version, riskId)
    planRisks.value = planRisks.value.filter(r => r.risk_id !== riskId)
  } catch (e) {
    console.error('handleDeleteRisk failed', e)
  }
}

function startEditRisk(risk: any) {
  newRiskForm.title = risk.title || ''
  newRiskForm.description = risk.description || ''
  newRiskForm.probability = risk.probability || 'medium'
  newRiskForm.impact = risk.impact || 'medium'
  newRiskForm.mitigation = risk.mitigation || ''
  newRiskForm.contingency = risk.contingency || ''
  newRiskForm.status = risk.status || 'identified'
  editingRiskId.value = risk.risk_id
  showAddRisk.value = true
}

function cancelEditRisk() {
  showAddRisk.value = false
  editingRiskId.value = null
  newRiskForm.title = ''
  newRiskForm.description = ''
  newRiskForm.probability = 'medium'
  newRiskForm.impact = 'medium'
  newRiskForm.mitigation = ''
  newRiskForm.contingency = ''
  newRiskForm.status = 'identified'
}

// ─── Approval Functions ─────────────────────────────────
async function loadApprovalFlow() {
  if (!currentPlan.value) return
  loadingApproval.value = true
  try {
    const [flowRes, levelsRes] = await Promise.all([
      getApproval(currentPlan.value.plan_id),
      getApprovalLevels(currentPlan.value.plan_id),
    ])
    approvalFlow.value = flowRes.data
    approvalLevels.value = levelsRes.data || []
  } catch (e: any) {
    if (e.response?.status === 404) {
      approvalFlow.value = null
      approvalLevels.value = []
    }
  } finally {
    loadingApproval.value = false
  }
}

async function handleStartApproval() {
  if (!currentPlan.value) return
  const skipLevels = skipLevelsInput.value
    ? skipLevelsInput.value.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
    : []
  try {
    await startApproval(currentPlan.value.plan_id, {
      initiator_id: startApprovalForm.initiator_id,
      initiator_name: startApprovalForm.initiator_name,
      skip_levels: skipLevels,
    })
    showStartApproval.value = false
    skipLevelsInput.value = ''
    await loadApprovalFlow()
  } catch (e) {
    console.error('startApproval failed', e)
  }
}

async function handleApprovalAction(level: number, action: string) {
  if (!currentPlan.value) return
  try {
    await approvalAction(currentPlan.value.plan_id, level, {
      action,
      actor_id: startApprovalForm.initiator_id,
      actor_name: startApprovalForm.initiator_name,
      comment: approvalActionComment[level] || '',
    })
    approvalActionComment[level] = ''
    await loadApprovalFlow()
  } catch (e) {
    console.error('approvalAction failed', e)
  }
}

// ─── Constraints Handlers ────────────────────────────────
async function handleCreateConstraint() {
  if (!newConstraintForm.value.trim() || !currentPlan.value) return
  try {
    const res = await createConstraint(currentPlan.value.plan_id, {
      type: newConstraintForm.type,
      value: newConstraintForm.value,
      unit: newConstraintForm.unit,
      description: newConstraintForm.description,
    })
    planConstraints.value.push(res.data)
    cancelEditConstraint()
  } catch (e) {
    console.error('handleCreateConstraint failed', e)
  }
}

async function handleUpdateConstraint(constraintId: string) {
  if (!currentPlan.value) return
  try {
    await updateConstraint(currentPlan.value.plan_id, constraintId, {
      type: newConstraintForm.type,
      value: newConstraintForm.value,
      unit: newConstraintForm.unit,
      description: newConstraintForm.description,
    })
    const idx = planConstraints.value.findIndex(c => c.constraint_id === constraintId)
    if (idx !== -1) {
      planConstraints.value[idx] = { ...planConstraints.value[idx], ...newConstraintForm }
    }
    cancelEditConstraint()
  } catch (e) {
    console.error('handleUpdateConstraint failed', e)
  }
}

async function handleDeleteConstraint(constraintId: string) {
  if (!currentPlan.value) return
  try {
    await deleteConstraint(currentPlan.value.plan_id, constraintId)
    planConstraints.value = planConstraints.value.filter(c => c.constraint_id !== constraintId)
  } catch (e) {
    console.error('handleDeleteConstraint failed', e)
  }
}

function startEditConstraint(constraint: any) {
  editingConstraintId.value = constraint.constraint_id
  showAddConstraint.value = true
  newConstraintForm.type = constraint.type
  newConstraintForm.value = constraint.value
  newConstraintForm.unit = constraint.unit || ''
  newConstraintForm.description = constraint.description || ''
}

function cancelEditConstraint() {
  showAddConstraint.value = false
  editingConstraintId.value = null
  newConstraintForm.type = 'budget'
  newConstraintForm.value = ''
  newConstraintForm.unit = ''
  newConstraintForm.description = ''
}

// ─── Stakeholders Handlers ───────────────────────────────
async function handleCreateStakeholder() {
  if (!newStakeholderForm.name.trim() || !currentPlan.value) return
  try {
    const res = await createStakeholder(currentPlan.value.plan_id, {
      name: newStakeholderForm.name,
      level: newStakeholderForm.level,
      interest: newStakeholderForm.interest,
      influence: newStakeholderForm.influence,
      description: newStakeholderForm.description,
    })
    planStakeholders.value.push(res.data)
    cancelEditStakeholder()
  } catch (e) {
    console.error('handleCreateStakeholder failed', e)
  }
}

async function handleUpdateStakeholder(stakeholderId: string) {
  if (!currentPlan.value) return
  try {
    await updateStakeholder(currentPlan.value.plan_id, stakeholderId, {
      name: newStakeholderForm.name,
      level: newStakeholderForm.level,
      interest: newStakeholderForm.interest,
      influence: newStakeholderForm.influence,
      description: newStakeholderForm.description,
    })
    const idx = planStakeholders.value.findIndex(s => s.stakeholder_id === stakeholderId)
    if (idx !== -1) {
      planStakeholders.value[idx] = { ...planStakeholders.value[idx], ...newStakeholderForm }
    }
    cancelEditStakeholder()
  } catch (e) {
    console.error('handleUpdateStakeholder failed', e)
  }
}

async function handleDeleteStakeholder(stakeholderId: string) {
  if (!currentPlan.value) return
  try {
    await deleteStakeholder(currentPlan.value.plan_id, stakeholderId)
    planStakeholders.value = planStakeholders.value.filter(s => s.stakeholder_id !== stakeholderId)
  } catch (e) {
    console.error('handleDeleteStakeholder failed', e)
  }
}

function startEditStakeholder(stakeholder: any) {
  editingStakeholderId.value = stakeholder.stakeholder_id
  showAddStakeholder.value = true
  newStakeholderForm.name = stakeholder.name
  newStakeholderForm.level = stakeholder.level || 5
  newStakeholderForm.interest = stakeholder.interest || ''
  newStakeholderForm.influence = stakeholder.influence || ''
  newStakeholderForm.description = stakeholder.description || ''
}

function cancelEditStakeholder() {
  showAddStakeholder.value = false
  editingStakeholderId.value = null
  newStakeholderForm.name = ''
  newStakeholderForm.level = 5
  newStakeholderForm.interest = ''
  newStakeholderForm.influence = ''
  newStakeholderForm.description = ''
}

// ─── Requirements Handlers ───────────────────────────────────────────────────────
async function handleCreateRequirement() {
  if (!newRequirementForm.description.trim() || !currentPlan.value) return
  try {
    const res = await createRequirement(currentPlan.value.plan_id, {
      description: newRequirementForm.description,
      priority: newRequirementForm.priority,
      category: newRequirementForm.category,
      status: newRequirementForm.status,
      notes: newRequirementForm.notes,
    })
    planRequirements.value.push(res.data)
    cancelEditRequirement()
  } catch (e) {
    console.error('handleCreateRequirement failed', e)
  }
}

async function handleUpdateRequirement(reqId: string) {
  if (!currentPlan.value) return
  try {
    await updateRequirement(currentPlan.value.plan_id, reqId, {
      description: newRequirementForm.description,
      priority: newRequirementForm.priority,
      category: newRequirementForm.category,
      status: newRequirementForm.status,
      notes: newRequirementForm.notes,
    })
    const idx = planRequirements.value.findIndex(r => r.id === reqId)
    if (idx !== -1) {
      planRequirements.value[idx] = {
        ...planRequirements.value[idx],
        description: newRequirementForm.description,
        priority: newRequirementForm.priority,
        category: newRequirementForm.category,
        status: newRequirementForm.status,
        notes: newRequirementForm.notes,
      }
    }
    cancelEditRequirement()
  } catch (e) {
    console.error('handleUpdateRequirement failed', e)
  }
}

async function handleDeleteRequirement(reqId: string) {
  if (!currentPlan.value) return
  try {
    await deleteRequirement(currentPlan.value.plan_id, reqId)
    planRequirements.value = planRequirements.value.filter(r => r.id !== reqId)
  } catch (e) {
    console.error('handleDeleteRequirement failed', e)
  }
}

function startEditRequirement(req: any) {
  editingRequirementId.value = req.id
  showAddRequirement.value = true
  newRequirementForm.description = req.description || ''
  newRequirementForm.priority = req.priority || 'medium'
  newRequirementForm.category = req.category || 'other'
  newRequirementForm.status = req.status || 'pending'
  newRequirementForm.notes = req.notes || ''
}

function cancelEditRequirement() {
  showAddRequirement.value = false
  editingRequirementId.value = null
  newRequirementForm.description = ''
  newRequirementForm.priority = 'medium'
  newRequirementForm.category = 'other'
  newRequirementForm.status = 'pending'
  newRequirementForm.notes = ''
}

async function handleCreateRoom() {
  if (!newRoomForm.topic.trim() || !currentPlan.value) return
  try {
    const res = await api.post('/rooms', {
      topic: newRoomForm.topic,
      title: newRoomForm.title || newRoomForm.topic,
      plan_id: currentPlan.value.plan_id,
      version: planDetailActiveVersion.value,
      mode: newRoomForm.mode,
    })
    const room = res.data
    newRoomForm.topic = ''
    newRoomForm.title = ''
    showCreateRoom.value = false
    // Refresh rooms list
    const roomsRes = await getRoomsByPlan(currentPlan.value.plan_id)
    planRooms.value = roomsRes.data?.rooms || []
    // Enter the room
    await enterRoom(room.room_id)
  } catch (e) {
    console.error('createRoom failed', e)
  }
}

async function loadRoomTemplates() {
  try {
    const res = await listRoomTemplates()
    roomTemplates.value = res.data?.templates || []
  } catch (e) {
    console.error('loadRoomTemplates failed', e)
  }
}

async function openRoomTemplates() {
  showRoomTemplates.value = true
  showCreateTemplate.value = false
  editingTemplate.value = null
  await loadRoomTemplates()
}

async function handleSaveTemplate() {
  if (!newTemplateForm.name.trim()) return
  try {
    if (editingTemplate.value) {
      await updateRoomTemplate(editingTemplate.value.template_id, {
        name: newTemplateForm.name,
        description: newTemplateForm.description,
        purpose: newTemplateForm.purpose,
        mode: newTemplateForm.mode,
        default_phase: newTemplateForm.default_phase,
        settings: newTemplateForm.settings,
        is_shared: newTemplateForm.is_shared,
      })
    } else {
      await createRoomTemplate({
        name: newTemplateForm.name,
        description: newTemplateForm.description,
        purpose: newTemplateForm.purpose,
        mode: newTemplateForm.mode,
        default_phase: newTemplateForm.default_phase,
        settings: newTemplateForm.settings,
        is_shared: newTemplateForm.is_shared,
      })
    }
    showCreateTemplate.value = false
    editingTemplate.value = null
    await loadRoomTemplates()
  } catch (e) {
    console.error('handleSaveTemplate failed', e)
  }
}

function startEditTemplate(tmpl: any) {
  editingTemplate.value = tmpl
  Object.assign(newTemplateForm, {
    name: tmpl.name,
    description: tmpl.description || '',
    purpose: tmpl.purpose || 'initial_discussion',
    mode: tmpl.mode || 'hierarchical',
    default_phase: tmpl.default_phase || 'selecting',
    settings: typeof tmpl.settings === 'object' ? tmpl.settings : {},
    is_shared: tmpl.is_shared || false,
  })
  showCreateTemplate.value = true
}

async function handleDeleteTemplate(templateId: string) {
  if (!confirm('确定删除此模板？')) return
  try {
    await deleteRoomTemplate(templateId)
    await loadRoomTemplates()
  } catch (e) {
    console.error('handleDeleteTemplate failed', e)
  }
}

// ─── Plan Template Functions ────────────────────────────────
async function loadPlanTemplates() {
  try {
    const res = await listPlanTemplates()
    planTemplates.value = Array.isArray(res.data) ? res.data : (res.data?.templates || [])
  } catch (e) {
    console.error('loadPlanTemplates failed', e)
  }
}

async function openPlanTemplates() {
  showPlanTemplates.value = true
  showCreatePlanTemplate.value = false
  editingPlanTemplate.value = null
  await loadPlanTemplates()
}

async function handleSavePlanTemplate() {
  if (!newPlanTemplateForm.name.trim()) return
  try {
    if (editingPlanTemplate.value) {
      await updatePlanTemplate(editingPlanTemplate.value.template_id, {
        name: newPlanTemplateForm.name,
        description: newPlanTemplateForm.description,
        plan_content: newPlanTemplateForm.plan_content,
        tags: newPlanTemplateForm.tags,
        is_shared: newPlanTemplateForm.is_shared,
      })
    } else {
      await createPlanTemplate({
        name: newPlanTemplateForm.name,
        description: newPlanTemplateForm.description,
        plan_content: newPlanTemplateForm.plan_content,
        tags: newPlanTemplateForm.tags,
        is_shared: newPlanTemplateForm.is_shared,
      })
    }
    showCreatePlanTemplate.value = false
    editingPlanTemplate.value = null
    await loadPlanTemplates()
  } catch (e) {
    console.error('handleSavePlanTemplate failed', e)
  }
}

function startEditPlanTemplate(tmpl: any) {
  editingPlanTemplate.value = tmpl
  Object.assign(newPlanTemplateForm, {
    name: tmpl.name,
    description: tmpl.description || '',
    plan_content: typeof tmpl.plan_content === 'object' ? tmpl.plan_content : {},
    tags: Array.isArray(tmpl.tags) ? tmpl.tags : [],
    is_shared: tmpl.is_shared || false,
  })
  showCreatePlanTemplate.value = true
}

async function handleDeletePlanTemplate(templateId: string) {
  if (!confirm('确定删除此计划模板？')) return
  try {
    await deletePlanTemplate(templateId)
    await loadPlanTemplates()
  } catch (e) {
    console.error('handleDeletePlanTemplate failed', e)
  }
}

async function handleCreatePlanFromTemplate(tmpl: any) {
  try {
    const res = await createPlanFromTemplate(tmpl.template_id, {
      title: `${tmpl.name} - 副本`,
      topic: tmpl.description || '',
    })
    showPlanTemplates.value = false
    // Refresh plans list and navigate to new plan
    const plansRes = await listPlans()
    plans.value = plansRes.data?.plans || []
    // Navigate to the new plan if we're on home view
    if (res.data?.plan_id) {
      await openPlanDetail(res.data.plan_id)
    }
  } catch (e) {
    console.error('handleCreatePlanFromTemplate failed', e)
  }
}

// Step 73: Task Template Functions
async function loadTaskTemplates() {
  try {
    const res = await listTaskTemplates()
    taskTemplates.value = Array.isArray(res.data) ? res.data : (res.data?.templates || [])
  } catch (e) {
    console.error('loadTaskTemplates failed', e)
  }
}

async function openTaskTemplates() {
  showTaskTemplates.value = true
  showCreateTaskTemplate.value = false
  editingTaskTemplate.value = null
  await loadTaskTemplates()
}

async function handleSaveTaskTemplate() {
  if (!newTaskTemplateForm.name.trim() || !newTaskTemplateForm.default_title.trim()) return
  try {
    if (editingTaskTemplate.value) {
      await updateTaskTemplate(editingTaskTemplate.value.template_id, {
        name: newTaskTemplateForm.name,
        description: newTaskTemplateForm.description,
        default_title: newTaskTemplateForm.default_title,
        default_description: newTaskTemplateForm.default_description,
        priority: newTaskTemplateForm.priority,
        difficulty: newTaskTemplateForm.difficulty,
        estimated_hours: newTaskTemplateForm.estimated_hours,
        owner_level: newTaskTemplateForm.owner_level,
        owner_role: newTaskTemplateForm.owner_role,
        tags: newTaskTemplateForm.tags,
        is_shared: newTaskTemplateForm.is_shared,
      })
    } else {
      await createTaskTemplate({
        name: newTaskTemplateForm.name,
        description: newTaskTemplateForm.description,
        default_title: newTaskTemplateForm.default_title,
        default_description: newTaskTemplateForm.default_description,
        priority: newTaskTemplateForm.priority,
        difficulty: newTaskTemplateForm.difficulty,
        estimated_hours: newTaskTemplateForm.estimated_hours,
        owner_level: newTaskTemplateForm.owner_level,
        owner_role: newTaskTemplateForm.owner_role,
        tags: newTaskTemplateForm.tags,
        created_by: newTaskTemplateForm.created_by,
        is_shared: newTaskTemplateForm.is_shared,
      })
    }
    showCreateTaskTemplate.value = false
    editingTaskTemplate.value = null
    await loadTaskTemplates()
  } catch (e) {
    console.error('handleSaveTaskTemplate failed', e)
  }
}

function startEditTaskTemplate(tmpl: any) {
  editingTaskTemplate.value = tmpl
  Object.assign(newTaskTemplateForm, {
    name: tmpl.name,
    description: tmpl.description || '',
    default_title: tmpl.default_title || '',
    default_description: tmpl.default_description || '',
    priority: tmpl.priority || 'medium',
    difficulty: tmpl.difficulty || 'medium',
    estimated_hours: tmpl.estimated_hours ?? null,
    owner_level: tmpl.owner_level ?? null,
    owner_role: tmpl.owner_role || '',
    tags: Array.isArray(tmpl.tags) ? tmpl.tags : [],
    is_shared: tmpl.is_shared || false,
  })
  showCreateTaskTemplate.value = true
}

async function handleDeleteTaskTemplate(templateId: string) {
  if (!confirm('确定删除此任务模板？')) return
  try {
    await deleteTaskTemplate(templateId)
    await loadTaskTemplates()
  } catch (e) {
    console.error('handleDeleteTaskTemplate failed', e)
  }
}

async function handleCreateTaskFromTemplate(tmpl: any) {
  if (!currentPlan.value) return
  try {
    const res = await createTaskFromTemplate(
      tmpl.template_id,
      currentPlan.value.plan_id,
      planDetailActiveVersion.value,
    )
    showTaskTemplates.value = false
    // Refresh tasks list
    await loadTasks()
    // Show success notification
    if (res.data?.task_id) {
      const task = res.data.task
      alert(`任务「${task?.title || tmpl.default_title}」已创建`)
    }
  } catch (e) {
    console.error('handleCreateTaskFromTemplate failed', e)
  }
}

async function handleCreateRoomFromTemplate(tmpl: any) {
  if (!currentPlan.value) return
  try {
    const res = await createRoomFromTemplate(currentPlan.value.plan_id, tmpl.template_id, {
      topic: tmpl.name,
      version: planDetailActiveVersion.value,
    })
    showRoomTemplates.value = false
    // Refresh rooms list
    const roomsRes = await getRoomsByPlan(currentPlan.value.plan_id)
    planRooms.value = roomsRes.data?.rooms || []
    // Enter the room
    await enterRoom(res.data.room_id)
  } catch (e) {
    console.error('handleCreateRoomFromTemplate failed', e)
  }
}

async function handleExportPlan() {
  if (!currentPlan.value || exportLoading.value) return
  exportLoading.value = true
  try {
    const res = await exportPlanMarkdown(currentPlan.value.plan_id)
    const blob = new Blob([res.data as string], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${currentPlan.value.plan_number || currentPlan.value.plan_id}.md`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error('exportPlan failed', e)
  } finally {
    exportLoading.value = false
  }
}

async function handleExportVersion() {
  if (!currentPlan.value || !planDetailActiveVersion.value || exportLoading.value) return
  exportLoading.value = true
  try {
    const res = await exportVersionMarkdown(currentPlan.value.plan_id, planDetailActiveVersion.value)
    const blob = new Blob([res.data as string], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${currentPlan.value.plan_number || currentPlan.value.plan_id}-${planDetailActiveVersion.value}.md`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error('exportVersion failed', e)
  } finally {
    exportLoading.value = false
  }
}

async function openRoomHierarchy(room: any, event: Event) {
  event.stopPropagation()
  event.preventDefault()
  selectedRoomForHierarchy.value = room
  showRoomHierarchy.value = true
  hierarchyActiveTab.value = 'view'
  hierarchyLoading.value = true
  try {
    const res = await getRoomHierarchy(room.room_id)
    roomHierarchyData.value = res.data
    // Pre-fill link form with current values
    hierarchyLinkForm.parent_room_id = res.data.parent?.room_id || ''
    hierarchyLinkForm.child_rooms = (res.data.children || []).map((c: any) => c.room_id)
    hierarchyLinkForm.related_rooms = (res.data.related || []).map((r: any) => r.room_id)
  } catch (e) {
    console.error('load hierarchy failed', e)
    roomHierarchyData.value = { room_id: room.room_id, parent: null, children: [], related: [] }
  } finally {
    hierarchyLoading.value = false
  }
}

async function handleLinkRoom() {
  if (!selectedRoomForHierarchy.value) return
  hierarchyActionLoading.value = true
  try {
    await linkRoom(selectedRoomForHierarchy.value.room_id, {
      parent_room_id: hierarchyLinkForm.parent_room_id || undefined,
      child_rooms: hierarchyLinkForm.child_rooms.length ? hierarchyLinkForm.child_rooms : undefined,
      related_rooms: hierarchyLinkForm.related_rooms.length ? hierarchyLinkForm.related_rooms : undefined,
    })
    // Reload hierarchy
    const res = await getRoomHierarchy(selectedRoomForHierarchy.value.room_id)
    roomHierarchyData.value = res.data
    hierarchyLinkForm.parent_room_id = res.data.parent?.room_id || ''
    hierarchyLinkForm.child_rooms = (res.data.children || []).map((c: any) => c.room_id)
    hierarchyLinkForm.related_rooms = (res.data.related || []).map((r: any) => r.room_id)
  } catch (e) {
    console.error('link room failed', e)
    alert('链接房间失败: ' + (e as any)?.response?.data?.detail || (e as Error).message)
  } finally {
    hierarchyActionLoading.value = false
  }
}

async function handleConcludeRoom() {
  if (!selectedRoomForHierarchy.value) return
  hierarchyActionLoading.value = true
  try {
    await concludeRoom(selectedRoomForHierarchy.value.room_id, {
      summary: hierarchyConcludeForm.summary || undefined,
      conclusion: hierarchyConcludeForm.conclusion || undefined,
    })
    hierarchyConcludeForm.summary = ''
    hierarchyConcludeForm.conclusion = ''
    hierarchyActiveTab.value = 'view'
    // Reload rooms list
    if (currentPlan.value) {
      const roomsRes = await getRoomsByPlan(currentPlan.value.plan_id)
      planRooms.value = roomsRes.data?.rooms || []
    }
  } catch (e) {
    console.error('conclude room failed', e)
    alert('结束房间失败: ' + (e as any)?.response?.data?.detail || (e as Error).message)
  } finally {
    hierarchyActionLoading.value = false
  }
}

// Room Tags Management
function toggleRoomTags() {
  showRoomTagsModal.value = !showRoomTagsModal.value
  roomTagsForm.newTag = ''
}

async function handleAddRoomTag() {
  if (!currentRoom.value || !roomTagsForm.newTag.trim()) return
  roomTagsLoading.value = true
  try {
    const res = await addRoomTags(currentRoom.value.room_id, [roomTagsForm.newTag.trim()])
    currentRoom.value.tags = res.data.tags
    roomTagsForm.newTag = ''
    // Refresh rooms list
    if (currentPlan.value) {
      const roomsRes = await getRoomsByPlan(currentPlan.value.plan_id)
      planRooms.value = roomsRes.data?.rooms || []
    }
  } catch (e) {
    console.error('add room tag failed', e)
    alert('添加标签失败: ' + (e as any)?.response?.data?.detail || (e as Error).message)
  } finally {
    roomTagsLoading.value = false
  }
}

async function handleRemoveRoomTag(tag: string) {
  if (!currentRoom.value) return
  roomTagsLoading.value = true
  try {
    const res = await removeRoomTags(currentRoom.value.room_id, [tag])
    currentRoom.value.tags = res.data.tags
    // Refresh rooms list
    if (currentPlan.value) {
      const roomsRes = await getRoomsByPlan(currentPlan.value.plan_id)
      planRooms.value = roomsRes.data?.rooms || []
    }
  } catch (e) {
    console.error('remove room tag failed', e)
    alert('移除标签失败: ' + (e as any)?.response?.data?.detail || (e as Error).message)
  } finally {
    roomTagsLoading.value = false
  }
}

async function handleUpdateRoomTags(tags: string[]) {
  if (!currentRoom.value) return
  roomTagsLoading.value = true
  try {
    const res = await updateRoomTags(currentRoom.value.room_id, tags)
    currentRoom.value.tags = res.data.tags
    // Refresh rooms list
    if (currentPlan.value) {
      const roomsRes = await getRoomsByPlan(currentPlan.value.plan_id)
      planRooms.value = roomsRes.data?.rooms || []
    }
  } catch (e) {
    console.error('update room tags failed', e)
    alert('更新标签失败: ' + (e as any)?.response?.data?.detail || (e as Error).message)
  } finally {
    roomTagsLoading.value = false
  }
}

function getTaskTitle(taskId: string): string {
  const task = planTasks.value.find(t => t.task_id === taskId)
  return task ? (task.task_number ? `${task.task_number} ${task.title}` : task.title) : ''
}

async function openTaskDependencies() {
  if (!currentPlan.value) return
  showTaskDependencies.value = true
  dependencyLoading.value = true
  try {
    const version = planDetailActiveVersion.value || currentPlan.value.current_version
    const [graphRes, blockedRes] = await Promise.all([
      getTaskDependencyGraph(currentPlan.value.plan_id, version),
      getBlockedTasks(currentPlan.value.plan_id, version),
    ])
    dependencyGraph.value = graphRes.data
    blockedTasks.value = blockedRes.data?.tasks || []
  } catch (e) {
    console.error('load dependency graph failed', e)
    dependencyGraph.value = null
  } finally {
    dependencyLoading.value = false
  }
}

async function openTaskDetail(task: any) {
  if (!currentPlan.value) return
  selectedTaskForDetail.value = task
  showTaskDetail.value = true
  taskDetailActiveTab.value = 'comments'
  taskDetailLoading.value = true
  taskTimeLoading.value = true
  try {
    const version = planDetailActiveVersion.value || currentPlan.value.current_version
    const [commentsRes, checkpointsRes, timeEntriesRes, timeSummaryRes] = await Promise.all([
      listTaskComments(currentPlan.value.plan_id, version, task.task_id),
      listTaskCheckpoints(currentPlan.value.plan_id, version, task.task_id),
      listTimeEntries(currentPlan.value.plan_id, version, task.task_id),
      getTimeSummary(currentPlan.value.plan_id, version, task.task_id),
    ])
    taskDetailComments.value = commentsRes.data?.comments || commentsRes.data || []
    taskDetailCheckpoints.value = checkpointsRes.data?.checkpoints || checkpointsRes.data || []
    taskTimeEntries.value = timeEntriesRes.data || []
    taskTimeSummary.value = timeSummaryRes.data || null
  } catch (e) {
    console.error('load task detail failed', e)
    taskDetailComments.value = []
    taskDetailCheckpoints.value = []
    taskTimeEntries.value = []
    taskTimeSummary.value = null
  } finally {
    taskDetailLoading.value = false
    taskTimeLoading.value = false
  }
}

async function handleCreateComment() {
  if (!currentPlan.value || !selectedTaskForDetail.value || !newCommentForm.content.trim()) return
  const version = planDetailActiveVersion.value || currentPlan.value.current_version
  try {
    await createTaskComment(currentPlan.value.plan_id, version, selectedTaskForDetail.value.task_id, {
      author_name: newCommentForm.author_name || 'Guest',
      content: newCommentForm.content,
    })
    newCommentForm.content = ''
    // reload comments
    const commentsRes = await listTaskComments(currentPlan.value.plan_id, version, selectedTaskForDetail.value.task_id)
    taskDetailComments.value = commentsRes.data?.comments || commentsRes.data || []
  } catch (e) {
    console.error('create comment failed', e)
  }
}

async function handleCreateCheckpoint() {
  if (!currentPlan.value || !selectedTaskForDetail.value || !newCheckpointForm.name.trim()) return
  const version = planDetailActiveVersion.value || currentPlan.value.current_version
  try {
    await createTaskCheckpoint(currentPlan.value.plan_id, version, selectedTaskForDetail.value.task_id, {
      name: newCheckpointForm.name,
      status: newCheckpointForm.status,
    })
    newCheckpointForm.name = ''
    newCheckpointForm.status = 'pending'
    // reload checkpoints
    const checkpointsRes = await listTaskCheckpoints(currentPlan.value.plan_id, version, selectedTaskForDetail.value.task_id)
    taskDetailCheckpoints.value = checkpointsRes.data?.checkpoints || checkpointsRes.data || []
  } catch (e) {
    console.error('create checkpoint failed', e)
  }
}

async function handleCreateTimeEntry() {
  if (!currentPlan.value || !selectedTaskForDetail.value || !newTimeEntryForm.hours) return
  const hours = parseFloat(newTimeEntryForm.hours)
  if (isNaN(hours) || hours <= 0) return
  const version = planDetailActiveVersion.value || currentPlan.value.current_version
  try {
    await createTimeEntry(currentPlan.value.plan_id, version, selectedTaskForDetail.value.task_id, {
      user_name: newTimeEntryForm.user_name || 'Guest',
      hours,
      description: newTimeEntryForm.description,
    })
    newTimeEntryForm.user_name = ''
    newTimeEntryForm.hours = ''
    newTimeEntryForm.description = ''
    // reload time entries and summary
    const [entriesRes, summaryRes] = await Promise.all([
      listTimeEntries(currentPlan.value.plan_id, version, selectedTaskForDetail.value.task_id),
      getTimeSummary(currentPlan.value.plan_id, version, selectedTaskForDetail.value.task_id),
    ])
    taskTimeEntries.value = entriesRes.data || []
    taskTimeSummary.value = summaryRes.data || null
    // Also update the task's actual_hours in the task list
    if (selectedTaskForDetail.value) {
      selectedTaskForDetail.value.actual_hours = taskTimeSummary.value?.total_hours || 0
    }
  } catch (e) {
    console.error('create time entry failed', e)
  }
}

async function handleDeleteTimeEntry(entryId: string) {
  if (!currentPlan.value || !selectedTaskForDetail.value) return
  const version = planDetailActiveVersion.value || currentPlan.value.current_version
  try {
    await deleteTimeEntry(entryId)
    const [entriesRes, summaryRes] = await Promise.all([
      listTimeEntries(currentPlan.value.plan_id, version, selectedTaskForDetail.value.task_id),
      getTimeSummary(currentPlan.value.plan_id, version, selectedTaskForDetail.value.task_id),
    ])
    taskTimeEntries.value = entriesRes.data || []
    taskTimeSummary.value = summaryRes.data || null
    if (selectedTaskForDetail.value) {
      selectedTaskForDetail.value.actual_hours = taskTimeSummary.value?.total_hours || 0
    }
  } catch (e) {
    console.error('delete time entry failed', e)
  }
}

async function enterRoom(roomId: string) {
  try {
    const [roomRes, phaseRes] = await Promise.all([
      getRoom(roomId),
      getPhase(roomId),
    ])
    currentRoom.value = roomRes.data
    currentPhase.value = phaseRes.data
    participants.value = roomRes.data.participants || []
    messages.value = []
    // Step 64: Initialize activity stream when entering room
    roomActivityStream.value = []

    // Load existing context/history
    try {
      const ctx = await api.get(`/rooms/${roomId}/context`)
      if (ctx.data?.recent_history?.length) {
        messages.value = ctx.data.recent_history
      }
    } catch {}

    // Load tasks for the plan
    const planId = roomRes.data.plan_id
    const version = roomRes.data.version || roomRes.data.current_version || 'v1.0'
    if (planId) {
      try {
        const [tasksRes, metricsRes] = await Promise.all([
          listTasks(planId, version),
          getTaskMetrics(planId, version),
        ])
        tasks.value = tasksRes.data?.tasks || []
        taskMetrics.value = metricsRes.data
      } catch (e) {
        console.error('loadTasks failed', e)
        tasks.value = []
        taskMetrics.value = null
      }
    }

    // Load debate state if room is in DEBATE phase
    try {
      const ds = await getDebateState(roomId)
      debateState.value = ds.data
    } catch {
      debateState.value = null
    }

    // Step 63: Load phase timeline
    try {
      const tl = await getRoomPhaseTimeline(roomId)
      phaseTimeline.value = tl.data?.timeline || []
    } catch {
      phaseTimeline.value = []
    }

    // Load problem state if room is in a problem phase
    if (problemStates.includes(phaseRes.data?.current_phase)) {
      await loadProblemState(roomId, planId)
    }

    // Load hierarchical review / converging context for HIERARCHICAL_REVIEW or CONVERGING phase
    const initPhase = phaseRes.data?.current_phase
    if (initPhase === 'HIERARCHICAL_REVIEW' || initPhase === 'CONVERGING') {
      await loadHierarchicalReviewData(roomId)
    }

    connectWs(roomId)
    phasePollInterval = setInterval(async () => {
      try {
        const r = await getPhase(roomId)
        currentPhase.value = r.data
        // Refresh debate state when in DEBATE phase
        if (r.data?.current_phase === 'DEBATE') {
          try {
            const ds = await getDebateState(roomId)
            debateState.value = ds.data
          } catch {}
        }
        // Refresh problem state when in problem phases
        if (problemStates.includes(r.data?.current_phase)) {
          try {
            await loadProblemState(roomId, currentRoom.value?.plan_id)
          } catch {}
        }
        // Refresh hierarchical review data when in HIERARCHICAL_REVIEW or CONVERGING phase
        if (r.data?.current_phase === 'HIERARCHICAL_REVIEW' || r.data?.current_phase === 'CONVERGING') {
          await loadHierarchicalReviewData(roomId)
        }
      } catch {}
    }, 3000)

    view.value = 'room'
  } catch (e) {
    console.error('enterRoom failed', e)
  }
}

function leaveRoom() {
  wsCurrentRoom = null  // prevent auto-reconnect
  wsReconnectTimers.forEach(t => clearTimeout(t))
  wsReconnectTimers.length = 0
  if (ws) { ws.close(); ws = null }
  if (phasePollInterval) { clearInterval(phasePollInterval); phasePollInterval = null }
  currentRoom.value = null
  messages.value = []
  showAddParticipant.value = false
  showAddTask.value = false
  tasks.value = []
  taskMetrics.value = null
  debateState.value = null
  phaseTimeline.value = []
  roomActivityStream.value = []
  hierarchicalReviewData.value = null
  showAddDebatePoint.value = false
  wsStatus.value = 'disconnected'
  // Clear message search
  messageSearchQuery.value = ''
  messageSearchResults.value = []
  messageSearchActive.value = false
  view.value = 'plan_detail'
}

function backToHome() {
  view.value = 'home'
  currentPlan.value = null
  planVersions.value = []
  planRooms.value = []
  loadPlans()
  loadDashboardStats()
}

// ─── Room Actions ────────────────────────────────────────
function connectWs(roomId: string) {
  // Clear any pending reconnect timers
  wsReconnectTimers.forEach(t => clearTimeout(t))
  wsReconnectTimers.length = 0

  if (ws) ws.close()
  wsCurrentRoom = roomId
  wsReconnectAttempt = 0
  wsStatus.value = 'connecting'

  ws = new WebSocket(wsUrl(roomId))

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    const now = new Date().toISOString()
    if (msg.type === 'phase_change') {
      if (currentPhase.value) currentPhase.value.current_phase = msg.to_phase
      // Step 64: Push phase change to activity stream
      roomActivityStream.value.unshift({
        id: 'stream-' + Date.now(),
        event_type: 'phase_change',
        icon: '🔄',
        actor: msg.actor_name || msg.actor_id || 'System',
        detail: `${phaseLabel[msg.from_phase] || msg.from_phase} → ${phaseLabel[msg.to_phase] || msg.to_phase}`,
        timestamp: now,
      })
    } else if (msg.type === 'speech') {
      messages.value.push(msg)
      // Step 64: Push speech to activity stream (throttle: only first message per sender in a batch)
      roomActivityStream.value.unshift({
        id: 'stream-' + Date.now(),
        event_type: 'speech',
        icon: '💬',
        actor: msg.agent_id || 'Unknown',
        detail: (msg.content || '').substring(0, 60) + ((msg.content || '').length > 60 ? '...' : ''),
        timestamp: now,
      })
    } else if (msg.type === 'participant_joined') {
      if (!participants.value.find(p => p.participant_id === msg.participant?.participant_id)) {
        participants.value.push(msg.participant)
      }
      // Step 64: Push participant join to activity stream
      roomActivityStream.value.unshift({
        id: 'stream-' + Date.now(),
        event_type: 'participant_joined',
        icon: '👤',
        actor: msg.participant?.name || msg.participant?.agent_id || 'Unknown',
        detail: `以 L${msg.participant?.level || '?'} ${msg.participant?.role || 'Member'} 身份加入`,
        timestamp: now,
      })
    } else if (msg.type === 'participant_left') {
      // Step 64: Push participant leave to activity stream
      roomActivityStream.value.unshift({
        id: 'stream-' + Date.now(),
        event_type: 'participant_left',
        icon: '👋',
        actor: msg.agent_id || 'Unknown',
        detail: '离开了讨论室',
        timestamp: now,
      })
    }
  }

  ws.onopen = () => {
    wsStatus.value = 'connected'
    wsReconnectAttempt = 0
    console.log('WS connected')
  }

  ws.onerror = (err) => {
    console.error('WS error', err)
  }

  ws.onclose = () => {
    wsStatus.value = 'disconnected'
    if (!wsCurrentRoom) return  // was intentionally closed (leaveRoom)
    // Auto-reconnect with exponential backoff
    if (wsReconnectAttempt < WS_MAX_RECONNECT) {
      const delay = Math.min(WS_BASE_DELAY * Math.pow(2, wsReconnectAttempt), WS_MAX_DELAY)
      wsReconnectAttempt++
      console.log(`WS reconnecting in ${delay}ms (attempt ${wsReconnectAttempt}/${WS_MAX_RECONNECT})`)
      const timer = setTimeout(() => {
        if (wsCurrentRoom && wsCurrentRoom === roomId) {
          connectWs(roomId)
        }
      }, delay)
      wsReconnectTimers.push(timer)
    } else {
      console.warn('WS max reconnect attempts reached')
    }
  }
}

async function sendMessage() {
  if (!newMessage.content.trim() || !currentRoom.value) return
  try {
    await addSpeech(currentRoom.value.room_id, {
      agent_id: agentInfo.agent_id,
      content: newMessage.content,
    })
    newMessage.content = ''
  } catch (e) {
    console.error('sendMessage failed', e)
  }
}

async function searchMessages() {
  if (!messageSearchQuery.value.trim() || !currentRoom.value) return
  messageSearchLoading.value = true
  messageSearchActive.value = true
  try {
    const res = await searchRoomMessages(currentRoom.value.room_id, messageSearchQuery.value)
    messageSearchResults.value = res.data?.results || []
  } catch (e) {
    console.error('searchMessages failed', e)
  } finally {
    messageSearchLoading.value = false
  }
}

function clearMessageSearch() {
  messageSearchQuery.value = ''
  messageSearchResults.value = []
  messageSearchActive.value = false
}

async function addNewParticipant() {
  if (!newParticipant.name.trim() || !currentRoom.value) return
  const id = 'agent-' + Date.now()
  try {
    const res = await addParticipant(currentRoom.value.room_id, {
      agent_id: id,
      name: newParticipant.name,
      level: newParticipant.level,
      role: newParticipant.role,
    })
    participants.value.push(res.data)
    newParticipant.name = ''
    showAddParticipant.value = false
  } catch (e) {
    console.error('addParticipant failed', e)
  }
}

async function handleCreateTask() {
  if (!newTask.title.trim() || !currentPlan.value) return
  const planId = currentPlan.value.plan_id
  const version = planDetailActiveVersion.value
  try {
    const res = await createTask(planId, version, {
      title: newTask.title,
      description: newTask.description,
      priority: newTask.priority,
      assigned_to: newTask.assigned_to || undefined,
    })
    planTasks.value.push(res.data)
    newTask.title = ''
    newTask.description = ''
    newTask.priority = 'medium'
    newTask.assigned_to = ''
    showAddTask.value = false
  } catch (e) {
    console.error('createTask failed', e)
  }
}

async function handleUpdateTaskProgress(taskId: string, progress: number) {
  if (!currentPlan.value) return
  const planId = currentPlan.value.plan_id
  const version = planDetailActiveVersion.value
  try {
    const status = progress >= 100 ? 'completed' : progress > 0 ? 'in_progress' : 'pending'
    await updateTaskProgress(planId, version, taskId, { progress, status })
    const task = planTasks.value.find(t => t.task_id === taskId)
    if (task) {
      task.progress = progress
      task.status = status
    }
  } catch (e) {
    console.error('updateTaskProgress failed', e)
  }
}

async function advancePhase(toPhase: string) {
  if (!currentRoom.value) return
  try {
    const res = await transitionPhase(currentRoom.value.room_id, toPhase)
    currentPhase.value = res.data
  } catch (e) {
    console.error('advancePhase failed', e)
  }
}

async function handleCreateDebatePoint() {
  if (!currentRoom.value || !newDebatePoint.content.trim()) return
  try {
    const res = await createDebatePoint(currentRoom.value.room_id, {
      content: newDebatePoint.content,
      point_type: newDebatePoint.point_type,
    })
    newDebatePoint.content = ''
    newDebatePoint.point_type = 'proposal'
    showAddDebatePoint.value = false
    // Refresh debate state
    const ds = await getDebateState(currentRoom.value.room_id)
    debateState.value = ds.data
  } catch (e) {
    console.error('createDebatePoint failed', e)
  }
}

async function handleSubmitDebatePosition(pointId: string, position: 'support' | 'oppose') {
  if (!currentRoom.value) return
  try {
    await submitDebatePosition(currentRoom.value.room_id, {
      point_id: pointId,
      position,
      reasoning: '',
      agent_id: agentInfo.agent_id,
    })
    // Refresh debate state
    const ds = await getDebateState(currentRoom.value.room_id)
    debateState.value = ds.data
  } catch (e) {
    console.error('submitDebatePosition failed', e)
  }
}

async function handleSubmitExchange() {
  if (!currentRoom.value || !newExchange.content.trim() || !newExchange.from_agent.trim()) return
  exchangeLoading.value = true
  try {
    await submitDebateExchange(currentRoom.value.room_id, {
      exchange_type: newExchange.exchange_type,
      from_agent: newExchange.from_agent,
      target_agent: newExchange.target_agent || undefined,
      content: newExchange.content,
    })
    newExchange.content = ''
    newExchange.from_agent = ''
    newExchange.target_agent = ''
    showAddExchange.value = false
    // Refresh debate state
    const ds = await getDebateState(currentRoom.value.room_id)
    debateState.value = ds.data
  } catch (e) {
    console.error('submitDebateExchange failed', e)
  } finally {
    exchangeLoading.value = false
  }
}

async function handleAdvanceRound() {
  if (!currentRoom.value) return
  roundAdvancing.value = true
  try {
    await advanceDebateRound(currentRoom.value.room_id)
    // Refresh debate state
    const ds = await getDebateState(currentRoom.value.room_id)
    debateState.value = ds.data
  } catch (e) {
    console.error('advanceDebateRound failed', e)
  } finally {
    roundAdvancing.value = false
  }
}

async function handleEscalateRoom() {
  if (!currentRoom.value) return
  if (!escalationForm.reason.trim()) {
    alert('请填写升级原因')
    return
  }
  if (escalationForm.to_level <= escalationForm.from_level) {
    alert('目标层级必须高于当前层级')
    return
  }
  escalationLoading.value = true
  try {
    await escalateRoom(currentRoom.value.room_id, {
      from_level: escalationForm.from_level,
      to_level: escalationForm.to_level,
      mode: escalationForm.mode,
      content: {
        escalated_by: currentUser.name,
        reason: escalationForm.reason,
      },
      notes: escalationForm.notes,
    })
    showEscalationModal.value = false
    escalationForm.reason = ''
    escalationForm.notes = ''
    escalationForm.mode = 'level_by_level'
    escalationForm.from_level = 5
    escalationForm.to_level = 6
    // Refresh notifications
    await loadNotifications()
    await loadUnreadCount()
  } catch (e) {
    console.error('escalateRoom failed', e)
    alert('升级失败：' + (e instanceof Error ? e.message : String(e)))
  } finally {
    escalationLoading.value = false
  }
}

// ─── Problem Management ──────────────────────────────────────────
async function loadProblemState(roomId: string, planId?: string) {
  if (!planId) return
  try {
    const problemsRes = await getProblems(planId)
    const problems = problemsRes.data?.problems || []
    // Find the most recent problem for this room
    const roomProblem = problems.find((p: any) => p.room_id === roomId && problemStates.includes(getProblemPhaseFromStatus(p.status)))
    if (roomProblem) {
      currentProblem.value = roomProblem
      // Load analysis if in ANALYSIS or later
      if (['analyzed', 'discussion', 'plan_update', 'resuming'].includes(roomProblem.status)) {
        try {
          const analysisRes = await api.get(`/problems/${roomProblem.issue_id}/analysis`)
          problemAnalysis.value = analysisRes.data
        } catch {
          problemAnalysis.value = null
        }
      }
      // Load discussion if in DISCUSSION or later
      if (['discussion', 'plan_update', 'resuming'].includes(roomProblem.status)) {
        try {
          const discussRes = await api.get(`/problems/${roomProblem.issue_id}/discussion`)
          problemDiscussion.value = discussRes.data
        } catch {
          problemDiscussion.value = null
        }
      }
    } else {
      currentProblem.value = null
      problemAnalysis.value = null
      problemDiscussion.value = null
    }
  } catch (e) {
    console.error('loadProblemState failed', e)
    currentProblem.value = null
  }
}

function getProblemPhaseFromStatus(status: string): string {
  const map: Record<string, string> = {
    detected: 'PROBLEM_DETECTED',
    analyzed: 'PROBLEM_ANALYSIS',
    discussion: 'PROBLEM_DISCUSSION',
    plan_update: 'PLAN_UPDATE',
    resuming: 'RESUMING',
  }
  return map[status] || status
}

async function loadHierarchicalReviewData(roomId: string) {
  try {
    // Fetch room context at L7 level (strategic overview)
    const ctx = await api.get(`/rooms/${roomId}/context`, { params: { level: 7 } })
    hierarchicalReviewData.value = ctx.data || null
  } catch (e) {
    console.error('loadHierarchicalReviewData failed', e)
    hierarchicalReviewData.value = null
  }
}

async function handleReportProblem() {
  if (!currentRoom.value || !currentPlan.value) return
  if (!reportProblemForm.title.trim()) {
    alert('请填写问题标题')
    return
  }
  reportProblemLoading.value = true
  try {
    await api.post('/problems/report', {
      plan_id: currentPlan.value.plan_id,
      room_id: currentRoom.value.room_id,
      type: reportProblemForm.type,
      title: reportProblemForm.title,
      description: reportProblemForm.description,
      severity: reportProblemForm.severity,
      detected_by: currentUser.name,
      affected_tasks: reportProblemForm.affected_tasks,
      progress_delay: reportProblemForm.progress_delay,
      related_context: reportProblemForm.related_context,
    })
    showReportProblem.value = false
    reportProblemForm.type = 'execution_blocker'
    reportProblemForm.title = ''
    reportProblemForm.description = ''
    reportProblemForm.severity = 'medium'
    reportProblemForm.affected_tasks = []
    reportProblemForm.progress_delay = ''
    reportProblemForm.related_context = ''
    // Reload phase and problem state
    const phaseRes = await getPhase(currentRoom.value.room_id)
    currentPhase.value = phaseRes.data
    await loadProblemState(currentRoom.value.room_id, currentPlan.value.plan_id)
    await loadNotifications()
  } catch (e) {
    console.error('reportProblem failed', e)
    alert('报告问题失败：' + (e instanceof Error ? e.message : String(e)))
  } finally {
    reportProblemLoading.value = false
  }
}

async function handleAnalyzeProblem() {
  if (!currentProblem.value || !currentRoom.value) return
  if (!analyzeForm.root_cause.trim()) {
    alert('请填写根因分析')
    return
  }
  problemActionLoading.value = true
  try {
    await analyzeProblem(currentProblem.value.issue_id, {
      root_cause: analyzeForm.root_cause,
      root_cause_confidence: analyzeForm.root_cause_confidence,
      impact_scope: analyzeForm.impact_scope,
      affected_tasks: analyzeForm.affected_tasks,
      progress_impact: analyzeForm.progress_impact,
      severity_reassessment: analyzeForm.severity_reassessment,
      solution_options: analyzeForm.solution_options,
      recommended_option: analyzeForm.recommended_option,
      requires_discussion: analyzeForm.requires_discussion,
      discussion_needed_aspects: analyzeForm.discussion_needed_aspects,
    })
    // Reset form
    analyzeForm.root_cause = ''
    analyzeForm.root_cause_confidence = 0.8
    analyzeForm.impact_scope = ''
    analyzeForm.affected_tasks = []
    analyzeForm.progress_impact = ''
    analyzeForm.severity_reassessment = ''
    analyzeForm.solution_options = []
    analyzeForm.recommended_option = 0
    analyzeForm.requires_discussion = false
    analyzeForm.discussion_needed_aspects = []
    // Refresh
    const phaseRes = await getPhase(currentRoom.value.room_id)
    currentPhase.value = phaseRes.data
    await loadProblemState(currentRoom.value.room_id, currentPlan.value?.plan_id)
  } catch (e) {
    console.error('analyzeProblem failed', e)
    alert('分析问题失败：' + (e instanceof Error ? e.message : String(e)))
  } finally {
    problemActionLoading.value = false
  }
}

async function handleDiscussProblem() {
  if (!currentProblem.value || !currentRoom.value) return
  problemActionLoading.value = true
  try {
    await discussProblem(currentProblem.value.issue_id, {
      participants: discussForm.participants,
      discussion_focus: discussForm.discussion_focus,
      proposed_solutions: discussForm.proposed_solutions,
      votes: discussForm.votes,
    })
    // Reset
    discussForm.participants = []
    discussForm.discussion_focus = []
    discussForm.proposed_solutions = []
    discussForm.votes = {}
    // Refresh
    const phaseRes = await getPhase(currentRoom.value.room_id)
    currentPhase.value = phaseRes.data
    await loadProblemState(currentRoom.value.room_id, currentPlan.value?.plan_id)
  } catch (e) {
    console.error('discussProblem failed', e)
    alert('讨论问题失败：' + (e instanceof Error ? e.message : String(e)))
  } finally {
    problemActionLoading.value = false
  }
}

async function handleUpdatePlan() {
  if (!currentProblem.value || !currentPlan.value) return
  if (!planUpdateForm.new_version.trim()) {
    alert('请填写新版本号')
    return
  }
  problemActionLoading.value = true
  try {
    await updatePlan(currentPlan.value.plan_id, {
      new_version: planUpdateForm.new_version,
      parent_version: planUpdateForm.parent_version || currentPlan.value.current_version,
      update_type: planUpdateForm.update_type,
      description: planUpdateForm.description,
      changes: planUpdateForm.changes,
      task_updates: planUpdateForm.task_updates,
    })
    planUpdateForm.new_version = ''
    planUpdateForm.parent_version = ''
    planUpdateForm.description = ''
    planUpdateForm.changes = {}
    planUpdateForm.task_updates = []
    // Refresh
    const phaseRes = await getPhase(currentRoom.value.room_id)
    currentPhase.value = phaseRes.data
    await loadProblemState(currentRoom.value.room_id, currentPlan.value?.plan_id)
    await openPlanDetail(currentPlan.value.plan_id)
  } catch (e) {
    console.error('updatePlan failed', e)
    alert('更新计划失败：' + (e instanceof Error ? e.message : String(e)))
  } finally {
    problemActionLoading.value = false
  }
}

async function handleResumeExecution() {
  if (!currentProblem.value || !currentPlan.value) return
  if (!resumingForm.new_version.trim()) {
    alert('请填写新版本号')
    return
  }
  problemActionLoading.value = true
  try {
    await resumeExecution(currentPlan.value.plan_id, {
      new_version: resumingForm.new_version,
      resuming_from_task: resumingForm.resuming_from_task,
      checkpoint: resumingForm.checkpoint,
      resume_instructions: resumingForm.resume_instructions,
    })
    resumingForm.new_version = ''
    resumingForm.resuming_from_task = 0
    resumingForm.checkpoint = ''
    resumingForm.resume_instructions = {}
    // Refresh
    const phaseRes = await getPhase(currentRoom.value.room_id)
    currentPhase.value = phaseRes.data
    await loadProblemState(currentRoom.value.room_id, currentPlan.value?.plan_id)
  } catch (e) {
    console.error('resumeExecution failed', e)
    alert('恢复执行失败：' + (e instanceof Error ? e.message : String(e)))
  } finally {
    problemActionLoading.value = false
  }
}

// ─── Lifecycle ──────────────────────────────────────────
onMounted(() => {
  loadPlans()
  loadDashboardStats()
  loadUnreadCount()
  homePollInterval = setInterval(loadPlans, 10000)
  document.addEventListener('click', closeNotifications)
})
onUnmounted(() => {
  if (ws) ws.close()
  if (phasePollInterval) clearInterval(phasePollInterval)
  if (homePollInterval) clearInterval(homePollInterval)
  document.removeEventListener('click', closeNotifications)
})
</script>

<template>
  <div class="app">
    <!-- ══════════════════════════════════════════════════════ -->
    <!-- HOME / PLAN DASHBOARD                                 -->
    <!-- ══════════════════════════════════════════════════════ -->
    <div v-if="view === 'home'" class="home">
      <!-- Header -->
      <header class="app-header">
        <div class="logo">
          <span class="logo-icon">⚡</span>
          <span class="logo-text">Agora</span>
          <span class="logo-version">v2</span>
        </div>
        <div class="header-actions">
          <button class="btn-primary" @click="showCreatePlan = !showCreatePlan">
            {{ showCreatePlan ? '取消' : '+ 新计划' }}
          </button>
          <button class="btn-secondary" @click="openPlanTemplates" title="从计划模板创建">
            📋 计划模板
          </button>
          <!-- Notification Bell -->
          <button class="notification-bell" @click.stop="toggleNotifications" title="通知">
            🔔
            <span v-if="unreadCount > 0" class="notification-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
          </button>
        </div>
      </header>

      <!-- Create Plan Form -->
      <div v-if="showCreatePlan" class="create-panel">
        <div class="create-inner">
          <input
            v-model="newPlanForm.topic"
            class="input"
            placeholder="计划主题 / 决策问题"
            @keyup.enter="handleCreatePlan"
            autofocus
          />
          <input
            v-model="newPlanForm.title"
            class="input"
            placeholder="标题（可选）"
            @keyup.enter="handleCreatePlan"
          />
          <button class="btn-primary" @click="handleCreatePlan">创建计划 →</button>
        </div>
      </div>

      <!-- Search & Controls -->
      <div class="search-bar">
        <input
          v-model="searchQuery"
          class="input search-input"
          placeholder="🔍 搜索计划..."
        />
        <div class="sort-controls">
          <button
            class="sort-btn"
            :class="{ active: sortBy === 'recent' }"
            @click="sortBy = 'recent'"
          >最新</button>
          <button
            class="sort-btn"
            :class="{ active: sortBy === 'name' }"
            @click="sortBy = 'name'"
          >名称</button>
        </div>
        <span class="plan-count">{{ filteredPlans.length }} 个计划</span>
      </div>

      <!-- Dashboard Stats Bar -->
      <div v-if="dashboardStats" class="dashboard-stats-bar">
        <div class="stat-card">
          <div class="stat-value">{{ dashboardStats.total_plans || 0 }}</div>
          <div class="stat-label">总计划</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ dashboardStats.active_plans || 0 }}</div>
          <div class="stat-label">进行中</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ dashboardStats.total_rooms || 0 }}</div>
          <div class="stat-label">总房间</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ dashboardStats.pending_approvals || 0 }}</div>
          <div class="stat-label">待审批</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ dashboardStats.pending_action_items || 0 }}</div>
          <div class="stat-label">待处理</div>
        </div>
        <div v-if="dashboardStats.rooms_by_phase" class="stat-card stat-card-wide">
          <div class="stat-label" style="margin-bottom:4px">房间阶段</div>
          <div class="phase-bars">
            <div v-for="(count, phase) in dashboardStats.rooms_by_phase" :key="phase" class="phase-bar-item">
              <span class="phase-bar-label">{{ phaseLabel[phase] || phase }}</span>
              <span class="phase-bar-count">{{ count }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Plan Grid -->
      <div class="plans-grid">
        <div
          v-for="plan in filteredPlans"
          :key="plan.plan_id"
          class="plan-card"
          @click="openPlanDetail(plan.plan_id)"
        >
          <div class="plan-card-header">
            <span class="plan-number">{{ plan.plan_number }}</span>
            <span class="version-badge">v{{ plan.current_version || plan.version || '1.0' }}</span>
          </div>
          <div class="plan-card-title">{{ plan.title || plan.topic || '未命名计划' }}</div>
          <div class="plan-card-topic">{{ plan.topic }}</div>
          <!-- Mini metrics -->
          <div class="plan-card-metrics">
            <span class="metric-chip">📋 {{ plan.room_count || plan.rooms?.length || 0 }} 房间</span>
            <span class="metric-chip">🗂️ {{ plan.versions?.length || 1 }} 版本</span>
          </div>
          <div class="plan-card-footer">
            <span class="meta-item">{{ new Date(plan.created_at).toLocaleDateString('zh-CN') }}</span>
            <span class="meta-item">{{ plan.current_version || plan.version || 'v1.0' }}</span>
            <button
              class="btn-copy-plan"
              title="复制计划"
              @click.stop="handleCopyPlan(plan.plan_id)"
            >📋 复制</button>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="filteredPlans.length === 0" class="empty-state">
          <div class="empty-icon">🏛️</div>
          <div class="empty-text">暂无计划</div>
          <div class="empty-sub">点击上方「+ 新计划」创建第一个讨论计划</div>
        </div>
      </div>
    </div>

    <!-- Notification Panel -->
    <div v-if="showNotifications" class="notification-panel">
      <div class="notification-panel-header">
        <span class="notification-panel-title">通知</span>
        <div class="notification-panel-actions">
          <button v-if="unreadCount > 0" class="notification-action-btn" @click="handleMarkAllRead">全部已读</button>
          <button class="notification-close-btn" @click="showNotifications = false">✕</button>
        </div>
      </div>
      <div class="notification-list">
        <div v-if="notifications.length === 0" class="notification-empty">
          <div class="notification-empty-icon">🔔</div>
          <div class="notification-empty-text">暂无通知</div>
        </div>
        <div
          v-for="n in notifications"
          :key="n.notification_id"
          class="notification-item"
          :class="{ unread: !n.read }"
        >
          <div class="notification-item-header">
            <span
              class="notification-type-badge"
              :style="{ backgroundColor: notificationTypeColor[n.type] || '#6b7280' }"
            >
              {{ notificationTypeLabel[n.type] || n.type }}
            </span>
            <button class="notification-delete-btn" @click.stop="handleDeleteNotification(n.notification_id)" title="删除">✕</button>
          </div>
          <div class="notification-item-title">{{ n.title }}</div>
          <div v-if="n.message" class="notification-item-message">{{ n.message }}</div>
          <div class="notification-item-footer">
            <span class="notification-time">{{ new Date(n.created_at).toLocaleString('zh-CN') }}</span>
            <button
              v-if="!n.read"
              class="notification-mark-read-btn"
              @click.stop="handleMarkRead(n.notification_id)"
            >✓ 已读</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════ -->
    <!-- PLAN DETAIL VIEW                                      -->
    <!-- ══════════════════════════════════════════════════════ -->
    <div v-else-if="view === 'plan_detail'" class="plan-detail">
      <!-- Header -->
      <header class="app-header">
        <button class="btn-back" @click="backToHome">
          ← 全部计划
        </button>
        <div class="plan-header-info">
          <span class="plan-header-title">{{ currentPlan?.title || currentPlan?.topic || '计划详情' }}</span>
          <span class="plan-number">{{ currentPlan?.plan_number }}</span>
        </div>
        <button class="btn-primary" @click="showCreateRoom = !showCreateRoom">
          {{ showCreateRoom ? '取消' : '+ 新房间' }}
        </button>
        <button class="btn-secondary" @click="openRoomTemplates" title="从模板创建房间">
          📋 模板
        </button>
        <!-- Export Buttons -->
        <button class="btn-secondary" :disabled="exportLoading" @click="handleExportPlan" title="导出计划 Markdown">
          📥 计划
        </button>
        <button class="btn-secondary" :disabled="exportLoading" @click="handleExportVersion" title="导出版本 Markdown">
          📄 版本
        </button>
        <!-- Notification Bell -->
        <button class="notification-bell" @click.stop="toggleNotifications" title="通知">
          🔔
          <span v-if="unreadCount > 0" class="notification-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
        </button>
      </header>

      <!-- Create Room Form -->
      <div v-if="showCreateRoom" class="create-panel">
        <div class="create-inner">
          <input
            v-model="newRoomForm.topic"
            class="input"
            placeholder="房间话题"
            @keyup.enter="handleCreateRoom"
            autofocus
          />
          <input
            v-model="newRoomForm.title"
            class="input"
            placeholder="标题（可选）"
            @keyup.enter="handleCreateRoom"
          />
          <div class="mode-select-row">
            <label class="mode-label">模式：</label>
            <select v-model="newRoomForm.mode" class="input mode-select">
              <option value="hierarchical">层级模式</option>
              <option value="flat">扁平模式</option>
            </select>
          </div>
          <button class="btn-primary" @click="handleCreateRoom">创建房间 →</button>
        </div>
      </div>

      <!-- Plan Tabs -->
      <div class="plan-tabs">
        <button
          v-for="tab in ['overview', 'rooms', 'tasks', 'decisions', 'edicts', 'approvals', 'versions', 'risks', 'constraints', 'stakeholders', 'requirements', 'participants', 'activities', 'analytics', 'snapshots', 'escalations', 'action_items', 'meeting_minutes']"
          :key="tab"
          class="plan-tab"
          :class="{ active: activePlanTab === tab }"
          @click="activePlanTab = tab as any"
        >
          {{ tab === 'overview' ? '概览' : tab === 'rooms' ? '房间' : tab === 'tasks' ? '任务' : tab === 'decisions' ? '决策' : tab === 'edicts' ? '圣旨' : tab === 'approvals' ? '审批' : tab === 'versions' ? '版本' : tab === 'risks' ? '风险' : tab === 'constraints' ? '约束' : tab === 'stakeholders' ? '干系人' : tab === 'requirements' ? '需求' : tab === 'participants' ? '参与者' : tab === 'activities' ? '活动' : tab === 'analytics' ? '分析' : tab === 'snapshots' ? '快照' : tab === 'escalations' ? '升级' : tab === 'action_items' ? '行动' : '纪要' }}
        </button>
      </div>

      <!-- Overview Tab -->
      <div v-if="activePlanTab === 'overview'" class="plan-content">
        <div class="overview-grid">
          <!-- Plan Info -->
          <div class="overview-card">
            <div class="overview-card-title">计划信息</div>
            <div class="info-row">
              <span class="info-label">计划号</span>
              <span class="info-value">{{ currentPlan?.plan_number }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">主题</span>
              <span class="info-value">{{ currentPlan?.topic }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">当前版本</span>
              <span class="info-value">{{ planDetailActiveVersion }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">创建时间</span>
              <span class="info-value">{{ new Date(currentPlan?.created_at || '').toLocaleDateString('zh-CN') }}</span>
            </div>
          </div>

          <!-- Metrics -->
          <div class="overview-card">
            <div class="overview-card-title">统计概览</div>
            <div class="metrics-row">
              <div class="metric-box">
                <div class="metric-val">{{ planMetrics?.total_tasks || planTasks.length || 0 }}</div>
                <div class="metric-key">任务总数</div>
              </div>
              <div class="metric-box">
                <div class="metric-val completed">{{ planMetrics?.completed_tasks || 0 }}</div>
                <div class="metric-key">已完成</div>
              </div>
              <div class="metric-box">
                <div class="metric-val rate">{{ planMetrics?.completion_rate || 0 }}%</div>
                <div class="metric-key">完成率</div>
              </div>
              <div class="metric-box">
                <div class="metric-val">{{ planRooms.length }}</div>
                <div class="metric-key">讨论室</div>
              </div>
            </div>
          </div>

          <!-- Rooms Summary -->
          <div class="overview-card rooms-summary">
            <div class="overview-card-title">讨论室 ({{ planRooms.length }})</div>
            <div v-if="planRooms.length === 0" class="sidebar-empty">暂无讨论室</div>
            <div
              v-for="room in planRooms.slice(0, 5)"
              :key="room.room_id"
              class="room-mini-row"
              @click="enterRoom(room.room_id)"
            >
              <span
                class="phase-pill small"
                :style="{ background: phaseColors[room.phase] || '#6b7280' }"
              >{{ phaseLabel[room.phase] || room.phase }}</span>
              <span class="room-mini-topic">{{ room.topic || room.title || '讨论室' }}</span>
              <span class="room-mini-num">{{ room.room_number }}</span>
            </div>
            <div v-if="planRooms.length > 5" class="see-more" @click="activePlanTab = 'rooms'">
              查看全部 {{ planRooms.length }} 个房间 →
            </div>
          </div>

          <!-- Tasks Summary -->
          <div class="overview-card tasks-summary">
            <div class="overview-card-title">任务 ({{ planTasks.length }})</div>
            <div v-if="planTasks.length === 0" class="sidebar-empty">暂无任务</div>
            <div
              v-for="task in planTasks.slice(0, 5)"
              :key="task.task_id"
              class="task-mini-row"
            >
              <span class="task-mini-title">{{ task.title }}</span>
              <span class="task-mini-progress">{{ task.progress || 0 }}%</span>
            </div>
            <div v-if="planTasks.length > 5" class="see-more" @click="activePlanTab = 'tasks'">
              查看全部 {{ planTasks.length }} 个任务 →
            </div>
          </div>
        </div>
      </div>

      <!-- Rooms Tab -->
      <div v-else-if="activePlanTab === 'rooms'" class="plan-content">
        <div class="rooms-grid">
          <div
            v-for="room in planRooms"
            :key="room.room_id"
            class="plan-room-card"
            @click="enterRoom(room.room_id)"
          >
            <div class="plan-room-header">
              <span
                class="phase-pill"
                :style="{ background: phaseColors[room.phase] || '#6b7280' }"
              >{{ phaseLabel[room.phase] || room.phase }}</span>
              <span class="room-number">{{ room.room_number }}</span>
            </div>
            <div class="plan-room-topic">{{ room.topic || room.title || '讨论室' }}</div>
            <div class="plan-room-meta">
              <span>👥 {{ room.participant_count || 0 }}</span>
              <span>{{ new Date(room.created_at).toLocaleDateString('zh-CN') }}</span>
            </div>
            <!-- Room Tags -->
            <div v-if="room.tags?.length" class="room-tags-row">
              <span v-for="tag in room.tags.slice(0, 3)" :key="tag" class="room-tag">{{ tag }}</span>
              <span v-if="room.tags.length > 3" class="room-tag more">+{{ room.tags.length - 3 }}</span>
            </div>
            <!-- Hierarchy indicators -->
            <div class="room-hierarchy-indicators" @click.stop>
              <span
                v-if="room.parent_room_id"
                class="hierarchy-badge parent"
                title="子房间"
              >↑ 父</span>
              <span
                v-if="room.child_rooms?.length"
                class="hierarchy-badge child"
                title="子房间"
              >↓ {{ room.child_rooms.length }}子</span>
              <span
                v-if="room.related_rooms?.length"
                class="hierarchy-badge related"
                title="关联房间"
              >↔ {{ room.related_rooms.length }}关</span>
              <button
                class="hierarchy-btn"
                title="层级管理"
                @click="openRoomHierarchy(room, $event)"
              >🔗</button>
            </div>
          </div>

          <div v-if="planRooms.length === 0" class="empty-state" style="grid-column: 1/-1">
            <div class="empty-icon">🚪</div>
            <div class="empty-text">暂无讨论室</div>
            <div class="empty-sub">点击上方「+ 新房间」创建第一个讨论室</div>
          </div>
        </div>
      </div>

      <!-- Room Hierarchy Modal -->
      <div v-if="showRoomHierarchy" class="modal-overlay" @click.self="showRoomHierarchy = false">
        <div class="modal-content room-hierarchy-modal">
          <div class="modal-header">
            <h3>🔗 讨论室层级管理</h3>
            <button class="modal-close" @click="showRoomHierarchy = false">✕</button>
          </div>
          <div class="modal-body">
            <div class="hierarchy-room-info">
              <span class="phase-pill small" :style="{ background: phaseColors[selectedRoomForHierarchy?.phase] || '#6b7280' }">
                {{ phaseLabel[selectedRoomForHierarchy?.phase] || selectedRoomForHierarchy?.phase || '' }}
              </span>
              <span class="hierarchy-room-topic">{{ selectedRoomForHierarchy?.topic || selectedRoomForHierarchy?.title || '' }}</span>
              <span class="hierarchy-room-num">{{ selectedRoomForHierarchy?.room_number || '' }}</span>
            </div>

            <!-- Tabs -->
            <div class="hierarchy-tabs">
              <button :class="{ active: hierarchyActiveTab === 'view' }" @click="hierarchyActiveTab = 'view'">层级视图</button>
              <button :class="{ active: hierarchyActiveTab === 'link' }" @click="hierarchyActiveTab = 'link'">链接房间</button>
              <button :class="{ active: hierarchyActiveTab === 'conclude' }" @click="hierarchyActiveTab = 'conclude'">结束房间</button>
            </div>

            <!-- View Tab -->
            <div v-if="hierarchyActiveTab === 'view'" class="hierarchy-view-tab">
              <div v-if="hierarchyLoading" class="loading-state">加载中...</div>
              <template v-else-if="roomHierarchyData">
                <div class="hierarchy-section">
                  <div class="hierarchy-section-title">上级房间</div>
                  <div v-if="roomHierarchyData.parent" class="hierarchy-item parent-item" @click="enterRoom(roomHierarchyData.parent.room_id); showRoomHierarchy = false">
                    <span class="hierarchy-icon">↑</span>
                    <span class="hierarchy-item-topic">{{ roomHierarchyData.parent.topic }}</span>
                    <span class="hierarchy-item-phase">{{ phaseLabel[roomHierarchyData.parent.phase] || roomHierarchyData.parent.phase }}</span>
                  </div>
                  <div v-else class="hierarchy-empty">无上级房间</div>
                </div>
                <div class="hierarchy-section">
                  <div class="hierarchy-section-title">子房间 ({{ roomHierarchyData.children?.length || 0 }})</div>
                  <div v-if="roomHierarchyData.children?.length" class="hierarchy-items-list">
                    <div v-for="child in roomHierarchyData.children" :key="child.room_id" class="hierarchy-item child-item" @click="enterRoom(child.room_id); showRoomHierarchy = false">
                      <span class="hierarchy-icon">↓</span>
                      <span class="hierarchy-item-topic">{{ child.topic }}</span>
                      <span class="hierarchy-item-phase">{{ phaseLabel[child.phase] || child.phase }}</span>
                    </div>
                  </div>
                  <div v-else class="hierarchy-empty">无子房间</div>
                </div>
                <div class="hierarchy-section">
                  <div class="hierarchy-section-title">关联房间 ({{ roomHierarchyData.related?.length || 0 }})</div>
                  <div v-if="roomHierarchyData.related?.length" class="hierarchy-items-list">
                    <div v-for="rel in roomHierarchyData.related" :key="rel.room_id" class="hierarchy-item related-item" @click="enterRoom(rel.room_id); showRoomHierarchy = false">
                      <span class="hierarchy-icon">↔</span>
                      <span class="hierarchy-item-topic">{{ rel.topic }}</span>
                      <span class="hierarchy-item-phase">{{ phaseLabel[rel.phase] || rel.phase }}</span>
                    </div>
                  </div>
                  <div v-else class="hierarchy-empty">无关联房间</div>
                </div>
              </template>
            </div>

            <!-- Link Tab -->
            <div v-if="hierarchyActiveTab === 'link'" class="hierarchy-link-tab">
              <div class="form-group">
                <label>上级房间</label>
                <select v-model="hierarchyLinkForm.parent_room_id" class="input">
                  <option value="">无（顶级房间）</option>
                  <option v-for="r in planRooms.filter(r => r.room_id !== selectedRoomForHierarchy?.room_id)" :key="r.room_id" :value="r.room_id">
                    {{ r.topic || r.title }} ({{ r.room_number }})
                  </option>
                </select>
              </div>
              <div class="form-group">
                <label>子房间（多选）</label>
                <div class="checkbox-group">
                  <label v-for="r in planRooms.filter(r => r.room_id !== selectedRoomForHierarchy?.room_id)" :key="r.room_id" class="checkbox-item">
                    <input type="checkbox" :value="r.room_id" v-model="hierarchyLinkForm.child_rooms" />
                    {{ r.topic || r.title }} ({{ r.room_number }})
                  </label>
                </div>
              </div>
              <div class="form-group">
                <label>关联房间（多选）</label>
                <div class="checkbox-group">
                  <label v-for="r in planRooms.filter(r => r.room_id !== selectedRoomForHierarchy?.room_id)" :key="r.room_id" class="checkbox-item">
                    <input type="checkbox" :value="r.room_id" v-model="hierarchyLinkForm.related_rooms" />
                    {{ r.topic || r.title }} ({{ r.room_number }})
                  </label>
                </div>
              </div>
              <div class="modal-actions">
                <button class="btn-primary" :disabled="hierarchyActionLoading" @click="handleLinkRoom">
                  {{ hierarchyActionLoading ? '保存中...' : '保存链接' }}
                </button>
              </div>
            </div>

            <!-- Conclude Tab -->
            <div v-if="hierarchyActiveTab === 'conclude'" class="hierarchy-conclude-tab">
              <div class="form-group">
                <label>会议总结</label>
                <textarea v-model="hierarchyConcludeForm.summary" class="input" rows="4" placeholder="描述本次讨论的主要结论..."></textarea>
              </div>
              <div class="form-group">
                <label>结论</label>
                <textarea v-model="hierarchyConcludeForm.conclusion" class="input" rows="3" placeholder="最终决策或下一步行动..."></textarea>
              </div>
              <div class="modal-actions">
                <button class="btn-danger" :disabled="hierarchyActionLoading" @click="handleConcludeRoom">
                  {{ hierarchyActionLoading ? '结束中...' : '确认结束房间' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Room Tags Modal -->
      <div v-if="showRoomTagsModal" class="modal-overlay" @click.self="showRoomTagsModal = false">
        <div class="modal-content room-tags-modal">
          <div class="modal-header">
            <h3>🏷️ 讨论室标签</h3>
            <button class="modal-close" @click="showRoomTagsModal = false">✕</button>
          </div>
          <div class="modal-body">
            <div class="room-tags-room-info">
              <span class="phase-pill small" :style="{ background: phaseColors[currentRoom?.phase] || '#6b7280' }">
                {{ phaseLabel[currentRoom?.phase] || currentRoom?.phase || '' }}
              </span>
              <span class="room-tags-topic">{{ currentRoom?.topic || currentRoom?.title || '' }}</span>
              <span class="room-tags-num">{{ currentRoom?.room_number || '' }}</span>
            </div>

            <!-- Current Tags -->
            <div class="room-tags-section">
              <div class="room-tags-section-title">当前标签</div>
              <div v-if="currentRoom?.tags?.length" class="room-tags-list">
                <span v-for="tag in currentRoom.tags" :key="tag" class="room-tag-item">
                  {{ tag }}
                  <button class="tag-remove-btn" @click="handleRemoveRoomTag(tag)" :disabled="roomTagsLoading">×</button>
                </span>
              </div>
              <div v-else class="room-tags-empty">暂无标签</div>
            </div>

            <!-- Add Tag -->
            <div class="room-tags-section">
              <div class="room-tags-section-title">添加标签</div>
              <div class="room-tags-add-form">
                <input
                  v-model="roomTagsForm.newTag"
                  class="input"
                  placeholder="输入标签名称"
                  @keyup.enter="handleAddRoomTag"
                />
                <button class="btn-primary" @click="handleAddRoomTag" :disabled="roomTagsLoading || !roomTagsForm.newTag.trim()">
                  添加
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Escalation Modal -->
      <div v-if="showEscalationModal" class="modal-overlay" @click.self="showEscalationModal = false">
        <div class="modal-content escalation-modal">
          <div class="modal-header">
            <h3>🔺 升级讨论</h3>
            <button class="modal-close" @click="showEscalationModal = false">✕</button>
          </div>
          <div class="escalation-form">
            <div class="form-group">
              <label>当前层级</label>
              <select v-model.number="escalationForm.from_level" class="input">
                <option :value="1">L1 - 任务层</option>
                <option :value="2">L2 - 岗位层</option>
                <option :value="3">L3 - 班组层</option>
                <option :value="4">L4 - 团队层</option>
                <option :value="5">L5 - 部门层</option>
                <option :value="6">L6 - 事业部层</option>
              </select>
            </div>
            <div class="form-group">
              <label>目标层级</label>
              <select v-model.number="escalationForm.to_level" class="input">
                <option :value="2">L2 - 岗位层</option>
                <option :value="3">L3 - 班组层</option>
                <option :value="4">L4 - 团队层</option>
                <option :value="5">L5 - 部门层</option>
                <option :value="6">L6 - 事业部层</option>
                <option :value="7">L7 - 战略层</option>
              </select>
            </div>
            <div class="form-group">
              <label>升级模式</label>
              <select v-model="escalationForm.mode" class="input">
                <option value="level_by_level">逐级汇报 (L1→L2→L3→...)</option>
                <option value="cross_level">跨级汇报 (L1→L3→L5→L7)</option>
                <option value="emergency">紧急汇报 (L1→L5→L7)</option>
              </select>
            </div>
            <div class="form-group">
              <label>升级原因 <span class="required">*</span></label>
              <textarea v-model="escalationForm.reason" class="input" rows="3" placeholder="请描述升级的原因和需要高层级决策的问题..."></textarea>
            </div>
            <div class="form-group">
              <label>补充说明（可选）</label>
              <textarea v-model="escalationForm.notes" class="input" rows="2" placeholder="额外备注信息..."></textarea>
            </div>
            <div class="escalation-path-preview" v-if="escalationForm.from_level && escalationForm.to_level && escalationForm.to_level > escalationForm.from_level">
              <span class="path-label">升级路径：</span>
              <span v-if="escalationPathLoading" class="path-loading">计算中...</span>
              <span v-else-if="escalationPathPreview" class="path-steps">
                {{ escalationPathPreview.path_description || escalationPathPreview.escalation_path?.join(' → ') || '' }}
              </span>
              <span v-else class="path-steps">
                <template v-if="escalationForm.mode === 'level_by_level'">
                  {{ Array.from({length: escalationForm.to_level - escalationForm.from_level + 1}, (_, i) => 'L' + (escalationForm.from_level + i)).join(' → ') }}
                </template>
                <template v-else-if="escalationForm.mode === 'cross_level'">
                  L{{ escalationForm.from_level }} → L{{ Math.min(escalationForm.from_level + 2, escalationForm.to_level) }} → L{{ escalationForm.to_level }}
                </template>
                <template v-else>
                  L{{ escalationForm.from_level }} → L5 → L7
                </template>
              </span>
            </div>
            <div class="modal-actions">
              <button class="btn-cancel" @click="showEscalationModal = false">取消</button>
              <button class="btn-danger" :disabled="escalationLoading" @click="handleEscalateRoom">
                {{ escalationLoading ? '升级中...' : '确认升级' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Task Dependencies Modal -->
      <div v-if="showTaskDependencies" class="modal-overlay" @click.self="showTaskDependencies = false">
        <div class="modal-content task-dependencies-modal">
          <div class="modal-header">
            <h3>🔗 任务依赖关系</h3>
            <button class="modal-close" @click="showTaskDependencies = false">✕</button>
          </div>

          <div v-if="dependencyLoading" class="loading-state">加载中...</div>
          <template v-else-if="dependencyGraph">
            <!-- Summary Bar -->
            <div class="dep-summary-bar">
              <div class="dep-stat">
                <span class="dep-stat-num">{{ dependencyGraph.total_tasks || 0 }}</span>
                <span class="dep-stat-label">总任务</span>
              </div>
              <div class="dep-stat blocked">
                <span class="dep-stat-num">{{ dependencyGraph.blocked_task_count || 0 }}</span>
                <span class="dep-stat-label">被阻塞</span>
              </div>
              <div class="dep-stat edges">
                <span class="dep-stat-num">{{ dependencyGraph.edges?.length || 0 }}</span>
                <span class="dep-stat-label">依赖边</span>
              </div>
            </div>

            <!-- Blocked Tasks Section -->
            <div v-if="dependencyGraph.blocked_task_count > 0" class="dep-section">
              <div class="dep-section-title">🚫 被阻塞的任务 ({{ blockedTasks.length }})</div>
              <div v-for="task in blockedTasks" :key="task.task_id" class="dep-blocked-task">
                <div class="dep-task-header">
                  <span class="dep-task-num">{{ task.task_number || task.task_id.slice(0,8) }}</span>
                  <span class="dep-task-title">{{ task.title }}</span>
                </div>
                <div class="dep-blocked-by">
                  <span class="dep-blocked-label">被以下阻塞：</span>
                  <span v-for="bid in task.blocked_by" :key="bid" class="dep-blocker-chip">
                    {{ getTaskTitle(bid) || bid.slice(0,8) }}
                  </span>
                </div>
              </div>
            </div>

            <!-- Dependency Graph Section -->
            <div class="dep-section">
              <div class="dep-section-title">📊 依赖关系图</div>
              <div v-if="dependencyGraph.nodes?.length === 0" class="dep-empty">暂无任务</div>
              <div v-else class="dep-graph-list">
                <div v-for="node in dependencyGraph.nodes" :key="node.task_id" class="dep-node">
                  <div class="dep-node-header">
                    <span v-if="node.is_blocked" class="dep-blocked-badge">🚫</span>
                    <span class="dep-node-num">{{ node.task_number || node.task_id.slice(0,8) }}</span>
                    <span class="dep-node-title">{{ node.title }}</span>
                    <span class="dep-node-status" :class="'s-' + node.status">{{ statusLabel[node.status] || node.status }}</span>
                  </div>
                  <div v-if="node.dependencies?.length > 0" class="dep-node-deps">
                    <span class="dep-deps-label">依赖：</span>
                    <span v-for="dep in node.dependencies" :key="dep" class="dep-dep-chip" :class="{ 'dep-missing': !getTaskTitle(dep) }">
                      {{ getTaskTitle(dep) || dep.slice(0,8) }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <div v-else class="dep-empty">加载失败，请重试</div>
        </div>
      </div>

      <!-- Tasks Tab -->
      <div v-else-if="activePlanTab === 'tasks'" class="plan-content">
        <div class="tasks-toolbar">
          <div class="version-selector">
            <span class="version-label">版本：</span>
            <select
              v-model="planDetailActiveVersion"
              class="input version-select"
              @change="switchPlanVersion(planDetailActiveVersion)"
            >
              <option v-for="v in planVersions" :key="v" :value="v">{{ v }}</option>
            </select>
          </div>
          <button class="btn-primary" @click="showAddTask = !showAddTask">
            {{ showAddTask ? '取消' : '+ 添加任务' }}
          </button>
          <button class="btn-secondary" @click="openTaskDependencies">
            🔗 依赖关系
          </button>
          <button class="btn-secondary" @click="showGanttView = !showGanttView">
            {{ showGanttView ? '📋 列表视图' : '📊 甘特图' }}
          </button>
          <button class="btn-secondary" @click="openTaskTemplates" title="任务模板">
            📝 任务模板
          </button>
        </div>

        <!-- Add Task Form -->
        <div v-if="showAddTask" class="add-task-panel">
          <input
            v-model="newTask.title"
            class="input"
            placeholder="任务标题"
            @keyup.enter="handleCreateTask"
            autofocus
          />
          <textarea
            v-model="newTask.description"
            class="input task-desc-input"
            placeholder="任务描述（可选）"
            rows="2"
          ></textarea>
          <div class="task-form-row">
            <select v-model="newTask.priority" class="input priority-select">
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
              <option value="critical">紧急</option>
            </select>
            <input
              v-model="newTask.assigned_to"
              class="input"
              placeholder="负责人（可选）"
            />
          </div>
          <button class="btn-primary" @click="handleCreateTask">创建任务</button>
        </div>

        <!-- Task Metrics -->
        <div v-if="planMetrics" class="tasks-metrics">
          <span>✅ 已完成 {{ planMetrics.tasks?.completed || 0 }} / {{ planMetrics.tasks?.total || planTasks.length || 0 }}</span>
          <span class="metric-rate">完成率 {{ ((planMetrics.tasks?.completion_rate || 0) * 100).toFixed(0) }}%</span>
        </div>

        <!-- Gantt Chart View -->
        <div v-if="showGanttView && planTasks.length > 0" class="gantt-wrapper">
          <div class="gantt-chart">
            <!-- Timeline header -->
            <div class="gantt-row gantt-header-row">
              <div class="gantt-label-col">任务</div>
              <div class="gantt-timeline-outer">
                <div class="gantt-timeline-header">
                  <span
                    v-for="day in ganttDateRange"
                    :key="day"
                    class="gantt-day-label"
                    :class="{'gantt-today': day === ganttTodayStr}"
                    :style="{ left: (ganttDateRange.indexOf(day) / (ganttDateRange.length - 1)) * 100 + '%' }"
                  >{{ day.substring(5) }}</span>
                </div>
              </div>
            </div>
            <!-- Task rows -->
            <div class="gantt-rows-area">
              <div v-for="(task, idx) in ganttTasks" :key="task.task_id" class="gantt-row gantt-data-row">
                <div class="gantt-label-col">
                  <div class="gantt-task-name" :title="task.title">{{ task.title }}</div>
                  <div class="gantt-task-meta">
                    <span class="gantt-priority-dot" :class="'gp-' + task.priority">{{ task.priority === 'critical' ? '🔴' : task.priority === 'high' ? '🟠' : task.priority === 'medium' ? '🟡' : '🟢' }}</span>
                    <span class="gantt-status-chip" :class="'gs-' + task.status">{{ task.status === 'completed' ? '✅' : task.status === 'in_progress' ? '🔄' : '⏳' }}</span>
                    <span v-if="(task.dependencies || []).length > 0" class="gantt-dep-badge" title="依赖任务">🔗{{ (task.dependencies || []).length }}</span>
                  </div>
                </div>
                <div class="gantt-timeline-outer">
                  <!-- Grid lines -->
                  <div class="gantt-grid-lines">
                    <div
                      v-for="(day, di) in ganttDateRange"
                      :key="di"
                      class="gantt-grid-line"
                      :class="{'gantt-today-col': day === ganttTodayStr}"
                    ></div>
                  </div>
                  <!-- Today indicator -->
                  <div v-if="ganttTodayOffset >= 0" class="gantt-today-vline" :style="{ left: ganttTodayOffset + '%' }"></div>
                  <!-- Task bar -->
                  <div
                    v-if="task.barLeft !== null"
                    class="gantt-bar"
                    :class="'gantt-bar-' + task.status"
                    :style="{ left: task.barLeft + '%', width: Math.max(task.barWidth, 2) + '%' }"
                    :title="task.title + ' | 进度: ' + task.progress + '%' + (task.deadline ? ' | 截止: ' + task.deadline : '')"
                    @click="openTaskDetail(task)"
                  >
                    <div
                      class="gantt-bar-fill"
                      :class="'gbf-' + task.status"
                      :style="{ width: task.progress + '%' }"
                    ></div>
                    <span v-if="task.barWidth > 6" class="gantt-bar-label">{{ task.progress }}%</span>
                  </div>
                  <!-- Dependency connector dot -->
                  <div
                    v-for="(arrow, ai) in task.depArrows"
                    :key="'dep-' + ai"
                    class="gantt-dep-connector"
                    :style="{ left: arrow.x1 + '%', top: '50%' }"
                    :title="'依赖: ' + (tasksWithId[arrow.depId]?.title || arrow.depId)"
                  ></div>
                </div>
              </div>
              <!-- SVG overlay for dependency arrows -->
              <svg class="gantt-svg-overlay" :style="{ width: '100%', height: (ganttTasks.length * 48) + 'px' }">
                <defs>
                  <marker id="gantt-arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                    <polygon points="0 0, 6 3, 0 6" fill="#60a5fa"/>
                  </marker>
                </defs>
                <line
                  v-for="(arrow, ai) in ganttAllArrows"
                  :key="'arr-' + ai"
                  :x1="arrow.x1 + '%'"
                  :y1="arrow.y1 + 'px'"
                  :x2="arrow.x2 + '%'"
                  :y2="arrow.y2 + 'px'"
                  stroke="#60a5fa"
                  stroke-width="1.5"
                  stroke-dasharray="4,2"
                  marker-end="url(#gantt-arrow)"
                />
              </svg>
            </div>
          </div>
        </div>
        <div v-else-if="showGanttView && planTasks.length === 0" class="gantt-empty">
          <div class="empty-icon">📊</div>
          <div class="empty-text">暂无任务</div>
          <div class="empty-sub">添加任务后即可在甘特图中查看时间线</div>
        </div>

        <!-- Task List -->
        <div class="tasks-list">
          <div v-if="planTasks.length === 0 && !showAddTask" class="empty-state" style="padding: 60px 0">
            <div class="empty-icon">📋</div>
            <div class="empty-text">暂无任务</div>
            <div class="empty-sub">点击上方「+ 添加任务」创建第一个任务</div>
          </div>
          <div
            v-for="task in planTasks"
            :key="task.task_id"
            class="task-card"
            @click="openTaskDetail(task)"
          >
            <div class="task-card-header">
              <div class="task-card-title">{{ task.title }}</div>
              <div class="task-card-badges">
                <span class="priority-dot" :class="'p-' + task.priority">
                  {{ task.priority === 'critical' ? '🔴' : task.priority === 'high' ? '🟠' : task.priority === 'medium' ? '🟡' : '🟢' }}
                </span>
                <span class="status-chip" :class="'s-' + task.status">
                  {{ task.status === 'completed' ? '✅ 完成' : task.status === 'in_progress' ? '🔄 进行中' : '⏳ 待处理' }}
                </span>
              </div>
            </div>
            <div v-if="task.description" class="task-card-desc">{{ task.description }}</div>
            <div class="task-progress-row">
              <div class="task-progress-bar">
                <div
                  class="task-progress-fill"
                  :style="{ width: (task.progress || 0) + '%' }"
                  :class="'fill-' + task.status"
                ></div>
              </div>
              <span class="task-progress-val">{{ task.progress || 0 }}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              :value="task.progress || 0"
              class="task-slider"
              @click.stop
              @change="(e) => handleUpdateTaskProgress(task.task_id, Number((e.target as HTMLInputElement).value))"
            />
          </div>
        </div>
      </div>

      <!-- Decisions Tab -->
      <div v-else-if="activePlanTab === 'decisions'" class="plan-content">
        <div class="decisions-toolbar">
          <div class="version-selector">
            <span class="version-label">版本：</span>
            <select
              v-model="planDetailActiveVersion"
              class="input version-select"
              @change="switchPlanVersion(planDetailActiveVersion)"
            >
              <option v-for="v in planVersions" :key="v" :value="v">v{{ v }}</option>
            </select>
          </div>
          <button class="btn-primary" @click="showAddDecision = !showAddDecision; editingDecisionId = null; cancelEditDecision()">
            {{ showAddDecision ? '取消' : '+ 创建决策' }}
          </button>
        </div>

        <!-- Add/Edit Decision Form -->
        <div v-if="showAddDecision" class="add-decision-panel">
          <div class="decision-form-header">{{ editingDecisionId ? '编辑决策' : '创建决策' }}</div>
          <input
            v-model="newDecisionForm.title"
            class="input"
            placeholder="决策标题 *"
            @keyup.enter="editingDecisionId ? handleUpdateDecision(editingDecisionId) : handleCreateDecision()"
            autofocus
          />
          <textarea
            v-model="newDecisionForm.decision_text"
            class="input decision-text-input"
            placeholder="决策内容 / 决定 *"
            rows="3"
          ></textarea>
          <textarea
            v-model="newDecisionForm.description"
            class="input decision-text-input"
            placeholder="描述（可选）"
            rows="2"
          ></textarea>
          <textarea
            v-model="newDecisionForm.rationale"
            class="input decision-text-input"
            placeholder="理由（可选）"
            rows="2"
          ></textarea>
          <textarea
            v-model="newDecisionForm.alternatives_considered"
            class="input decision-text-input"
            placeholder="考虑的替代方案（每行一个，可选）"
            rows="2"
          ></textarea>
          <div class="decision-form-row">
            <input
              v-model="newDecisionForm.agreed_by"
              class="input"
              placeholder="同意者（逗号分隔，可选）"
            />
            <input
              v-model="newDecisionForm.disagreed_by"
              class="input"
              placeholder="反对者（逗号分隔，可选）"
            />
          </div>
          <input
            v-model="newDecisionForm.decided_by"
            class="input"
            placeholder="决策人（可选）"
          />
          <div class="decision-form-actions">
            <button class="btn-primary" @click="editingDecisionId ? handleUpdateDecision(editingDecisionId) : handleCreateDecision()">
              {{ editingDecisionId ? '保存修改' : '创建决策' }}
            </button>
            <button class="btn-cancel" @click="cancelEditDecision()">取消</button>
          </div>
        </div>

        <!-- Decisions List -->
        <div v-if="planDecisions.length === 0 && !showAddDecision" class="empty-state" style="padding: 60px 0">
          <div class="empty-icon">⚖️</div>
          <div class="empty-text">暂无决策</div>
          <div class="empty-sub">点击上方「+ 创建决策」创建第一个决策记录</div>
        </div>
        <div class="decisions-list">
          <div
            v-for="decision in planDecisions"
            :key="decision.decision_id"
            class="decision-card"
          >
            <div class="decision-card-header">
              <div class="decision-card-title">{{ decision.title }}</div>
              <div class="decision-card-actions">
                <button class="btn-edit" @click="startEditDecision(decision)">编辑</button>
              </div>
            </div>
            <div class="decision-card-number">{{ decision.decision_number || '未编号' }}</div>
            <div class="decision-card-text">{{ decision.decision_text }}</div>
            <div v-if="decision.description" class="decision-card-desc">{{ decision.description }}</div>
            <div v-if="decision.rationale" class="decision-card-rationale">
              <span class="decision-label">理由：</span>{{ decision.rationale }}
            </div>
            <div v-if="decision.alternatives_considered?.length" class="decision-card-alts">
              <span class="decision-label">考虑的替代方案：</span>
              <div v-for="(alt, i) in decision.alternatives_considered" :key="i" class="alt-item">• {{ alt }}</div>
            </div>
            <div class="decision-card-footer">
              <div v-if="decision.agreed_by?.length" class="decision-party agreed">
                <span class="decision-label">✅ 同意：</span>{{ decision.agreed_by.join(', ') }}
              </div>
              <div v-if="decision.disagreed_by?.length" class="decision-party disagreed">
                <span class="decision-label">❌ 反对：</span>{{ decision.disagreed_by.join(', ') }}
              </div>
              <div v-if="decision.decided_by" class="decision-party">
                <span class="decision-label">决策人：</span>{{ decision.decided_by }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Edicts Tab (L7 圣旨) -->
      <div v-else-if="activePlanTab === 'edicts'" class="plan-content">
        <div class="edicts-toolbar">
          <div class="version-selector">
            <span class="version-label">版本：</span>
            <select
              v-model="planDetailActiveVersion"
              class="input version-select"
              @change="switchPlanVersion(planDetailActiveVersion)"
            >
              <option v-for="v in planVersions" :key="v" :value="v">v{{ v }}</option>
            </select>
          </div>
          <button class="btn-primary" @click="showAddEdict = !showAddEdict; editingEdictId = null; cancelEditEdict()">
            {{ showAddEdict ? '取消' : '+ 创建圣旨' }}
          </button>
        </div>

        <!-- Add/Edit Edict Form -->
        <div v-if="showAddEdict" class="add-edict-panel">
          <div class="edict-form-header">{{ editingEdictId ? '编辑圣旨' : '创建圣旨' }}</div>
          <input
            v-model="newEdictForm.title"
            class="input"
            placeholder="圣旨标题 *"
            @keyup.enter="editingEdictId ? handleUpdateEdict(editingEdictId) : handleCreateEdict()"
            autofocus
          />
          <textarea
            v-model="newEdictForm.content"
            class="input edict-text-input"
            placeholder="圣旨内容 *"
            rows="4"
          ></textarea>
          <div class="edict-form-row">
            <input
              v-model="newEdictForm.issued_by"
              class="input"
              placeholder="签发人（L7）"
            />
            <input
              v-model="newEdictForm.recipients"
              class="input"
              placeholder="接收层级（如 L6,L5）"
            />
          </div>
          <div class="edict-form-row">
            <input
              v-model="newEdictForm.effective_from"
              class="input"
              placeholder="生效时间（如 2026-04-04T00:00:00Z）"
            />
            <select v-model="newEdictForm.status" class="input">
              <option value="draft">草稿</option>
              <option value="published">已颁布</option>
              <option value="revoked">已撤销</option>
            </select>
          </div>
          <div class="edict-form-actions">
            <button class="btn-primary" @click="editingEdictId ? handleUpdateEdict(editingEdictId) : handleCreateEdict()">
              {{ editingEdictId ? '保存修改' : '创建圣旨' }}
            </button>
            <button class="btn-cancel" @click="cancelEditEdict()">取消</button>
          </div>
        </div>

        <!-- Edicts List -->
        <div v-if="planEdicts.length === 0 && !showAddEdict" class="empty-state" style="padding: 60px 0">
          <div class="empty-icon">📜</div>
          <div class="empty-text">暂无圣旨</div>
          <div class="empty-sub">点击上方「+ 创建圣旨」创建第一条政令</div>
        </div>
        <div class="edicts-list">
          <div
            v-for="edict in planEdicts"
            :key="edict.edict_id"
            class="edict-card"
          >
            <div class="edict-card-header">
              <div class="edict-card-title">{{ edict.title }}</div>
              <div class="edict-card-actions">
                <button class="btn-ack" @click="startAckEdict(edict.edict_id)">确认收到</button>
                <button class="btn-edit" @click="startEditEdict(edict)">编辑</button>
                <button class="btn-edit btn-delete" @click="handleDeleteEdict(edict.edict_id)">删除</button>
              </div>
            </div>
            <div class="edict-card-number">圣旨第 {{ edict.edict_number || '?' }} 号</div>
            <div class="edict-card-status" :class="'status-' + edict.status">
              {{ edict.status === 'published' ? '✅ 已颁布' : edict.status === 'draft' ? '📝 草稿' : '❌ 已撤销' }}
            </div>
            <div class="edict-card-content">{{ edict.content }}</div>
            <div v-if="edict.issued_by" class="edict-card-meta">
              <span class="edict-label">签发人：</span>{{ edict.issued_by }}
            </div>
            <div v-if="edict.recipients?.length" class="edict-card-meta">
              <span class="edict-label">接收方：</span>{{ Array.isArray(edict.recipients) ? edict.recipients.join(', ') : edict.recipients }}
            </div>
            <div v-if="edict.effective_from" class="edict-card-meta">
              <span class="edict-label">生效时间：</span>{{ edict.effective_from }}
            </div>
            <!-- 签收记录 -->
            <div v-if="edictAcknowledgments[edict.edict_id]?.length" class="edict-acks">
              <div class="edict-acks-header">
                <span class="edict-label">签收情况：</span>{{ edictAcknowledgments[edict.edict_id].length }} 人已确认
              </div>
              <div
                v-for="ack in edictAcknowledgments[edict.edict_id]"
                :key="ack.ack_id"
                class="edict-ack-row"
              >
                <span class="ack-level">L{{ ack.level }}</span>
                <span class="ack-name">{{ ack.acknowledged_by }}</span>
                <span class="ack-time">{{ ack.acknowledged_at?.slice(0, 16) }}</span>
                <button class="btn-del-ack" @click="handleDeleteAck(edict.edict_id, ack.ack_id)">×</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Approvals Tab -->
      <div v-else-if="activePlanTab === 'approvals'" class="plan-content">
        <!-- Toolbar -->
        <div class="activity-filter-bar">
          <button class="btn-primary" @click="loadApprovalFlow">
            {{ loadingApproval ? '加载中...' : '刷新审批状态' }}
          </button>
          <button v-if="!approvalFlow" class="btn-primary" @click="showStartApproval = !showStartApproval">
            {{ showStartApproval ? '取消' : '+ 启动审批流' }}
          </button>
          <span v-if="approvalFlow" class="approval-status-badge" :class="'approval-status-' + (approvalFlow.status || 'unknown')">
            {{ approvalFlow.status === 'in_progress' ? '审批中' : approvalFlow.status === 'approved' ? '已通过' : approvalFlow.status === 'rejected' ? '已驳回' : approvalFlow.status === 'pending' ? '待审批' : approvalFlow.status || '未知' }}
          </span>
        </div>

        <!-- Start Approval Form -->
        <div v-if="showStartApproval" class="start-approval-form">
          <div class="form-title">启动审批流</div>
          <div class="form-row">
            <label>发起人ID</label>
            <input v-model="startApprovalForm.initiator_id" class="input" placeholder="user-1" />
          </div>
          <div class="form-row">
            <label>发起人名称</label>
            <input v-model="startApprovalForm.initiator_name" class="input" placeholder="用户名" />
          </div>
          <div class="form-row">
            <label>跳过的层级（可选，逗号分隔）</label>
            <input v-model="skipLevelsInput" class="input" placeholder="如: 1,2,3" />
          </div>
          <button class="btn-primary" @click="handleStartApproval">确认启动</button>
        </div>

        <!-- Approval Levels Reference -->
        <div v-if="approvalLevels.length > 0" class="approval-levels-ref">
          <div class="section-title">审批层级说明</div>
          <div class="approval-levels-grid">
            <div v-for="lvl in approvalLevels" :key="lvl.level" class="approval-level-ref-card">
              <div class="approval-level-ref-header">L{{ lvl.level }} — {{ lvl.level_label }}</div>
              <div class="approval-level-ref-role">{{ lvl.reviewer_role }}</div>
            </div>
          </div>
        </div>

        <!-- Approval Flow Status -->
        <div v-if="approvalFlow" class="approval-flow-status">
          <div class="section-title">审批流状态</div>
          <div class="info-row">
            <span class="info-label">当前层级</span>
            <span class="info-value">L{{ approvalFlow.current_level }} — {{ approvalFlow.current_level_label }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">状态</span>
            <span class="info-value">{{ approvalFlow.status }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">发起人</span>
            <span class="info-value">{{ approvalFlow.initiator_name || approvalFlow.initiator_id }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">发起时间</span>
            <span class="info-value">{{ approvalFlow.started_at ? new Date(approvalFlow.started_at).toLocaleString() : '-' }}</span>
          </div>

          <!-- Approval Levels Status -->
          <div class="section-title" style="margin-top: 20px">各层级审批状态</div>
          <div class="approval-levels-list">
            <div v-for="(lvlData, lvl) in approvalFlow.levels" :key="lvl" class="approval-level-row" :class="'approval-level-' + (lvlData.status || 'pending')">
              <div class="approval-level-header">
                <div class="approval-level-badge">L{{ lvl }}</div>
                <div class="approval-level-info">
                  <span class="approval-level-label">{{ lvlData.level_label || ('L' + lvl) }}</span>
                  <span class="approval-level-reviewer">{{ lvlData.reviewer_role }}</span>
                </div>
                <div class="approval-level-status">
                  <span class="approval-status-tag" :class="'status-' + (lvlData.status || 'pending')">
                    {{ lvlData.status === 'approved' ? '✅ 通过' : lvlData.status === 'rejected' ? '❌ 驳回' : lvlData.status === 'skipped' ? '⏭️ 跳过' : lvlData.status === 'current' ? '⏳ 待审批' : '⏸️ 等待中' }}
                  </span>
                </div>
              </div>
              <div v-if="lvlData.records && lvlData.records.length > 0" class="approval-level-records">
                <div v-for="rec in lvlData.records" :key="rec.action + rec.timestamp" class="approval-record">
                  <span class="record-action">{{ rec.action === 'APPROVE' ? '✅ 同意' : rec.action === 'REJECT' ? '❌ 驳回' : rec.action === 'RETURN' ? '↩️ 退回' : rec.action === 'ESCALATE' ? '🔺 升级' : rec.action }}</span>
                  <span class="record-actor">{{ rec.actor_name || rec.actor_id }}</span>
                  <span class="record-time">{{ new Date(rec.timestamp).toLocaleString() }}</span>
                  <span v-if="rec.comment" class="record-comment">「{{ rec.comment }}」</span>
                </div>
              </div>
              <!-- Action Buttons for Current Level -->
              <div v-if="lvlData.status === 'current'" class="approval-level-actions">
                <input
                  v-model="approvalActionComment[lvl as number]"
                  class="input approval-comment-input"
                  placeholder="审批意见（可选）"
                />
                <button class="btn-approve" @click="handleApprovalAction(Number(lvl), 'APPROVE')">✅ 同意</button>
                <button class="btn-reject" @click="handleApprovalAction(Number(lvl), 'REJECT')">❌ 驳回</button>
                <button class="btn-return" @click="handleApprovalAction(Number(lvl), 'RETURN')">↩️ 退回</button>
                <button class="btn-escalate" @click="handleApprovalAction(Number(lvl), 'ESCALATE')">🔺 升级</button>
              </div>
            </div>
          </div>
        </div>

        <!-- No Approval Flow -->
        <div v-if="!approvalFlow && !showStartApproval" class="empty-state" style="padding: 60px 0">
          <div class="empty-icon">📋</div>
          <div class="empty-text">暂无审批流</div>
          <div class="empty-sub">启动审批流后，各层级将按顺序审批</div>
        </div>
      </div>

      <!-- Versions Tab -->
      <div v-else-if="activePlanTab === 'versions'" class="plan-content">
        <div class="versions-toolbar">
          <button class="btn-secondary" @click="openVersionCompare" :disabled="planVersions.length < 2">
            📊 版本对比
          </button>
        </div>
        <div class="versions-list">
          <div v-for="v in planVersions" :key="v" class="version-row">
            <div class="version-badge-lg">v{{ v }}</div>
            <div class="version-info">
              <span class="version-name">{{ v === planDetailActiveVersion ? '当前版本' : v }}</span>
              <button
                v-if="v !== planDetailActiveVersion"
                class="btn-switch-version"
                @click="switchPlanVersion(v)"
              >切换</button>
            </div>
          </div>
          <div v-if="planVersions.length === 0" class="empty-state" style="padding: 60px 0">
            <div class="empty-icon">🗂️</div>
            <div class="empty-text">暂无版本记录</div>
          </div>
        </div>

        <!-- Version Compare Panel -->
        <div v-if="showVersionCompare" class="version-compare-panel">
          <div class="compare-panel-header">
            <div class="compare-title">📊 版本对比</div>
            <button class="modal-close" @click="closeVersionCompare">✕</button>
          </div>
          <div class="compare-selectors">
            <div class="form-group">
              <label>版本 A</label>
              <select v-model="compareVersionA" class="input" @change="loadVersionCompare">
                <option v-for="v in planVersions" :key="v" :value="v">v{{ v }}</option>
              </select>
            </div>
            <div class="compare-arrow">↔</div>
            <div class="form-group">
              <label>版本 B</label>
              <select v-model="compareVersionB" class="input" @change="loadVersionCompare">
                <option v-for="v in planVersions" :key="v" :value="v">v{{ v }}</option>
              </select>
            </div>
            <button class="btn-primary" @click="loadVersionCompare" :disabled="compareLoading">
              {{ compareLoading ? '加载中...' : '对比' }}
            </button>
          </div>
          <div v-if="compareDataA && compareDataB" class="compare-content">
            <div class="compare-summary">
              <div class="compare-col">
                <div class="compare-col-header">v{{ compareVersionA }}</div>
                <div class="compare-stat">房间: {{ compareDataA.rooms?.length || 0 }}</div>
                <div class="compare-stat">任务: {{ compareDataA.tasks?.length || 0 }}</div>
                <div class="compare-stat">决策: {{ compareDataA.decisions?.length || 0 }}</div>
                <div class="compare-stat">风险: {{ compareDataA.risks?.length || 0 }}</div>
                <div class="compare-stat">圣旨: {{ compareDataA.edicts?.length || 0 }}</div>
              </div>
              <div class="compare-col">
                <div class="compare-col-header">v{{ compareVersionB }}</div>
                <div class="compare-stat">房间: {{ compareDataB.rooms?.length || 0 }}</div>
                <div class="compare-stat">任务: {{ compareDataB.tasks?.length || 0 }}</div>
                <div class="compare-stat">决策: {{ compareDataB.decisions?.length || 0 }}</div>
                <div class="compare-stat">风险: {{ compareDataB.risks?.length || 0 }}</div>
                <div class="compare-stat">圣旨: {{ compareDataB.edicts?.length || 0 }}</div>
              </div>
            </div>
            <div class="compare-details">
              <div class="compare-section">
                <div class="compare-section-title">任务差异</div>
                <div class="compare-tasks">
                  <div v-for="task in (compareDataB.tasks || [])" :key="task.task_id" class="compare-task-row">
                    <span class="task-num">#{{ task.task_number }}</span>
                    <span class="task-title">{{ task.title }}</span>
                    <span class="task-status" :class="'status-' + task.status">{{ task.status }}</span>
                  </div>
                  <div v-if="!compareDataB.tasks?.length" class="empty-compare">无任务</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Risks Tab -->
      <div v-else-if="activePlanTab === 'risks'" class="plan-content">
        <div class="risks-toolbar">
          <div class="version-selector">
            <span class="version-label">版本：</span>
            <select
              v-model="planDetailActiveVersion"
              class="input version-select"
              @change="switchPlanVersion(planDetailActiveVersion)"
            >
              <option v-for="v in planVersions" :key="v" :value="v">v{{ v }}</option>
            </select>
          </div>
          <button class="btn-primary" @click="showAddRisk = !showAddRisk; editingRiskId = null; cancelEditRisk()">
            {{ showAddRisk ? '取消' : '+ 添加风险' }}
          </button>
        </div>
        <div v-if="planRisks.length > 0" class="risk-summary">
          <span class="risk-stat critical">🔴 严重 {{ planRisks.filter(r => r.severity === 'critical' || r.probability === 'high' && r.impact === 'high').length }}</span>
          <span class="risk-stat high">🟠 高危 {{ planRisks.filter(r => r.severity === 'high' || (r.probability === 'high' && r.impact === 'medium') || (r.probability === 'medium' && r.impact === 'high')).length }}</span>
          <span class="risk-stat medium">🟡 中等 {{ planRisks.filter(r => r.severity === 'medium' || (r.probability === 'medium' && r.impact === 'medium') || (r.probability === 'high' && r.impact === 'low') || (r.probability === 'low' && r.impact === 'high')).length }}</span>
          <span class="risk-stat low">🟢 低危 {{ planRisks.filter(r => r.severity === 'low' || (r.probability === 'low' && r.impact === 'low') || (r.probability === 'medium' && r.impact === 'low') || (r.probability === 'low' && r.impact === 'medium')).length }}</span>
        </div>

        <!-- Add/Edit Risk Form -->
        <div v-if="showAddRisk" class="add-risk-panel">
          <div class="risk-form-header">{{ editingRiskId ? '编辑风险' : '创建风险' }}</div>
          <input
            v-model="newRiskForm.title"
            class="input"
            placeholder="风险标题 *"
            @keyup.enter="editingRiskId ? handleUpdateRisk(editingRiskId) : handleCreateRisk()"
            autofocus
          />
          <textarea
            v-model="newRiskForm.description"
            class="input risk-text-input"
            placeholder="风险描述（可选）"
            rows="2"
          ></textarea>
          <div class="risk-form-row">
            <div class="form-group">
              <label class="form-label">概率</label>
              <select v-model="newRiskForm.probability" class="input">
                <option value="low">低</option>
                <option value="medium">中</option>
                <option value="high">高</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">影响</label>
              <select v-model="newRiskForm.impact" class="input">
                <option value="low">低</option>
                <option value="medium">中</option>
                <option value="high">高</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">状态</label>
              <select v-model="newRiskForm.status" class="input">
                <option value="identified">已识别</option>
                <option value="monitoring">监控中</option>
                <option value="mitigating">处理中</option>
                <option value="resolved">已解决</option>
              </select>
            </div>
          </div>
          <textarea
            v-model="newRiskForm.mitigation"
            class="input risk-text-input"
            placeholder="缓解措施（可选）"
            rows="2"
          ></textarea>
          <textarea
            v-model="newRiskForm.contingency"
            class="input risk-text-input"
            placeholder="应急预案（可选）"
            rows="2"
          ></textarea>
          <div class="risk-form-actions">
            <button class="btn-primary" @click="editingRiskId ? handleUpdateRisk(editingRiskId) : handleCreateRisk()">
              {{ editingRiskId ? '保存修改' : '创建风险' }}
            </button>
            <button class="btn-cancel" @click="cancelEditRisk()">取消</button>
          </div>
        </div>

        <!-- Risks List -->
        <div v-if="planRisks.length === 0 && !showAddRisk" class="empty-state" style="padding: 60px 0">
          <div class="empty-icon">⚠️</div>
          <div class="empty-text">暂无风险</div>
          <div class="empty-sub">点击上方「+ 添加风险」创建第一条风险记录</div>
        </div>
        <div class="risks-list">
          <div
            v-for="risk in planRisks"
            :key="risk.risk_id"
            class="risk-card"
          >
            <div class="risk-card-header">
              <div class="risk-card-title">{{ risk.title }}</div>
              <div class="risk-card-actions">
                <span class="severity-badge" :class="'sev-' + (risk.severity || 'medium')">
                  {{ risk.severity === 'critical' ? '🔴 严重' : risk.severity === 'high' ? '🟠 高' : risk.severity === 'medium' ? '🟡 中' : '🟢 低' }}
                </span>
                <button class="btn-edit" @click="startEditRisk(risk)">编辑</button>
                <button class="btn-edit btn-delete" @click="handleDeleteRisk(risk.risk_id)">删除</button>
              </div>
            </div>
            <div v-if="risk.description" class="risk-card-desc">{{ risk.description }}</div>
            <div class="risk-card-meta">
              <span class="risk-meta-item">📊 概率: <span class="risk-val">{{ risk.probability === 'high' ? '高' : risk.probability === 'medium' ? '中' : '低' }}</span></span>
              <span class="risk-meta-item">💥 影响: <span class="risk-val">{{ risk.impact === 'high' ? '高' : risk.impact === 'medium' ? '中' : '低' }}</span></span>
              <span class="risk-meta-item status-risk" :class="'status-' + risk.status">
                {{ risk.status === 'identified' ? '📋 已识别' : risk.status === 'monitoring' ? '👁️ 监控中' : risk.status === 'mitigating' ? '🔧 处理中' : '✅ 已解决' }}
              </span>
            </div>
            <div v-if="risk.mitigation" class="risk-card-mitigation">
              <span class="risk-label">缓解措施：</span>{{ risk.mitigation }}
            </div>
            <div v-if="risk.contingency" class="risk-card-contingency">
              <span class="risk-label">应急预案：</span>{{ risk.contingency }}
            </div>
          </div>
        </div>
      </div>

      <!-- Constraints Tab -->
      <div v-else-if="activePlanTab === 'constraints'" class="plan-content">
        <div class="constraints-toolbar">
          <button class="btn-primary" @click="showAddConstraint = !showAddConstraint; editingConstraintId = null; cancelEditConstraint()">
            {{ showAddConstraint ? '取消' : '+ 添加约束' }}
          </button>
        </div>

        <!-- Add/Edit Constraint Form -->
        <div v-if="showAddConstraint" class="add-constraint-panel">
          <div class="constraint-form-header">{{ editingConstraintId ? '编辑约束' : '创建约束' }}</div>
          <div class="constraint-form-row">
            <div class="form-group">
              <label class="form-label">类型</label>
              <select v-model="newConstraintForm.type" class="input">
                <option value="budget">预算</option>
                <option value="time">时间</option>
                <option value="quality">质量</option>
                <option value="scope">范围</option>
                <option value="resource">资源</option>
                <option value="regulatory">法规</option>
                <option value="technical">技术</option>
                <option value="other">其他</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">数值 *</label>
              <input
                v-model="newConstraintForm.value"
                class="input"
                placeholder="约束数值"
                @keyup.enter="editingConstraintId ? handleUpdateConstraint(editingConstraintId) : handleCreateConstraint()"
                autofocus
              />
            </div>
            <div class="form-group">
              <label class="form-label">单位</label>
              <input
                v-model="newConstraintForm.unit"
                class="input"
                placeholder="如: 万元/天/%"
              />
            </div>
          </div>
          <textarea
            v-model="newConstraintForm.description"
            class="input constraint-text-input"
            placeholder="约束描述（可选）"
            rows="2"
          ></textarea>
          <div class="constraint-form-actions">
            <button class="btn-primary" @click="editingConstraintId ? handleUpdateConstraint(editingConstraintId) : handleCreateConstraint()">
              {{ editingConstraintId ? '保存修改' : '创建约束' }}
            </button>
            <button class="btn-cancel" @click="cancelEditConstraint()">取消</button>
          </div>
        </div>

        <!-- Constraints List -->
        <div v-if="planConstraints.length === 0 && !showAddConstraint" class="empty-state" style="padding: 60px 0">
          <div class="empty-icon">🚧</div>
          <div class="empty-text">暂无约束</div>
          <div class="empty-sub">点击上方「+ 添加约束」创建第一条约束记录</div>
        </div>
        <div class="constraints-list">
          <div
            v-for="constraint in planConstraints"
            :key="constraint.constraint_id"
            class="constraint-card"
          >
            <div class="constraint-card-header">
              <div class="constraint-card-title">
                <span class="constraint-type-badge" :class="'type-' + constraint.type">
                  {{ constraint.type === 'budget' ? '💰 预算' : constraint.type === 'time' ? '⏰ 时间' : constraint.type === 'quality' ? '✅ 质量' : constraint.type === 'scope' ? '📐 范围' : constraint.type === 'resource' ? '👥 资源' : constraint.type === 'regulatory' ? '📜 法规' : constraint.type === 'technical' ? '🔧 技术' : '📋 其他' }}
                </span>
                <span class="constraint-value">{{ constraint.value }}{{ constraint.unit ? ' ' + constraint.unit : '' }}</span>
              </div>
              <div class="constraint-card-actions">
                <button class="btn-edit" @click="startEditConstraint(constraint)">编辑</button>
                <button class="btn-edit btn-delete" @click="handleDeleteConstraint(constraint.constraint_id)">删除</button>
              </div>
            </div>
            <div v-if="constraint.description" class="constraint-card-desc">{{ constraint.description }}</div>
          </div>
        </div>
      </div>

      <!-- Stakeholders Tab -->
      <div v-else-if="activePlanTab === 'stakeholders'" class="plan-content">
        <div class="stakeholders-toolbar">
          <button class="btn-primary" @click="showAddStakeholder = !showAddStakeholder; editingStakeholderId = null; cancelEditStakeholder()">
            {{ showAddStakeholder ? '取消' : '+ 添加干系人' }}
          </button>
        </div>

        <!-- Add/Edit Stakeholder Form -->
        <div v-if="showAddStakeholder" class="add-stakeholder-panel">
          <div class="stakeholder-form-header">{{ editingStakeholderId ? '编辑干系人' : '创建干系人' }}</div>
          <input
            v-model="newStakeholderForm.name"
            class="input"
            placeholder="干系人名称 *"
            @keyup.enter="editingStakeholderId ? handleUpdateStakeholder(editingStakeholderId) : handleCreateStakeholder()"
            autofocus
          />
          <div class="stakeholder-form-row">
            <div class="form-group">
              <label class="form-label">层级</label>
              <select v-model="newStakeholderForm.level" class="input">
                <option :value="7">L7 战略层</option>
                <option :value="6">L6 事业部层</option>
                <option :value="5">L5 部门层</option>
                <option :value="4">L4 团队层</option>
                <option :value="3">L3 班组层</option>
                <option :value="2">L2 岗位层</option>
                <option :value="1">L1 任务层</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">关注程度</label>
              <select v-model="newStakeholderForm.interest" class="input">
                <option value="high">高</option>
                <option value="medium">中</option>
                <option value="low">低</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">影响力</label>
              <select v-model="newStakeholderForm.influence" class="input">
                <option value="high">高</option>
                <option value="medium">中</option>
                <option value="low">低</option>
              </select>
            </div>
          </div>
          <textarea
            v-model="newStakeholderForm.description"
            class="input stakeholder-text-input"
            placeholder="干系人描述（可选）"
            rows="2"
          ></textarea>
          <div class="stakeholder-form-actions">
            <button class="btn-primary" @click="editingStakeholderId ? handleUpdateStakeholder(editingStakeholderId) : handleCreateStakeholder()">
              {{ editingStakeholderId ? '保存修改' : '创建干系人' }}
            </button>
            <button class="btn-cancel" @click="cancelEditStakeholder()">取消</button>
          </div>
        </div>

        <!-- Stakeholders List -->
        <div v-if="planStakeholders.length === 0 && !showAddStakeholder" class="empty-state" style="padding: 60px 0">
          <div class="empty-icon">👥</div>
          <div class="empty-text">暂无干系人</div>
          <div class="empty-sub">点击上方「+ 添加干系人」创建第一条干系人记录</div>
        </div>
        <div class="stakeholders-list">
          <div
            v-for="stakeholder in planStakeholders"
            :key="stakeholder.stakeholder_id"
            class="stakeholder-card"
          >
            <div class="stakeholder-card-header">
              <div class="stakeholder-card-title">{{ stakeholder.name }}</div>
              <div class="stakeholder-card-actions">
                <span class="level-badge" :class="'level-' + stakeholder.level">
                  L{{ stakeholder.level || 5 }}
                </span>
                <button class="btn-edit" @click="startEditStakeholder(stakeholder)">编辑</button>
                <button class="btn-edit btn-delete" @click="handleDeleteStakeholder(stakeholder.stakeholder_id)">删除</button>
              </div>
            </div>
            <div class="stakeholder-card-meta">
              <span class="stakeholder-meta-item">
                {{ stakeholder.interest === 'high' ? '🔥' : stakeholder.interest === 'medium' ? '⚡' : '💤' }} 关注: {{ stakeholder.interest === 'high' ? '高' : stakeholder.interest === 'medium' ? '中' : '低' }}
              </span>
              <span class="stakeholder-meta-item">
                {{ stakeholder.influence === 'high' ? '💪' : stakeholder.influence === 'medium' ? '🤝' : '➖' }} 影响: {{ stakeholder.influence === 'high' ? '高' : stakeholder.influence === 'medium' ? '中' : '低' }}
              </span>
            </div>
            <div v-if="stakeholder.description" class="stakeholder-card-desc">{{ stakeholder.description }}</div>
          </div>
        </div>
      </div>

      <!-- Requirements Tab -->
      <div v-else-if="activePlanTab === 'requirements'" class="plan-content">
        <div class="requirements-toolbar">
          <button class="btn-primary" @click="showAddRequirement = !showAddRequirement; editingRequirementId = null; cancelEditRequirement()">
            {{ showAddRequirement ? '取消' : '+ 添加需求' }}
          </button>
        </div>

        <!-- Add/Edit Requirement Form -->
        <div v-if="showAddRequirement" class="add-requirement-panel">
          <div class="requirement-form-header">{{ editingRequirementId ? '编辑需求' : '创建需求' }}</div>
          <textarea
            v-model="newRequirementForm.description"
            class="input requirement-text-input"
            placeholder="需求描述 *"
            rows="3"
          ></textarea>
          <div class="requirement-form-row">
            <div class="form-group">
              <label class="form-label">优先级</label>
              <select v-model="newRequirementForm.priority" class="input">
                <option value="high">高 (HIGH)</option>
                <option value="medium">中 (MEDIUM)</option>
                <option value="low">低 (LOW)</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">类别</label>
              <select v-model="newRequirementForm.category" class="input">
                <option value="budget">💰 预算</option>
                <option value="timeline">⏰ 时间</option>
                <option value="technical">🔧 技术</option>
                <option value="quality">✅ 质量</option>
                <option value="resource">👥 资源</option>
                <option value="risk">⚠️ 风险</option>
                <option value="compliance">📜 法规</option>
                <option value="other">📋 其他</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">状态</label>
              <select v-model="newRequirementForm.status" class="input">
                <option value="pending">待处理</option>
                <option value="in_progress">进行中</option>
                <option value="met">已满足</option>
                <option value="partially_met">部分满足</option>
                <option value="not_met">未满足</option>
                <option value="deprecated">已废弃</option>
              </select>
            </div>
          </div>
          <textarea
            v-model="newRequirementForm.notes"
            class="input requirement-notes-input"
            placeholder="备注（可选）"
            rows="2"
          ></textarea>
          <div class="requirement-form-actions">
            <button class="btn-primary" @click="editingRequirementId ? handleUpdateRequirement(editingRequirementId) : handleCreateRequirement()">
              {{ editingRequirementId ? '保存修改' : '创建需求' }}
            </button>
            <button class="btn-cancel" @click="cancelEditRequirement()">取消</button>
          </div>
        </div>

        <!-- Requirements Summary -->
        <div v-if="planRequirements.length > 0" class="requirement-summary">
          <span class="req-stat pending">⏳ 待处理 {{ planRequirements.filter(r => r.status === 'pending').length }}</span>
          <span class="req-stat in-progress">🔄 进行中 {{ planRequirements.filter(r => r.status === 'in_progress').length }}</span>
          <span class="req-stat met">✅ 已满足 {{ planRequirements.filter(r => r.status === 'met').length }}</span>
          <span class="req-stat partially-met">🔸 部分满足 {{ planRequirements.filter(r => r.status === 'partially_met').length }}</span>
          <span class="req-stat not-met">❌ 未满足 {{ planRequirements.filter(r => r.status === 'not_met').length }}</span>
          <span class="req-stat deprecated">🚫 已废弃 {{ planRequirements.filter(r => r.status === 'deprecated').length }}</span>
        </div>

        <!-- Requirements List -->
        <div v-if="planRequirements.length === 0 && !showAddRequirement" class="empty-state" style="padding: 60px 0">
          <div class="empty-icon">📋</div>
          <div class="empty-text">暂无需求</div>
          <div class="empty-sub">点击上方「+ 添加需求」创建第一条需求记录</div>
        </div>
        <div class="requirements-list">
          <div
            v-for="req in planRequirements"
            :key="req.id"
            class="requirement-card"
          >
            <div class="requirement-card-header">
              <div class="requirement-card-title">{{ req.description }}</div>
              <div class="requirement-card-actions">
                <span class="priority-badge" :class="'priority-' + req.priority">
                  {{ req.priority === 'high' ? '🔴 高' : req.priority === 'medium' ? '🟡 中' : '🟢 低' }}
                </span>
                <span class="category-badge" :class="'category-' + req.category">
                  {{ req.category === 'budget' ? '💰' : req.category === 'timeline' ? '⏰' : req.category === 'technical' ? '🔧' : req.category === 'quality' ? '✅' : req.category === 'resource' ? '👥' : req.category === 'risk' ? '⚠️' : req.category === 'compliance' ? '📜' : '📋' }}
                  {{ req.category }}
                </span>
                <span class="status-badge" :class="'status-' + req.status">
                  {{ req.status === 'pending' ? '⏳ 待处理' : req.status === 'in_progress' ? '🔄 进行中' : req.status === 'met' ? '✅ 已满足' : req.status === 'partially_met' ? '🔸 部分' : req.status === 'not_met' ? '❌ 未满足' : '🚫 废弃' }}
                </span>
                <button class="btn-edit" @click="startEditRequirement(req)">编辑</button>
                <button class="btn-edit btn-delete" @click="handleDeleteRequirement(req.id)">删除</button>
              </div>
            </div>
            <div v-if="req.notes" class="requirement-card-notes">{{ req.notes }}</div>
          </div>
        </div>
      </div>

      <!-- Participants Tab -->
      <div v-else-if="activePlanTab === 'participants'" class="plan-content">
        <!-- Summary Bar -->
        <div v-if="participantActivity.length > 0" class="participant-summary-bar">
          <div class="summary-item">
            <span class="summary-value">{{ participantActivity.length }}</span>
            <span class="summary-label">参与者</span>
          </div>
          <div class="summary-item">
            <span class="summary-value">{{ participantActivity.reduce((s: number, p: any) => s + p.message_count, 0) }}</span>
            <span class="summary-label">总消息</span>
          </div>
          <div class="summary-item">
            <span class="summary-value">{{ participantActivity.reduce((s: number, p: any) => s + p.speech_count, 0) }}</span>
            <span class="summary-label">总发言</span>
          </div>
          <div class="summary-item">
            <span class="summary-value">{{ participantActivity.reduce((s: number, p: any) => s + p.challenge_count, 0) }}</span>
            <span class="summary-label">总挑战</span>
          </div>
        </div>

        <!-- Participant Activity List -->
        <div v-if="participantActivity.length === 0" class="empty-state">
          <div style="padding: 60px 0; text-align: center; color: #9ca3af;">
            <div style="font-size: 32px; margin-bottom: 12px;">👥</div>
            <div>暂无参与者活动数据</div>
          </div>
        </div>

        <div v-else class="participant-list">
          <div v-for="p in participantActivity" :key="p.participant_id" class="participant-card">
            <div class="participant-card-header">
              <div class="participant-avatar">{{ p.name?.charAt(0)?.toUpperCase() || '?' }}</div>
              <div class="participant-info">
                <div class="participant-name">{{ p.name }}</div>
                <div class="participant-meta">
                  <span class="level-badge">L{{ p.level }}</span>
                  <span class="role-badge">{{ p.role }}</span>
                  <span class="rooms-badge">🏛️ {{ p.rooms_joined }} 房间</span>
                </div>
              </div>
            </div>
            <div class="participant-stats">
              <div class="stat-item">
                <div class="stat-num">{{ p.message_count }}</div>
                <div class="stat-lbl">消息</div>
              </div>
              <div class="stat-item">
                <div class="stat-num">{{ p.speech_count }}</div>
                <div class="stat-lbl">发言</div>
              </div>
              <div class="stat-item">
                <div class="stat-num">{{ p.challenge_count }}</div>
                <div class="stat-lbl">挑战</div>
              </div>
              <div class="stat-item">
                <div class="stat-num">{{ p.response_count }}</div>
                <div class="stat-lbl">回应</div>
              </div>
              <div class="stat-item">
                <div class="stat-num">{{ p.activity_count }}</div>
                <div class="stat-lbl">活动</div>
              </div>
            </div>
            <!-- Activity Bar -->
            <div class="participant-bar">
              <div class="bar-label">消息分布</div>
              <div class="bar-track">
                <div class="bar-fill bar-speech" :style="{ width: p.message_count > 0 ? (p.speech_count / p.message_count * 100) + '%' : '0%' }" title="发言"></div>
                <div class="bar-fill bar-challenge" :style="{ width: p.message_count > 0 ? (p.challenge_count / p.message_count * 100) + '%' : '0%' }" title="挑战"></div>
                <div class="bar-fill bar-response" :style="{ width: p.message_count > 0 ? (p.response_count / p.message_count * 100) + '%' : '0%' }" title="回应"></div>
              </div>
              <div class="bar-legend">
                <span class="legend-item"><span class="dot dot-speech"></span>发言</span>
                <span class="legend-item"><span class="dot dot-challenge"></span>挑战</span>
                <span class="legend-item"><span class="dot dot-response"></span>回应</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Activities Tab -->
      <div v-else-if="activePlanTab === 'activities'" class="plan-content">
        <!-- Scope Selector -->
        <div class="activity-scope-bar">
          <div class="scope-tabs">
            <button
              class="scope-tab"
              :class="{ active: activityScope === 'plan' }"
              @click="activityScope = 'plan'; activityScopeRoomId = ''; activityScopeVersion = ''; loadPlanActivities()"
            >📋 计划</button>
            <button
              class="scope-tab"
              :class="{ active: activityScope === 'room' }"
              @click="activityScope = 'room'; activityScopeVersion = ''; loadPlanActivities()"
            >🏛️ 房间</button>
            <button
              class="scope-tab"
              :class="{ active: activityScope === 'version' }"
              @click="activityScope = 'version'; activityScopeRoomId = ''; activityScopeVersion = planDetailActiveVersion; loadPlanActivities()"
            >📦 版本</button>
          </div>
          <!-- Room selector (when scope=room) -->
          <select
            v-if="activityScope === 'room'"
            v-model="activityScopeRoomId"
            class="input activity-scope-select"
            @change="loadPlanActivities()"
          >
            <option value="">选择讨论室...</option>
            <option v-for="room in planRooms" :key="room.room_id" :value="room.room_id">
              {{ room.topic || room.title || '房间 ' + room.room_id.slice(0,8) }}
            </option>
          </select>
          <!-- Version selector (when scope=version) -->
          <select
            v-if="activityScope === 'version'"
            v-model="activityScopeVersion"
            class="input activity-scope-select"
            @change="loadPlanActivities()"
          >
            <option value="">选择版本...</option>
            <option v-for="v in planVersions" :key="v" :value="v">{{ v }}</option>
          </select>
        </div>

        <!-- Activity Stats Summary (plan scope only) -->
        <div v-if="activityStats" class="activity-stats">
          <div class="activity-stat-card">
            <div class="activity-stat-num">{{ activityStats.total || 0 }}</div>
            <div class="activity-stat-label">总活动数</div>
          </div>
          <div v-for="(count, type) in activityStats.by_type" :key="type" class="activity-stat-card">
            <div class="activity-stat-num">{{ count }}</div>
            <div class="activity-stat-label">{{ String(type).split('.')[1] || type }}</div>
          </div>
        </div>

        <!-- Filter Bar -->
        <div class="activity-filter-bar">
          <select v-model="activityFilterType" class="input activity-filter-select">
            <option value="">全部类型</option>
            <option value="plan">计划</option>
            <option value="room">房间</option>
            <option value="task">任务</option>
            <option value="decision">决策</option>
            <option value="edict">圣旨</option>
            <option value="problem">问题</option>
            <option value="approval">审批</option>
            <option value="escalation">升级</option>
            <option value="risk">风险</option>
            <option value="constraint">约束</option>
            <option value="stakeholder">干系人</option>
            <option value="participant">参与者</option>
            <option value="subtask">子任务</option>
          </select>
          <button class="btn-primary" @click="loadPlanActivities">刷新</button>
        </div>

        <!-- Activity Detail -->
        <div v-if="selectedActivity" class="activity-detail-panel">
          <div class="activity-detail-header">
            <div class="activity-detail-title">活动详情</div>
            <button class="btn-edit" @click="selectedActivity = null">关闭</button>
          </div>
          <div class="info-row">
            <span class="info-label">活动ID</span>
            <span class="info-value">{{ selectedActivity.activity_id }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">类型</span>
            <span class="info-value">{{ selectedActivity.action_type }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">时间</span>
            <span class="info-value">{{ new Date(selectedActivity.timestamp).toLocaleString() }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">执行人</span>
            <span class="info-value">{{ selectedActivity.performed_by || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">层级</span>
            <span class="info-value">{{ selectedActivity.level || '-' }}</span>
          </div>
          <div class="activity-detail-content">{{ selectedActivity.description || selectedActivity.content || '无描述' }}</div>
        </div>

        <!-- Activities List -->
        <div v-if="planActivities.length === 0" class="empty-state" style="padding: 60px 0">
          <div class="empty-icon">📋</div>
          <div class="empty-text">暂无活动记录</div>
          <div class="empty-sub">计划内的操作将自动记录为活动历史</div>
        </div>
        <div class="activities-list">
          <div
            v-for="act in filteredActivities"
            :key="act.activity_id"
            class="activity-card"
            @click="selectedActivity = act"
          >
            <div class="activity-card-header">
              <span class="activity-type-badge" :class="'activity-type-' + (act.action_type?.split('.')[0] || 'other')">
                {{ act.action_type || 'unknown' }}
              </span>
              <span class="activity-time">{{ new Date(act.timestamp).toLocaleString() }}</span>
            </div>
            <div class="activity-card-content">{{ act.description || act.content || '无描述' }}</div>
            <div class="activity-card-footer">
              <span v-if="act.performed_by" class="activity-performer">👤 {{ act.performed_by }}</span>
              <span v-if="act.level" class="activity-level">L{{ act.level }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Analytics Tab -->
      <div v-else-if="activePlanTab === 'analytics'" class="plan-content">
        <div class="tab-header-row">
          <div class="tab-title">📊 数据分析</div>
          <button class="btn-primary" @click="loadAnalyticsData">刷新</button>
        </div>

        <!-- Summary Cards -->
        <div v-if="planMetrics" class="analytics-summary-cards">
          <div class="analytics-card rooms-card">
            <div class="analytics-card-icon">🏛️</div>
            <div class="analytics-card-body">
              <div class="analytics-card-num">{{ planMetrics.rooms?.total || 0 }}</div>
              <div class="analytics-card-label">讨论室</div>
              <div class="analytics-card-sub">
                <span class="sub-active">{{ planMetrics.rooms?.active || 0 }} 活跃</span>
                <span class="sub-div">|</span>
                <span class="sub-done">{{ planMetrics.rooms?.completed || 0 }} 已完成</span>
              </div>
            </div>
          </div>
          <div class="analytics-card tasks-card">
            <div class="analytics-card-icon">📋</div>
            <div class="analytics-card-body">
              <div class="analytics-card-num">{{ planMetrics.tasks?.total || 0 }}</div>
              <div class="analytics-card-label">任务总数</div>
              <div class="analytics-card-sub">
                <span class="sub-done">✅ {{ planMetrics.tasks?.completed || 0 }} 已完成</span>
                <span class="sub-div">|</span>
                <span class="sub-progress">🔄 {{ planMetrics.tasks?.in_progress || 0 }} 进行中</span>
              </div>
            </div>
          </div>
          <div class="analytics-card decisions-card">
            <div class="analytics-card-icon">⚖️</div>
            <div class="analytics-card-body">
              <div class="analytics-card-num">{{ planMetrics.decisions?.total || 0 }}</div>
              <div class="analytics-card-label">决策总数</div>
            </div>
          </div>
          <div class="analytics-card risks-card">
            <div class="analytics-card-icon">🚨</div>
            <div class="analytics-card-body">
              <div class="analytics-card-num">{{ planMetrics.risks?.total || 0 }}</div>
              <div class="analytics-card-label">风险总数</div>
            </div>
          </div>
        </div>

        <!-- Two Column Layout -->
        <div v-if="planMetrics" class="analytics-grid">
          <!-- Rooms Phase Distribution -->
          <div class="analytics-panel">
            <div class="analytics-panel-title">🏛️ 讨论室阶段分布</div>
            <div class="analytics-empty" v-if="!planMetrics.rooms?.by_phase || Object.keys(planMetrics.rooms.by_phase).length === 0">
              暂无数据
            </div>
            <div v-else class="phase-distribution">
              <div
                v-for="(count, phase) in planMetrics.rooms.by_phase"
                :key="phase"
                class="phase-row"
              >
                <div class="phase-label-row">
                  <span class="phase-name">{{ phaseLabel[phase] || phase }}</span>
                  <span class="phase-count">{{ count }}</span>
                </div>
                <div class="phase-bar-track">
                  <div
                    class="phase-bar-fill"
                    :style="{
                      width: (count / planMetrics.rooms.total * 100) + '%',
                      background: phaseColors[phase] || '#6b7280'
                    }"
                  ></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Tasks Status Breakdown -->
          <div class="analytics-panel">
            <div class="analytics-panel-title">📋 任务状态分析</div>
            <div class="task-status-breakdown">
              <div
                v-for="(count, status) in planMetrics.tasks?.by_status"
                :key="status"
                class="task-status-row"
              >
                <div class="task-status-label">
                  <span class="task-status-dot" :class="'dot-' + status"></span>
                  <span>{{ String(status) === 'completed' ? '✅ 已完成' : String(status) === 'in_progress' ? '🔄 进行中' : String(status) === 'blocked' ? '🚫 阻塞' : String(status) === 'pending' ? '⏳ 待处理' : status }}</span>
                  <span class="task-status-count">{{ count }}</span>
                </div>
                <div class="task-status-bar-track">
                  <div
                    class="task-status-bar-fill"
                    :class="'fill-' + status"
                    :style="{ width: ((count as number) / planMetrics.tasks.total * 100) + '%' }"
                  ></div>
                </div>
              </div>
            </div>

            <!-- Task Priority Distribution -->
            <div class="analytics-panel-title" style="margin-top:20px">🎯 任务优先级</div>
            <div class="priority-breakdown">
              <div
                v-for="(count, priority) in planMetrics.tasks?.by_priority"
                :key="priority"
                class="priority-row"
              >
                <span class="priority-label">{{ String(priority) === 'critical' ? '🔴 紧急' : String(priority) === 'high' ? '🟠 高' : String(priority) === 'medium' ? '🟡 中' : '🟢 低' }}</span>
                <div class="priority-bar-track">
                  <div
                    class="priority-bar-fill"
                    :class="'fill-' + priority"
                    :style="{ width: ((count as number) / planMetrics.tasks.total * 100) + '%' }"
                  ></div>
                </div>
                <span class="priority-count">{{ count }}</span>
              </div>
            </div>
          </div>

          <!-- Tasks Completion Rate -->
          <div class="analytics-panel wide">
            <div class="analytics-panel-title">📈 整体进度</div>
            <div class="completion-overview">
              <div class="completion-big-ring">
                <svg viewBox="0 0 120 120" class="ring-svg">
                  <circle cx="60" cy="60" r="50" fill="none" stroke="#e5e7eb" stroke-width="12"/>
                  <circle
                    cx="60" cy="60" r="50" fill="none"
                    :stroke="planMetrics.tasks?.completion_rate >= 70 ? '#22c55e' : planMetrics.tasks?.completion_rate >= 40 ? '#f59e0b' : '#ef4444'"
                    stroke-width="12"
                    stroke-linecap="round"
                    :stroke-dasharray="314"
                    :stroke-dashoffset="314 - (314 * (planMetrics.tasks?.completion_rate || 0))"
                    transform="rotate(-90 60 60)"
                  />
                </svg>
                <div class="ring-label">
                  <div class="ring-pct">{{ ((planMetrics.tasks?.completion_rate || 0) * 100).toFixed(0) }}%</div>
                  <div class="ring-sub">完成率</div>
                </div>
              </div>
              <div class="completion-stats">
                <div class="stat-row">
                  <span class="stat-lbl">平均进度</span>
                  <span class="stat-val">{{ ((planMetrics.tasks?.average_progress || 0) * 100).toFixed(0) }}%</span>
                </div>
                <div class="stat-row">
                  <span class="stat-lbl">已完成</span>
                  <span class="stat-val done">{{ planMetrics.tasks?.completed || 0 }}</span>
                </div>
                <div class="stat-row">
                  <span class="stat-lbl">进行中</span>
                  <span class="stat-val progress">{{ planMetrics.tasks?.in_progress || 0 }}</span>
                </div>
                <div class="stat-row">
                  <span class="stat-lbl">阻塞</span>
                  <span class="stat-val blocked">{{ planMetrics.tasks?.blocked || 0 }}</span>
                </div>
                <div class="stat-row">
                  <span class="stat-lbl">待处理</span>
                  <span class="stat-val pending">{{ planMetrics.tasks?.pending || 0 }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Hours Estimate -->
          <div class="analytics-panel" v-if="planMetrics.tasks?.total_estimated_hours > 0">
            <div class="analytics-panel-title">⏱️ 工时估算</div>
            <div class="hours-comparison">
              <div class="hours-row">
                <span class="hours-label">预估</span>
                <div class="hours-bar-track">
                  <div class="hours-bar-fill estimated" :style="{ width: Math.min(100, (planMetrics.tasks.total_estimated_hours / Math.max(planMetrics.tasks.total_estimated_hours, planMetrics.tasks.total_actual_hours || 1) * 100)) + '%' }"></div>
                </div>
                <span class="hours-num">{{ planMetrics.tasks.total_estimated_hours.toFixed(1) }}h</span>
              </div>
              <div class="hours-row">
                <span class="hours-label">实际</span>
                <div class="hours-bar-track">
                  <div class="hours-bar-fill actual" :style="{ width: Math.min(100, (planMetrics.tasks.total_actual_hours / Math.max(planMetrics.tasks.total_estimated_hours, planMetrics.tasks.total_actual_hours || 1) * 100)) + '%' }"></div>
                </div>
                <span class="hours-num">{{ (planMetrics.tasks.total_actual_hours || 0).toFixed(1) }}h</span>
              </div>
              <div class="hours-variance" v-if="planMetrics.tasks.total_actual_hours > 0">
                <span class="variance-label">偏差:</span>
                <span class="variance-val" :class="planMetrics.tasks.total_actual_hours > planMetrics.tasks.total_estimated_hours ? 'over' : 'under'">
                  {{ planMetrics.tasks.total_actual_hours > planMetrics.tasks.total_estimated_hours ? '+' : '' }}{{ (planMetrics.tasks.total_actual_hours - planMetrics.tasks.total_estimated_hours).toFixed(1) }}h
                  ({{ (((planMetrics.tasks.total_actual_hours / planMetrics.tasks.total_estimated_hours - 1) * 100)).toFixed(0) }}%)
                </span>
              </div>
            </div>
          </div>

          <!-- Decisions, Risks, Edicts Counts -->
          <div class="analytics-panel">
            <div class="analytics-panel-title">📦 其他统计</div>
            <div class="other-stats-grid">
              <div class="other-stat-card">
                <div class="other-stat-icon">⚖️</div>
                <div class="other-stat-num">{{ planMetrics.decisions?.total || 0 }}</div>
                <div class="other-stat-label">决策</div>
              </div>
              <div class="other-stat-card">
                <div class="other-stat-icon">🚨</div>
                <div class="other-stat-num">{{ planMetrics.risks?.total || 0 }}</div>
                <div class="other-stat-label">风险</div>
              </div>
              <div class="other-stat-card">
                <div class="other-stat-icon">📜</div>
                <div class="other-stat-num">{{ planMetrics.edicts?.total || 0 }}</div>
                <div class="other-stat-label">圣旨</div>
              </div>
              <div class="other-stat-card">
                <div class="other-stat-icon">🏛️</div>
                <div class="other-stat-num">{{ planMetrics.rooms?.active || 0 }}</div>
                <div class="other-stat-label">活跃房间</div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="!planMetrics" class="empty-state" style="padding: 60px 0">
          <div class="empty-icon">📊</div>
          <div class="empty-text">暂无分析数据</div>
          <button class="btn-primary" @click="loadAnalyticsData">加载数据</button>
        </div>
      </div>

      <!-- Snapshots Tab -->
      <div v-else-if="activePlanTab === 'snapshots'" class="plan-content">
        <div class="tab-header-row">
          <div class="tab-title">上下文快照</div>
          <button class="btn-primary" @click="loadPlanSnapshots">刷新</button>
        </div>

        <!-- Snapshot Detail -->
        <div v-if="selectedSnapshot" class="snapshot-detail-panel">
          <div class="snapshot-detail-header">
            <div class="snapshot-detail-title">快照详情</div>
            <button class="btn-edit" @click="selectedSnapshot = null">关闭</button>
          </div>
          <div class="info-row">
            <span class="info-label">快照ID</span>
            <span class="info-value">{{ selectedSnapshot.snapshot_id }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">关联房间</span>
            <span class="info-value">{{ selectedSnapshot.room_id || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">阶段</span>
            <span class="info-value phase-badge" :style="{ background: phaseColors[selectedSnapshot.phase] || '#6b7280' }">
              {{ selectedSnapshot.phase || '-' }}
            </span>
          </div>
          <div class="info-row">
            <span class="info-label">创建时间</span>
            <span class="info-value">{{ new Date(selectedSnapshot.created_at).toLocaleString() }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">上下文摘要</span>
          </div>
          <div class="snapshot-context">{{ selectedSnapshot.context_summary || '无摘要' }}</div>
        </div>

        <!-- Snapshots List -->
        <div v-if="planSnapshots.length === 0" class="empty-state" style="padding: 60px 0">
          <div class="empty-icon">📸</div>
          <div class="empty-text">暂无快照记录</div>
          <div class="empty-sub">讨论室推进时会自动创建上下文快照</div>
        </div>
        <div v-else class="snapshots-list">
          <div
            v-for="snap in planSnapshots"
            :key="snap.snapshot_id"
            class="snapshot-card"
            @click="viewSnapshot(snap)"
          >
            <div class="snapshot-card-header">
              <span class="phase-badge" :style="{ background: phaseColors[snap.phase] || '#6b7280' }">
                {{ snap.phase || 'unknown' }}
              </span>
              <span class="snapshot-time">{{ new Date(snap.created_at).toLocaleString() }}</span>
            </div>
            <div class="snapshot-card-summary">{{ snap.context_summary || '无摘要' }}</div>
            <div class="snapshot-card-id">ID: {{ snap.snapshot_id?.slice(0, 8) }}...</div>
          </div>
        </div>
      </div>

      <!-- Escalations Tab -->
      <div v-else-if="activePlanTab === 'escalations'" class="plan-content">
        <div class="tab-header-row">
          <div class="tab-title">升级记录</div>
          <button class="btn-primary" @click="loadPlanEscalations">刷新</button>
        </div>

        <!-- Escalation Action Modal -->
        <div v-if="showEscalationAction" class="modal-overlay" @click.self="showEscalationAction = false">
          <div class="modal-content">
            <div class="modal-header">
              <h3>🔺 处理升级</h3>
              <button class="modal-close" @click="showEscalationAction = false">✕</button>
            </div>
            <div class="modal-body">
              <div class="form-row">
                <label>操作 *</label>
                <select v-model="escalationActionForm.action" class="input">
                  <option value="">选择操作</option>
                  <option value="approve">批准</option>
                  <option value="reject">驳回</option>
                  <option value="forward">转发</option>
                  <option value="reassign">重新分配</option>
                </select>
              </div>
              <div class="form-row">
                <label>操作人</label>
                <input v-model="escalationActionForm.actor_name" class="input" placeholder="操作人姓名" />
              </div>
              <div class="form-row">
                <label>意见</label>
                <textarea v-model="escalationActionForm.comment" class="input" placeholder="处理意见..." rows="3"></textarea>
              </div>
              <div class="form-actions">
                <button class="btn-secondary" @click="showEscalationAction = false">取消</button>
                <button class="btn-primary" :disabled="escalationActionLoading || !escalationActionForm.action" @click="handleEscalationAction">
                  {{ escalationActionLoading ? '处理中...' : '提交' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Escalations Summary -->
        <div v-if="planEscalations.length > 0" class="summary-bar">
          <span class="summary-item">总升级数：<strong>{{ planEscalations.length }}</strong></span>
        </div>

        <!-- Escalations List -->
        <div v-if="planEscalations.length === 0" class="empty-state" style="padding: 60px 0">
          <div class="empty-icon">🔺</div>
          <div class="empty-text">暂无升级记录</div>
          <div class="empty-sub">当讨论室需要上级决策时会创建升级记录</div>
        </div>
        <div v-else class="escalations-list">
          <div
            v-for="esc in planEscalations"
            :key="esc.escalation_id"
            class="escalation-card"
            :class="{ 'escalation-pending': esc.status === 'pending' }"
          >
            <div class="escalation-card-header">
              <div class="escalation-levels">
                <span class="level-badge level-from">L{{ esc.from_level }}</span>
                <span class="level-arrow">→</span>
                <span class="level-badge level-to">L{{ esc.to_level }}</span>
              </div>
              <span class="escalation-status" :class="'status-' + esc.status">{{ esc.status || 'pending' }}</span>
            </div>
            <div class="escalation-card-body">
              <div class="escalation-info">
                <span class="info-label">模式：</span>
                <span class="info-value">{{ esc.mode === 'level_by_level' ? '逐级汇报' : esc.mode === 'cross_level' ? '跨级汇报' : '紧急汇报' }}</span>
              </div>
              <div v-if="esc.escalation_path && esc.escalation_path.length > 0" class="escalation-info">
                <span class="info-label">路径：</span>
                <span class="info-value">{{ 'L' + esc.escalation_path.join(' → L') }}</span>
              </div>
              <div v-if="esc.room_id" class="escalation-info">
                <span class="info-label">房间：</span>
                <span class="info-value escalation-room-id">{{ esc.room_id.slice(0, 8) }}...</span>
              </div>
              <div v-if="esc.content?.reason" class="escalation-reason">{{ esc.content.reason }}</div>
              <div v-if="esc.content?.notes" class="escalation-notes">{{ esc.content.notes }}</div>
            </div>
            <div class="escalation-card-footer">
              <span class="escalation-time">{{ new Date(esc.created_at || Date.now()).toLocaleString() }}</span>
              <button class="btn-edit btn-small" @click="openEscalationAction(esc)">处理</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Action Items Tab -->
      <div v-else-if="activePlanTab === 'action_items'" class="plan-content">
        <div class="tab-header-row">
          <div class="tab-title">📋 行动项</div>
          <div class="tab-header-actions">
            <select v-model="actionItemFilter" class="input filter-select" @change="loadPlanActionItems(actionItemFilter || undefined)">
              <option value="">全部</option>
              <option value="open">待处理</option>
              <option value="in_progress">进行中</option>
              <option value="completed">已完成</option>
            </select>
            <button class="btn-secondary" @click="loadPlanActionItems(actionItemFilter || undefined)">刷新</button>
          </div>
        </div>

        <!-- Action Items Summary -->
        <div v-if="planActionItems.length > 0" class="summary-bar">
          <span class="summary-item">总数：<strong>{{ planActionItems.length }}</strong></span>
          <span class="summary-item">待处理：<strong>{{ planActionItems.filter(i => i.status === 'open').length }}</strong></span>
          <span class="summary-item">进行中：<strong>{{ planActionItems.filter(i => i.status === 'in_progress').length }}</strong></span>
          <span class="summary-item">已完成：<strong>{{ planActionItems.filter(i => i.status === 'completed').length }}</strong></span>
        </div>

        <!-- Empty State -->
        <div v-if="planActionItems.length === 0 && !actionItemLoading" class="empty-state" style="padding: 60px 0">
          <div class="empty-icon">📋</div>
          <div class="empty-text">暂无行动项</div>
          <div class="empty-sub">在讨论室中创建的行动项将显示在这里</div>
        </div>

        <!-- Action Items List -->
        <div v-if="planActionItems.length > 0" class="action-items-list">
          <div
            v-for="item in planActionItems"
            :key="item.action_item_id"
            class="action-item-card"
            :class="{ 'action-item-completed': item.status === 'completed' }"
          >
            <div class="action-item-header">
              <div class="action-item-status">
                <span class="status-badge" :class="'badge-' + item.status">{{ item.status === 'open' ? '⏳ 待处理' : item.status === 'in_progress' ? '🔄 进行中' : '✅ 已完成' }}</span>
              </div>
              <div class="action-item-priority" :class="'priority-' + item.priority">{{ item.priority === 'critical' ? '🔴 紧急' : item.priority === 'high' ? '🟠 高' : item.priority === 'medium' ? '🟡 中' : '🟢 低' }}</div>
            </div>
            <div class="action-item-title">{{ item.title }}</div>
            <div v-if="item.description" class="action-item-desc">{{ item.description }}</div>
            <div class="action-item-meta">
              <span v-if="item.assignee">👤 {{ item.assignee }}<span v-if="item.assignee_level"> (L{{ item.assignee_level }})</span></span>
              <span v-if="item.due_date">📅 {{ item.due_date.split('T')[0] }}</span>
              <span v-if="item.created_by">📝 {{ item.created_by }}</span>
            </div>
            <div class="action-item-footer">
              <span class="action-item-time">{{ new Date(item.created_at || Date.now()).toLocaleString() }}</span>
              <div class="action-item-actions">
                <button v-if="item.status !== 'completed'" class="btn-complete btn-small" @click="handleCompleteActionItem(item.action_item_id, item.room_id)">完成</button>
                <button class="btn-edit btn-small" @click="startEditActionItem(item)">编辑</button>
                <button class="btn-delete btn-small" @click="handleDeleteActionItem(item.action_item_id, item.room_id)">删除</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Meeting Minutes Tab -->
      <div v-else-if="activePlanTab === 'meeting_minutes'" class="plan-content">
        <div class="tab-header-row">
          <div class="tab-title">📝 会议纪要</div>
          <div class="tab-header-actions">
            <button class="btn-primary" @click="loadPlanMeetingMinutes()">刷新</button>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="planMeetingMinutes.length === 0 && !meetingMinutesLoading" class="empty-state" style="padding: 60px 0">
          <div class="empty-icon">📝</div>
          <div class="empty-text">暂无会议纪要</div>
          <div class="empty-sub">在讨论室中生成会议纪要，将显示在这里</div>
        </div>

        <!-- Meeting Minutes List -->
        <div v-if="planMeetingMinutes.length > 0" class="meeting-minutes-list">
          <div
            v-for="minutes in planMeetingMinutes"
            :key="minutes.meeting_minutes_id"
            class="meeting-minutes-card"
            @click="openMeetingMinutesDetail(minutes)"
          >
            <div class="meeting-minutes-header">
              <div class="meeting-minutes-title">{{ minutes.title }}</div>
              <div class="meeting-minutes-time">{{ new Date(minutes.created_at || Date.now()).toLocaleString() }}</div>
            </div>
            <div v-if="minutes.summary" class="meeting-minutes-summary">{{ minutes.summary }}</div>
            <div v-if="minutes.decisions_summary" class="meeting-minutes-badge decisions">📜 {{ minutes.decisions_summary }}</div>
            <div v-if="minutes.action_items_summary" class="meeting-minutes-badge actions">✅ {{ minutes.action_items_summary }}</div>
            <div class="meeting-minutes-meta">
              <span v-if="minutes.created_by">👤 {{ minutes.created_by }}</span>
              <span v-if="minutes.duration_minutes">⏱ {{ minutes.duration_minutes }}分钟</span>
              <span v-if="minutes.participants_list && minutes.participants_list.length > 0">👥 {{ minutes.participants_list.length }}人</span>
            </div>
            <div class="meeting-minutes-footer">
              <button class="btn-delete btn-small" @click.stop="handleDeleteMeetingMinutes(minutes.meeting_minutes_id)">删除</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Meeting Minutes Detail Modal -->
      <div v-if="selectedMeetingMinutes" class="modal-overlay" @click.self="selectedMeetingMinutes = null">
        <div class="modal-content meeting-minutes-detail-modal">
          <div class="modal-header">
            <h3>📝 {{ selectedMeetingMinutes.title }}</h3>
            <button class="modal-close" @click="selectedMeetingMinutes = null">✕</button>
          </div>
          <div class="modal-body">
            <div class="minutes-detail-meta">
              <span v-if="selectedMeetingMinutes.created_by">👤 {{ selectedMeetingMinutes.created_by }}</span>
              <span v-if="selectedMeetingMinutes.created_at">🕐 {{ new Date(selectedMeetingMinutes.created_at).toLocaleString() }}</span>
              <span v-if="selectedMeetingMinutes.duration_minutes">⏱ {{ selectedMeetingMinutes.duration_minutes }}分钟</span>
            </div>
            <div v-if="selectedMeetingMinutes.summary" class="minutes-section">
              <div class="minutes-section-title">📋 摘要</div>
              <div class="minutes-section-content">{{ selectedMeetingMinutes.summary }}</div>
            </div>
            <div v-if="selectedMeetingMinutes.decisions_summary" class="minutes-section">
              <div class="minutes-section-title">📜 决策要点</div>
              <div class="minutes-section-content">{{ selectedMeetingMinutes.decisions_summary }}</div>
            </div>
            <div v-if="selectedMeetingMinutes.action_items_summary" class="minutes-section">
              <div class="minutes-section-title">✅ 行动项</div>
              <div class="minutes-section-content">{{ selectedMeetingMinutes.action_items_summary }}</div>
            </div>
            <div v-if="selectedMeetingMinutes.participants_list && selectedMeetingMinutes.participants_list.length > 0" class="minutes-section">
              <div class="minutes-section-title">👥 参与者</div>
              <div class="minutes-section-content">{{ selectedMeetingMinutes.participants_list.join(', ') }}</div>
            </div>
            <div v-if="selectedMeetingMinutes.content" class="minutes-section">
              <div class="minutes-section-title">📄 完整内容</div>
              <pre class="minutes-content">{{ selectedMeetingMinutes.content }}</pre>
            </div>
          </div>
        </div>
      </div>

      <!-- Room Templates Modal -->
      <div v-if="showRoomTemplates" class="modal-overlay" @click.self="showRoomTemplates = false">
        <div class="modal-content room-templates-modal">
          <div class="modal-header">
            <h3>📋 房间模板</h3>
            <div class="modal-header-actions">
              <button class="btn-primary btn-small" @click="showCreateTemplate = true; editingTemplate = null; Object.assign(newTemplateForm, { name: '', description: '', purpose: 'initial_discussion', mode: 'hierarchical', default_phase: 'selecting', settings: {}, is_shared: false })">
                + 新建模板
              </button>
              <button class="modal-close" @click="showRoomTemplates = false">✕</button>
            </div>
          </div>
          <div class="modal-body">
            <!-- Create Template Form -->
            <div v-if="showCreateTemplate" class="template-create-form">
              <div class="form-row">
                <label>模板名称 *</label>
                <input v-model="newTemplateForm.name" class="input" placeholder="例如：战略决策室" />
              </div>
              <div class="form-row">
                <label>描述</label>
                <textarea v-model="newTemplateForm.description" class="input" placeholder="模板用途说明..." rows="2"></textarea>
              </div>
              <div class="form-row-inline">
                <div class="form-field">
                  <label>用途</label>
                  <select v-model="newTemplateForm.purpose" class="input">
                    <option value="initial_discussion">初始讨论</option>
                    <option value="problem_solving">问题解决</option>
                    <option value="decision_making">决策制定</option>
                    <option value="review">评审回顾</option>
                  </select>
                </div>
                <div class="form-field">
                  <label>模式</label>
                  <select v-model="newTemplateForm.mode" class="input">
                    <option value="hierarchical">层级模式</option>
                    <option value="flat">扁平模式</option>
                    <option value="collaborative">协作模式</option>
                    <option value="specialized">专业模式</option>
                  </select>
                </div>
                <div class="form-field">
                  <label>默认阶段</label>
                  <select v-model="newTemplateForm.default_phase" class="input">
                    <option value="selecting">选择</option>
                    <option value="thinking">思考</option>
                    <option value="sharing">分享</option>
                    <option value="debate">辩论</option>
                  </select>
                </div>
              </div>
              <div class="form-row">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="newTemplateForm.is_shared" />
                  共享模板（所有用户可见）
                </label>
              </div>
              <div class="form-actions">
                <button class="btn-primary" @click="handleSaveTemplate">保存模板</button>
                <button class="btn-secondary" @click="showCreateTemplate = false">取消</button>
              </div>
            </div>

            <!-- Templates List -->
            <div v-if="!showCreateTemplate" class="templates-list">
              <div v-if="roomTemplates.length === 0" class="empty-state" style="padding: 40px 0">
                <div class="empty-icon">📋</div>
                <div class="empty-text">暂无模板</div>
                <div class="empty-sub">点击「新建模板」创建第一个房间模板</div>
              </div>
              <div
                v-for="tmpl in roomTemplates"
                :key="tmpl.template_id"
                class="template-card"
              >
                <div class="template-card-header">
                  <div class="template-card-title">{{ tmpl.name }}</div>
                  <div class="template-card-actions">
                    <button class="btn-edit" @click="startEditTemplate(tmpl)" title="编辑">✎</button>
                    <button class="btn-edit" @click="handleDeleteTemplate(tmpl.template_id)" title="删除">🗑</button>
                  </div>
                </div>
                <div class="template-card-desc">{{ tmpl.description || '无描述' }}</div>
                <div class="template-card-meta">
                  <span class="template-badge purpose">{{ tmpl.purpose }}</span>
                  <span class="template-badge mode">{{ tmpl.mode }}</span>
                  <span class="template-badge phase">{{ tmpl.default_phase }}</span>
                </div>
                <div class="template-card-footer">
                  <span v-if="tmpl.is_shared" class="shared-badge">共享</span>
                  <button class="btn-primary btn-small" @click="handleCreateRoomFromTemplate(tmpl)">
                    使用此模板创建房间 →
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Plan Templates Modal -->
      <div v-if="showPlanTemplates" class="modal-overlay" @click.self="showPlanTemplates = false">
        <div class="modal-content modal-medium">
          <div class="modal-header">
            <h3>📋 计划模板</h3>
            <div class="modal-header-actions">
              <button class="btn-primary btn-small" @click="showCreatePlanTemplate = true; editingPlanTemplate = null; Object.assign(newPlanTemplateForm, { name: '', description: '', plan_content: {}, tags: [], is_shared: false })">
                + 新建模板
              </button>
              <button class="modal-close" @click="showPlanTemplates = false">✕</button>
            </div>
          </div>
          <div class="modal-body">
            <!-- Create Plan Template Form -->
            <div v-if="showCreatePlanTemplate" class="template-create-form">
              <div class="form-row">
                <label>模板名称 *</label>
                <input v-model="newPlanTemplateForm.name" class="input" placeholder="例如：战略规划模板" />
              </div>
              <div class="form-row">
                <label>描述</label>
                <textarea v-model="newPlanTemplateForm.description" class="input" placeholder="模板用途说明..." rows="2"></textarea>
              </div>
              <div class="form-row">
                <label>标签（逗号分隔）</label>
                <input v-model="newPlanTemplateForm._tagsInput" class="input" placeholder="例如：战略,规划,年度" @blur="newPlanTemplateForm.tags = newPlanTemplateForm._tagsInput.split(',').map(t => t.trim()).filter(Boolean)" @keyup.enter="newPlanTemplateForm.tags = newPlanTemplateForm._tagsInput.split(',').map(t => t.trim()).filter(Boolean)" />
              </div>
              <div class="form-row">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="newPlanTemplateForm.is_shared" />
                  共享模板（所有用户可见）
                </label>
              </div>
              <div class="form-actions">
                <button class="btn-primary" @click="handleSavePlanTemplate">保存模板</button>
                <button class="btn-secondary" @click="showCreatePlanTemplate = false">取消</button>
              </div>
            </div>

            <!-- Plan Templates List -->
            <div v-if="!showCreatePlanTemplate" class="templates-list">
              <div v-if="planTemplates.length === 0" class="empty-state" style="padding: 40px 0">
                <div class="empty-icon">📋</div>
                <div class="empty-text">暂无计划模板</div>
                <div class="empty-sub">点击「新建模板」创建第一个计划模板</div>
              </div>
              <div
                v-for="tmpl in planTemplates"
                :key="tmpl.template_id"
                class="template-card"
              >
                <div class="template-card-header">
                  <div class="template-card-title">{{ tmpl.name }}</div>
                  <div class="template-card-actions">
                    <button class="btn-edit" @click="startEditPlanTemplate(tmpl)" title="编辑">✎</button>
                    <button class="btn-edit" @click="handleDeletePlanTemplate(tmpl.template_id)" title="删除">🗑</button>
                  </div>
                </div>
                <div class="template-card-desc">{{ tmpl.description || '无描述' }}</div>
                <div class="template-card-meta">
                  <span v-if="tmpl.tags && tmpl.tags.length > 0" class="template-badge" v-for="tag in tmpl.tags.slice(0, 3)" :key="tag">{{ tag }}</span>
                </div>
                <div class="template-card-footer">
                  <span v-if="tmpl.is_shared" class="shared-badge">共享</span>
                  <button class="btn-primary btn-small" @click="handleCreatePlanFromTemplate(tmpl)">
                    使用此模板创建计划 →
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 73: Task Templates Modal -->
      <div v-if="showTaskTemplates" class="modal-overlay" @click.self="showTaskTemplates = false">
        <div class="modal-content modal-medium">
          <div class="modal-header">
            <h3>📝 任务模板</h3>
            <div class="modal-header-actions">
              <button class="btn-primary btn-small" @click="showCreateTaskTemplate = true; editingTaskTemplate = null; Object.assign(newTaskTemplateForm, { name: '', description: '', default_title: '', default_description: '', priority: 'medium', difficulty: 'medium', estimated_hours: null, owner_level: null, owner_role: '', tags: [], is_shared: false, _tagsInput: '' })">
                + 新建模板
              </button>
              <button class="modal-close" @click="showTaskTemplates = false">✕</button>
            </div>
          </div>
          <div class="modal-body">
            <!-- Create/Edit Task Template Form -->
            <div v-if="showCreateTaskTemplate" class="template-create-form">
              <div class="form-row">
                <label>模板名称 *</label>
                <input v-model="newTaskTemplateForm.name" class="input" placeholder="例如：开发任务模板" />
              </div>
              <div class="form-row">
                <label>默认任务标题 *</label>
                <input v-model="newTaskTemplateForm.default_title" class="input" placeholder="例如：[功能开发] 用户模块" />
              </div>
              <div class="form-row">
                <label>默认描述</label>
                <textarea v-model="newTaskTemplateForm.default_description" class="input" placeholder="任务默认描述..." rows="2"></textarea>
              </div>
              <div class="form-row-inline">
                <div class="form-row">
                  <label>优先级</label>
                  <select v-model="newTaskTemplateForm.priority" class="input">
                    <option value="low">低</option>
                    <option value="medium">中</option>
                    <option value="high">高</option>
                    <option value="critical">紧急</option>
                  </select>
                </div>
                <div class="form-row">
                  <label>难度</label>
                  <select v-model="newTaskTemplateForm.difficulty" class="input">
                    <option value="low">低</option>
                    <option value="medium">中</option>
                    <option value="high">高</option>
                  </select>
                </div>
              </div>
              <div class="form-row-inline">
                <div class="form-row">
                  <label>预估工时（小时）</label>
                  <input v-model.number="newTaskTemplateForm.estimated_hours" type="number" class="input" min="0" step="0.5" placeholder="0" />
                </div>
                <div class="form-row">
                  <label>负责人层级（L1-L7）</label>
                  <input v-model.number="newTaskTemplateForm.owner_level" type="number" class="input" min="1" max="7" placeholder="3" />
                </div>
              </div>
              <div class="form-row">
                <label>负责人角色</label>
                <input v-model="newTaskTemplateForm.owner_role" class="input" placeholder="例如：前端工程师" />
              </div>
              <div class="form-row">
                <label>标签（逗号分隔）</label>
                <input v-model="newTaskTemplateForm._tagsInput" class="input" placeholder="例如：开发,功能,后端" @blur="newTaskTemplateForm.tags = newTaskTemplateForm._tagsInput.split(',').map(t => t.trim()).filter(Boolean)" @keyup.enter="newTaskTemplateForm.tags = newTaskTemplateForm._tagsInput.split(',').map(t => t.trim()).filter(Boolean)" />
              </div>
              <div class="form-row">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="newTaskTemplateForm.is_shared" />
                  共享模板（所有用户可见）
                </label>
              </div>
              <div class="form-actions">
                <button class="btn-primary" @click="handleSaveTaskTemplate">保存模板</button>
                <button class="btn-secondary" @click="showCreateTaskTemplate = false">取消</button>
              </div>
            </div>

            <!-- Task Templates List -->
            <div v-if="!showCreateTaskTemplate" class="templates-list">
              <div v-if="taskTemplates.length === 0" class="empty-state" style="padding: 40px 0">
                <div class="empty-icon">📝</div>
                <div class="empty-text">暂无任务模板</div>
                <div class="empty-sub">点击「新建模板」创建第一个任务模板</div>
              </div>
              <div
                v-for="tmpl in taskTemplates"
                :key="tmpl.template_id"
                class="template-card"
              >
                <div class="template-card-header">
                  <div class="template-card-title">{{ tmpl.name }}</div>
                  <div class="template-card-actions">
                    <button class="btn-edit" @click="startEditTaskTemplate(tmpl)" title="编辑">✎</button>
                    <button class="btn-edit" @click="handleDeleteTaskTemplate(tmpl.template_id)" title="删除">🗑</button>
                  </div>
                </div>
                <div class="template-card-desc">默认标题：{{ tmpl.default_title || '无' }}</div>
                <div class="template-card-meta">
                  <span class="priority-badge" :class="tmpl.priority || 'medium'">{{ priorityLabel[tmpl.priority] || tmpl.priority || '中' }}</span>
                  <span v-if="tmpl.estimated_hours" class="template-badge">{{ tmpl.estimated_hours }}h</span>
                  <span v-if="tmpl.owner_level" class="template-badge">L{{ tmpl.owner_level }}</span>
                  <span v-if="tmpl.tags && tmpl.tags.length > 0" class="template-badge" v-for="tag in tmpl.tags.slice(0, 3)" :key="tag">{{ tag }}</span>
                </div>
                <div class="template-card-footer">
                  <span v-if="tmpl.is_shared" class="shared-badge">共享</span>
                  <button class="btn-primary btn-small" @click="handleCreateTaskFromTemplate(tmpl)">
                    使用此模板创建任务 →
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- ══════════════════════════════════════════════════════ -->
    <!-- ROOM VIEW                                             -->
    <!-- ══════════════════════════════════════════════════════ -->
    <div v-else class="room">
      <!-- Room Header -->
      <header class="room-header">
        <button class="btn-back" @click="leaveRoom">
          ← 返回计划
        </button>
        <div class="room-title">
          <span class="room-name">{{ currentRoom?.topic || '讨论室' }}</span>
          <span
            class="phase-pill"
            :style="{ background: phaseColors[currentPhase?.current_phase] || '#6b7280' }"
          >
            {{ phaseLabel[currentPhase?.current_phase] || currentPhase?.current_phase || '-' }}
          </span>
        </div>
        <div class="room-meta-header">
          👥 {{ participants.length }}
          <span
            class="ws-status-dot"
            :class="wsStatus"
            :title="wsStatus === 'connected' ? '实时连接' : wsStatus === 'connecting' ? '连接中...' : '离线（自动重连中）'"
          >{{ wsStatus === 'connected' ? '🟢' : wsStatus === 'connecting' ? '🟡' : '🔴' }}</span>
        </div>
        <!-- Notification Bell -->
        <button class="notification-bell" @click.stop="toggleNotifications" title="通知">
          🔔
          <span v-if="unreadCount > 0" class="notification-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
        </button>
        <!-- Escalation Button -->
        <button class="escalate-btn" @click="showEscalationModal = true" title="升级讨论">
          🔺 升级
        </button>
        <!-- Room Tags Button -->
        <button class="room-tags-btn" @click.stop="toggleRoomTags" title="标签管理">
          🏷️ 标签
        </button>
      </header>
      <!-- Room Tags Display -->
      <div v-if="currentRoom?.tags?.length" class="room-header-tags">
        <span v-for="tag in currentRoom.tags" :key="tag" class="header-tag">{{ tag }}</span>
      </div>

      <!-- Room Body -->
      <div class="room-body">
        <!-- Main: Messages + Input -->
        <div class="room-main">
          <!-- Phase Controls -->
          <div v-if="currentPhase?.allowed_next?.length" class="phase-bar">
            <span class="phase-bar-label">推进阶段：</span>
            <button
              v-for="next in currentPhase.allowed_next"
              :key="next"
              class="phase-btn"
              @click="advancePhase(next)"
            >
              → {{ phaseLabel[next] || next }}
            </button>
          </div>

          <!-- Messages -->
          <div class="messages-area">
            <!-- Message Search Bar -->
            <div class="message-search-bar">
              <input
                v-model="messageSearchQuery"
                class="input message-search-input"
                placeholder="搜索消息内容..."
                @keyup.enter="searchMessages"
              />
              <button
                v-if="!messageSearchActive"
                class="btn-primary btn-sm"
                :disabled="!messageSearchQuery.trim()"
                @click="searchMessages"
              >搜索</button>
              <button
                v-else
                class="btn-secondary btn-sm"
                @click="clearMessageSearch"
              >清除</button>
            </div>
            <!-- Search Results Indicator -->
            <div v-if="messageSearchActive" class="search-results-indicator">
              <span v-if="messageSearchLoading">搜索中...</span>
              <span v-else>找到 {{ messageSearchResults.length }} 条结果</span>
            </div>
            <div v-if="!messageSearchActive && messages.length === 0" class="messages-empty">
              暂无发言记录
            </div>
            <div v-if="messageSearchActive && messageSearchResults.length === 0 && !messageSearchLoading" class="messages-empty">
              未找到匹配的消息
            </div>
            <div
              v-for="msg in (messageSearchActive ? messageSearchResults : messages)"
              :key="msg.message_id"
              class="message-row"
            >
              <div class="message-bubble">
                <div class="message-meta">
                  <span class="message-agent">{{ msg.agent_id }}</span>
                  <span class="message-time">{{ new Date(msg.timestamp).toLocaleTimeString() }}</span>
                </div>
                <div class="message-content">{{ msg.content }}</div>
              </div>
            </div>
          </div>

          <!-- Input -->
          <div class="input-bar">
            <input
              v-model="newMessage.content"
              class="input message-input"
              placeholder="输入发言，按 Enter 发送..."
              @keyup.enter="sendMessage"
            />
            <button class="btn-send" @click="sendMessage">发送</button>
          </div>
        </div>

        <!-- Sidebar: Participants + Tasks + Info -->
        <aside class="room-sidebar">
          <div class="sidebar-section">
            <div class="sidebar-title-row">
              <div class="sidebar-title">参与者 ({{ participants.length }})</div>
              <button class="btn-add-participant" @click="showAddParticipant = !showAddParticipant">
                {{ showAddParticipant ? '取消' : '+ 添加' }}
              </button>
            </div>

            <!-- Add Participant Form -->
            <div v-if="showAddParticipant" class="add-participant-form">
              <input
                v-model="newParticipant.name"
                class="input sidebar-input"
                placeholder="姓名"
                @keyup.enter="addNewParticipant"
              />
              <select v-model="newParticipant.role" class="input sidebar-input">
                <option>Member</option>
                <option>Coordinator</option>
                <option>Leader</option>
                <option>Analyst</option>
              </select>
              <div class="level-row">
                <span class="level-label">L</span>
                <input
                  v-model.number="newParticipant.level"
                  type="number"
                  min="1"
                  max="7"
                  class="input sidebar-input level-input"
                />
              </div>
              <button class="btn-primary sidebar-btn" @click="addNewParticipant">添加</button>
            </div>

            <!-- Participant List -->
            <div v-if="participants.length === 0 && !showAddParticipant" class="sidebar-empty">暂无参与者</div>
            <div
              v-for="p in participants"
              :key="p.participant_id"
              class="participant-row"
            >
              <span class="participant-avatar">{{ (p.name || p.agent_id || '?')[0].toUpperCase() }}</span>
              <div class="participant-info">
                <span class="participant-name">{{ p.name || p.agent_id }}</span>
                <span class="participant-role">L{{ p.level }} · {{ p.role }}</span>
              </div>
            </div>
          </div>

          <!-- Tasks Section -->
          <div class="sidebar-section">
            <div class="sidebar-title-row">
              <div class="sidebar-title">任务 ({{ tasks.length }})</div>
              <button class="btn-add-participant" @click="showAddTask = !showAddTask">
                {{ showAddTask ? '取消' : '+ 添加' }}
              </button>
            </div>

            <!-- Task Metrics Summary -->
            <div v-if="taskMetrics" class="task-metrics">
              <span class="metric-item">✅ {{ taskMetrics.completed || 0 }}</span>
              <span class="metric-divider">/</span>
              <span class="metric-item">📋 {{ taskMetrics.total || 0 }}</span>
              <span class="metric-progress">{{ taskMetrics.completion_rate || 0 }}%</span>
            </div>

            <!-- Add Task Form -->
            <div v-if="showAddTask" class="add-task-form">
              <input
                v-model="newTask.title"
                class="input sidebar-input"
                placeholder="任务标题"
                @keyup.enter="handleCreateTask"
              />
              <textarea
                v-model="newTask.description"
                class="input sidebar-input task-desc-input"
                placeholder="任务描述（可选）"
                rows="2"
              ></textarea>
              <select v-model="newTask.priority" class="input sidebar-input">
                <option value="low">低优先级</option>
                <option value="medium">中优先级</option>
                <option value="high">高优先级</option>
                <option value="critical">紧急</option>
              </select>
              <input
                v-model="newTask.assigned_to"
                class="input sidebar-input"
                placeholder="负责人（可选）"
              />
              <button class="btn-primary sidebar-btn" @click="handleCreateTask">创建任务</button>
            </div>

            <!-- Task List -->
            <div v-if="tasks.length === 0 && !showAddTask" class="sidebar-empty">暂无任务</div>
            <div
              v-for="task in tasks"
              :key="task.task_id"
              class="task-row"
            >
              <div class="task-info">
                <div class="task-title">{{ task.title }}</div>
                <div class="task-meta">
                  <span class="task-priority" :class="'priority-' + task.priority">{{ task.priority === 'critical' ? '🔴' : task.priority === 'high' ? '🟠' : task.priority === 'medium' ? '🟡' : '🟢' }}</span>
                  <span class="task-status" :class="'status-' + task.status">{{ task.status === 'completed' ? '✅' : task.status === 'in_progress' ? '🔄' : '⏳' }}</span>
                </div>
              </div>
              <div class="task-progress-bar">
                <div
                  class="task-progress-fill"
                  :style="{ width: (task.progress || 0) + '%' }"
                  :class="'progress-' + task.status"
                ></div>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                :value="task.progress || 0"
                class="task-slider"
                @change="(e) => handleUpdateTaskProgress(task.task_id, Number((e.target as HTMLInputElement).value))"
              />
            </div>
          </div>

          <!-- Debate Section (DEBATE phase only) -->
          <div v-if="currentPhase?.current_phase === 'DEBATE'" class="sidebar-section debate-section">
            <div class="sidebar-title-row">
              <div class="sidebar-title">💬 辩论 ({{ debateState?.all_points?.length || 0 }})</div>
              <div class="debate-title-btns">
                <button class="btn-add-participant" @click="showAddExchange = !showAddExchange">
                  {{ showAddExchange ? '取消' : '+ 交锋' }}
                </button>
                <button class="btn-add-participant" @click="showAddDebatePoint = !showAddDebatePoint">
                  {{ showAddDebatePoint ? '取消' : '+ 议题' }}
                </button>
              </div>
            </div>

            <!-- Add Exchange Form -->
            <div v-if="showAddExchange" class="add-debate-form">
              <select v-model="newExchange.exchange_type" class="input sidebar-input">
                <option value="challenge">🔴 挑战</option>
                <option value="response">🔵 回应</option>
                <option value="evidence">📊 证据</option>
                <option value="update_position">🔄 更新立场</option>
                <option value="consensus_building">🤝 共识建设</option>
              </select>
              <input
                v-model="newExchange.from_agent"
                class="input sidebar-input"
                placeholder="发起人姓名..."
              />
              <input
                v-model="newExchange.target_agent"
                class="input sidebar-input"
                placeholder="目标人（可选）..."
              />
              <textarea
                v-model="newExchange.content"
                class="input sidebar-textarea"
                placeholder="交锋内容..."
                rows="2"
              ></textarea>
              <button
                class="btn-primary sidebar-btn"
                :disabled="exchangeLoading || !newExchange.content.trim() || !newExchange.from_agent.trim()"
                @click="handleSubmitExchange"
              >{{ exchangeLoading ? '提交中...' : '发起交锋' }}</button>
            </div>

            <!-- Consensus Score -->
            <div v-if="debateState" class="consensus-bar">
              <div class="consensus-label">
                共识度
                <span class="consensus-level" :class="'level-' + (debateState.consensus_level === '高共识' ? 'high' : debateState.consensus_level === '中共识' ? 'mid' : debateState.consensus_level === '低共识' ? 'low' : 'dispute')">
                  {{ debateState.consensus_level || '未知' }}
                </span>
              </div>
              <div class="consensus-track">
                <div
                  class="consensus-fill"
                  :style="{ width: ((debateState.consensus_score || 0) * 100) + '%' }"
                  :class="'fill-' + (debateState.consensus_score >= 0.7 ? 'high' : debateState.consensus_score >= 0.5 ? 'mid' : 'low')"
                ></div>
              </div>
              <div class="consensus-score">{{ ((debateState.consensus_score || 0) * 100).toFixed(0) }}%</div>
            </div>

            <!-- Add Debate Point Form -->
            <div v-if="showAddDebatePoint" class="add-debate-form">
              <input
                v-model="newDebatePoint.content"
                class="input sidebar-input"
                placeholder="输入议题内容..."
                @keyup.enter="handleCreateDebatePoint"
              />
              <select v-model="newDebatePoint.point_type" class="input sidebar-input">
                <option value="proposal">提议</option>
                <option value="concern">顾虑</option>
                <option value="question">问题</option>
                <option value="alternative">替代方案</option>
              </select>
              <button class="btn-primary sidebar-btn" @click="handleCreateDebatePoint">发起辩论</button>
            </div>

            <!-- Debate Points List (all_points) -->
            <div v-if="debateState?.all_points?.length" class="debate-points">
              <div class="points-label">📋 所有议题 ({{ debateState.all_points.length }})</div>
              <div
                v-for="pt in debateState.all_points"
                :key="pt.point_id"
                class="debate-point-row"
                :class="{
                  converged: (debateState.converged_points || []).some(cp => cp.point === pt.content),
                  disputed: (debateState.disputed_points || []).some(dp => dp.point === pt.content),
                }"
              >
                <div class="point-header-row">
                  <span class="point-type-badge">{{ pt.point_type || '提议' }}</span>
                  <span class="point-status-badge" :class="{
                    'status-converged': (debateState.converged_points || []).some(cp => cp.point === pt.content),
                    'status-disputed': (debateState.disputed_points || []).some(dp => dp.point === pt.content),
                  }">
                    {{ (debateState.converged_points || []).some(cp => cp.point === pt.content) ? '✅共识' :
                       (debateState.disputed_points || []).some(dp => dp.point === pt.content) ? '⚔️分歧' : '⏳待议' }}
                  </span>
                </div>
                <div class="point-content">{{ pt.content }}</div>
                <div class="point-agents">发起人: {{ pt.created_by || '未知' }}</div>
                <div v-if="(debateState.disputed_points || []).some(dp => dp.point === pt.content)" class="debate-actions">
                  <button
                    class="stance-btn support"
                    :class="{ active: debatePositions[pt.point_id] === 'support' }"
                    @click="handleSubmitDebatePosition(pt.point_id, 'support')"
                  >👍 支持</button>
                  <button
                    class="stance-btn oppose"
                    :class="{ active: debatePositions[pt.point_id] === 'oppose' }"
                    @click="handleSubmitDebatePosition(pt.point_id, 'oppose')"
                  >👎 反对</button>
                </div>
              </div>
            </div>

            <!-- Recent Exchanges -->
            <div v-if="debateState?.recent_exchanges?.length" class="recent-exchanges">
              <div class="points-label">🔄 最近交锋</div>
              <div
                v-for="(ex, idx) in (debateState.recent_exchanges || []).slice(-3)"
                :key="'ex-' + idx"
                class="exchange-row"
              >
                <span class="exchange-type-badge">{{ ex.type === 'challenge' ? '🔴' : ex.type === 'response' ? '🔵' : ex.type === 'evidence' ? '📊' : ex.type === 'update_position' ? '🔄' : '🤝' }}</span>
                <span class="exchange-agent">{{ ex.from_agent }}</span>
                <span v-if="ex.target_agent" class="exchange-target">→ {{ ex.target_agent }}</span>
                <span class="exchange-content">{{ ex.content }}</span>
              </div>
            </div>

            <!-- Advance Round Button -->
            <div v-if="debateState" class="advance-round-row">
              <span class="round-info">第 {{ debateState.round }} / {{ debateState.max_rounds }} 轮</span>
              <button
                class="btn-advance-round"
                :disabled="roundAdvancing || debateState.round >= debateState.max_rounds"
                @click="handleAdvanceRound"
              >{{ roundAdvancing ? '推进中...' : '推进轮次 →' }}</button>
            </div>

            <div v-if="!debateState?.all_points?.length && !showAddDebatePoint" class="sidebar-empty">
              暂无议题，发起第一个辩论议题
            </div>
          </div>

          <!-- Problem Management Panel (problem phases only) -->
          <div v-if="isProblemPhase" class="sidebar-section problem-section">
            <div class="sidebar-title-row">
              <div class="sidebar-title">⚠️ 问题管理 ({{ currentProblem?.issue_number || '' }})</div>
              <div class="problem-phase-badge" :class="'phase-' + (currentPhase?.current_phase || '').toLowerCase()">
                {{ phaseLabel[currentPhase?.current_phase] || currentPhase?.current_phase }}
              </div>
            </div>

            <!-- Problem Info (all phases) -->
            <div v-if="currentProblem" class="problem-info">
              <div class="info-row">
                <span class="info-label">问题标题</span>
                <span class="info-value">{{ currentProblem.title }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">类型</span>
                <span class="info-value">{{ currentProblem.type }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">严重程度</span>
                <span class="severity-badge" :class="'severity-' + (currentProblem.severity || 'medium')">
                  {{ currentProblem.severity }}
                </span>
              </div>
              <div class="info-row">
                <span class="info-label">报告人</span>
                <span class="info-value">{{ currentProblem.detected_by }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">发现时间</span>
                <span class="info-value">{{ currentProblem.detected_at ? new Date(currentProblem.detected_at).toLocaleString() : '-' }}</span>
              </div>
              <div v-if="currentProblem.description" class="problem-desc">
                {{ currentProblem.description }}
              </div>
            </div>

            <!-- PROBLEM_DETECTED: Report form + next step -->
            <div v-if="currentPhase?.current_phase === 'PROBLEM_DETECTED'" class="problem-phase-content">
              <div class="problem-hint">问题已记录，等待开始分析</div>
              <button class="btn-primary sidebar-btn" @click="async () => {
                if (!currentRoom.value) return
                problemActionLoading = true
                try {
                  await api.post(`/problems/${currentProblem?.issue_id}/analyze`, { root_cause: '待分析' })
                  const phaseRes = await getPhase(currentRoom.value.room_id)
                  currentPhase.value = phaseRes.data
                  await loadProblemState(currentRoom.value.room_id, currentPlan.value?.plan_id)
                } catch {}
                problemActionLoading = false
              }">开始分析</button>
            </div>

            <!-- PROBLEM_ANALYSIS: Analysis form -->
            <div v-if="currentPhase?.current_phase === 'PROBLEM_ANALYSIS'" class="problem-phase-content">
              <div class="problem-section-title">📊 根因分析</div>
              <textarea v-model="analyzeForm.root_cause" class="input sidebar-input problem-textarea" placeholder="分析问题的根本原因..." rows="3"></textarea>
              <div class="form-row">
                <label class="form-label">置信度</label>
                <input v-model.number="analyzeForm.root_cause_confidence" type="range" min="0" max="1" step="0.1" class="problem-slider" />
                <span class="slider-value">{{ (analyzeForm.root_cause_confidence * 100).toFixed(0) }}%</span>
              </div>
              <input v-model="analyzeForm.impact_scope" class="input sidebar-input" placeholder="影响范围" />
              <textarea v-model="analyzeForm.progress_impact" class="input sidebar-input problem-textarea" placeholder="进度影响..." rows="2"></textarea>
              <div class="problem-section-title" style="margin-top:12px">💡 解决方案选项</div>
              <div v-for="(opt, idx) in analyzeForm.solution_options" :key="'opt-' + idx" class="solution-option">
                <input v-model="opt.description" class="input" placeholder="方案描述" />
                <div class="option-pros-cons">
                  <input v-model="opt.pros" class="input" placeholder="优点 (逗号分隔)" />
                  <input v-model="opt.cons" class="input" placeholder="缺点 (逗号分隔)" />
                </div>
              </div>
              <button class="btn-add-participant" @click="analyzeForm.solution_options.push({ description: '', pros: [], cons: [] })">+ 添加方案</button>
              <button class="btn-primary sidebar-btn" :disabled="problemActionLoading" @click="handleAnalyzeProblem">
                {{ problemActionLoading ? '提交中...' : '提交分析' }}
              </button>
            </div>

            <!-- PROBLEM_DISCUSSION: Discussion form -->
            <div v-if="currentPhase?.current_phase === 'PROBLEM_DISCUSSION'" class="problem-phase-content">
              <div class="problem-section-title">💬 问题讨论</div>
              <div v-if="problemAnalysis" class="analysis-summary">
                <div class="info-row"><span class="info-label">根因</span><span class="info-value">{{ problemAnalysis.root_cause }}</span></div>
                <div class="info-row"><span class="info-label">置信度</span><span class="info-value">{{ ((problemAnalysis.root_cause_confidence || 0) * 100).toFixed(0) }}%</span></div>
              </div>
              <!-- Solution Voting -->
              <div v-if="problemAnalysis?.solution_options?.length" class="solutions-voting">
                <div class="problem-section-title">投票选择方案</div>
                <div v-for="(opt, idx) in problemAnalysis.solution_options" :key="'so-' + idx" class="solution-vote-row">
                  <span class="solution-desc">{{ opt.description }}</span>
                  <button
                    class="vote-btn"
                    :class="{ selected: discussForm.votes[currentUser.name] === String(idx) }"
                    @click="discussForm.votes[currentUser.name] = String(idx)"
                  >{{ discussForm.votes[currentUser.name] === String(idx) ? '✅ 已投' : '投票' }}</button>
                </div>
              </div>
              <button class="btn-primary sidebar-btn" :disabled="problemActionLoading" @click="handleDiscussProblem">
                {{ problemActionLoading ? '提交中...' : '提交讨论结果' }}
              </button>
            </div>

            <!-- PLAN_UPDATE: Plan update status -->
            <div v-if="currentPhase?.current_phase === 'PLAN_UPDATE'" class="problem-phase-content">
              <div class="problem-section-title">📋 计划更新</div>
              <div class="problem-hint">分析完成，正在更新计划</div>
              <input v-model="planUpdateForm.new_version" class="input sidebar-input" placeholder="新版本号 (如 v1.1)" />
              <select v-model="planUpdateForm.update_type" class="input sidebar-input">
                <option value="problem_recovery">问题恢复</option>
                <option value="plan_revision">计划修订</option>
                <option value="scope_change">范围变更</option>
                <option value="resource_adjustment">资源调整</option>
              </select>
              <textarea v-model="planUpdateForm.description" class="input sidebar-input problem-textarea" placeholder="更新描述..." rows="3"></textarea>
              <button class="btn-primary sidebar-btn" :disabled="problemActionLoading" @click="handleUpdatePlan">
                {{ problemActionLoading ? '更新中...' : '确认计划更新' }}
              </button>
            </div>

            <!-- RESUMING: Resume execution -->
            <div v-if="currentPhase?.current_phase === 'RESUMING'" class="problem-phase-content">
              <div class="problem-section-title">▶️ 恢复执行</div>
              <div class="problem-hint">问题已解决，准备恢复执行</div>
              <input v-model="resumingForm.new_version" class="input sidebar-input" placeholder="版本号" />
              <input v-model.number="resumingForm.resuming_from_task" type="number" class="input sidebar-input" placeholder="从第N个任务恢复" />
              <input v-model="resumingForm.checkpoint" class="input sidebar-input" placeholder="检查点描述" />
              <button class="btn-primary sidebar-btn" :disabled="problemActionLoading" @click="handleResumeExecution">
                {{ problemActionLoading ? '恢复中...' : '恢复执行 →' }}
              </button>
            </div>

            <!-- Report Problem Button (for EXECUTING rooms) -->
            <div v-if="currentPhase?.current_phase === 'EXECUTING'" class="problem-report-area">
              <button class="btn-report-problem" @click="showReportProblem = !showReportProblem">
                ⚠️ 报告问题
              </button>
              <div v-if="showReportProblem" class="report-problem-form">
                <input v-model="reportProblemForm.title" class="input sidebar-input" placeholder="问题标题 *" />
                <textarea v-model="reportProblemForm.description" class="input sidebar-input problem-textarea" placeholder="问题描述..." rows="3"></textarea>
                <select v-model="reportProblemForm.type" class="input sidebar-input">
                  <option value="execution_blocker">执行阻塞</option>
                  <option value="resource_shortage">资源短缺</option>
                  <option value="scope_creep">范围蔓延</option>
                  <option value="quality_issue">质量问题</option>
                  <option value="risk_realized">风险实现</option>
                  <option value="other">其他</option>
                </select>
                <select v-model="reportProblemForm.severity" class="input sidebar-input">
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                  <option value="critical">严重</option>
                </select>
                <input v-model="reportProblemForm.progress_delay" class="input sidebar-input" placeholder="预计进度延迟" />
                <button class="btn-primary sidebar-btn" :disabled="reportProblemLoading" @click="handleReportProblem">
                  {{ reportProblemLoading ? '提交中...' : '提交问题报告' }}
                </button>
              </div>
            </div>
          </div>

          <!-- Hierarchical Review Panel (HIERARCHICAL_REVIEW phase) -->
          <div v-if="currentPhase?.current_phase === 'HIERARCHICAL_REVIEW'" class="sidebar-section hierarchical-review-section">
            <div class="sidebar-title-row">
              <div class="sidebar-title">🏛️ 层级评审</div>
              <div class="phase-badge-sm" style="background:#6366f1">评审中</div>
            </div>

            <!-- Consensus Summary from Convergence -->
            <div v-if="hierarchicalReviewData?.consensus_points?.length" class="review-consensus-block">
              <div class="review-section-label">📌 收敛共识点 ({{ hierarchicalReviewData.consensus_points.length }})</div>
              <div v-for="(cp, idx) in hierarchicalReviewData.consensus_points" :key="idx" class="consensus-point-chip">
                {{ cp.description || cp.point || JSON.stringify(cp) }}
              </div>
            </div>

            <!-- Hierarchy Context / Approval Status -->
            <div v-if="hierarchicalReviewData?.hierarchy_context" class="review-hierarchy-block">
              <div class="review-section-label">📊 层级审批链</div>
              <div class="approval-chain">
                <div
                  v-for="lvl in [7,6,5,4,3,2,1]"
                  :key="lvl"
                  class="approval-level-row"
                  :class="{ 'is-current': hierarchicalReviewData.hierarchy_context?.current_level === lvl }"
                >
                  <span class="level-num">L{{ lvl }}</span>
                  <span class="level-name">{{ hierarchicalReviewData.hierarchy_context?.approval_summary?.levels?.[lvl]?.level_label || '—' }}</span>
                  <span
                    class="approval-status-chip"
                    :class="'status-' + (hierarchicalReviewData.hierarchy_context?.approval_summary?.levels?.[lvl]?.status || 'pending')"
                  >
                    {{
                      hierarchicalReviewData.hierarchy_context?.approval_summary?.levels?.[lvl]?.status === 'approved' ? '✅' :
                      hierarchicalReviewData.hierarchy_context?.approval_summary?.levels?.[lvl]?.status === 'rejected' ? '❌' :
                      hierarchicalReviewData.hierarchy_context?.approval_summary?.levels?.[lvl]?.status === 'pending' ? '⏳' : '—'
                    }}
                  </span>
                </div>
              </div>
            </div>

            <!-- No hierarchy context yet -->
            <div v-else-if="!hierarchicalReviewData?.hierarchy_context" class="review-no-context">
              <div class="review-hint">评审上下文加载中...</div>
              <div class="review-hint-sub">层级审批链信息将在刷新后显示</div>
            </div>

            <!-- Review Notes -->
            <div class="review-notes-block">
              <div class="review-section-label">📝 评审备注</div>
              <textarea
                v-model="reviewNotes[currentPhase?.room_id || '']"
                class="input sidebar-input review-textarea"
                placeholder="填写评审意见..."
                rows="3"
              ></textarea>
            </div>
          </div>

          <!-- Converging Panel (CONVERGING phase) -->
          <div v-if="currentPhase?.current_phase === 'CONVERGING'" class="sidebar-section converging-section">
            <div class="sidebar-title-row">
              <div class="sidebar-title">🔄 收敛阶段</div>
              <div class="phase-badge-sm" style="background:#f59e0b">收敛中</div>
            </div>

            <!-- Consensus Points from DEBATE phase -->
            <div v-if="hierarchicalReviewData?.consensus_points?.length" class="converging-points-block">
              <div class="review-section-label">✅ 已收敛议题 ({{ hierarchicalReviewData.consensus_points.length }})</div>
              <div v-for="(cp, idx) in hierarchicalReviewData.consensus_points" :key="idx" class="consensus-point-item">
                <span class="point-check">✅</span>
                <span class="point-desc">{{ cp.description || cp.point || JSON.stringify(cp) }}</span>
              </div>
            </div>
            <div v-else class="converging-no-points">
              <div class="review-hint">暂无收敛共识点</div>
              <div class="review-hint-sub">辩论阶段的共识议题将在此处显示</div>
            </div>

            <!-- Converging hint -->
            <div class="converging-hint-block">
              <div class="review-section-label">💡 下一步</div>
              <div class="review-hint">收敛完成后，议题将提交至层级评审 (HIERARCHICAL_REVIEW) 或直接进入决策 (DECISION) 阶段</div>
            </div>
          </div>

          <!-- Step 63: Phase Timeline -->
          <div v-if="phaseTimeline.length > 0" class="sidebar-section phase-timeline-section">
            <div class="sidebar-title-row">
              <div class="sidebar-title">⏱ 阶段时间线</div>
              <span class="phase-timeline-count">{{ phaseTimeline.length }} 个阶段</span>
            </div>
            <div class="phase-timeline-list">
              <div
                v-for="(entry, idx) in phaseTimeline"
                :key="entry.entry_id || idx"
                class="timeline-entry"
                :class="{
                  'timeline-current': idx === phaseTimeline.length - 1 && !entry.exited_at,
                  'timeline-completed': entry.exited_at,
                }"
              >
                <div class="timeline-phase-dot"></div>
                <div class="timeline-content">
                  <div class="timeline-phase-name">
                    {{ phaseLabel[entry.phase] || entry.phase }}
                  </div>
                  <div class="timeline-time">
                    <span class="timeline-enter">进 {{ formatTime(entry.entered_at) }}</span>
                    <span v-if="entry.exited_at" class="timeline-exit">
                      出 {{ formatTime(entry.exited_at) }}
                    </span>
                    <span v-else class="timeline-running">进行中</span>
                  </div>
                  <div v-if="entry.duration_secs !== null" class="timeline-duration">
                    ⏱ {{ formatDuration(entry.duration_secs) }}
                  </div>
                  <div v-if="entry.exited_via" class="timeline-via">
                    → {{ phaseLabel[entry.exited_via] || entry.exited_via }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Step 64: Room Activity Stream -->
          <div class="sidebar-section activity-stream-section">
            <div class="sidebar-title-row">
              <div class="sidebar-title">📋 活动流 ({{ roomActivityStream.length }})</div>
              <button
                class="btn-add-participant"
                :style="{ fontSize: '0.7rem', padding: '2px 8px' }"
                @click="showActivityStream = !showActivityStream"
              >
                {{ showActivityStream ? '收起' : '展开' }}
              </button>
            </div>
            <div v-if="showActivityStream" class="activity-stream-list">
              <div v-if="roomActivityStream.length === 0" class="sidebar-empty">暂无活动记录</div>
              <div
                v-for="evt in roomActivityStream"
                :key="evt.id"
                class="stream-entry"
                :class="'stream-' + evt.event_type"
              >
                <span class="stream-icon">{{ evt.icon }}</span>
                <div class="stream-body">
                  <div class="stream-actor">{{ evt.actor }}</div>
                  <div class="stream-detail">{{ evt.detail }}</div>
                  <div class="stream-time">{{ new Date(evt.timestamp).toLocaleTimeString() }}</div>
                </div>
              </div>
            </div>
            <!-- Compact preview when collapsed -->
            <div v-else class="activity-stream-preview">
              <div
                v-for="evt in roomActivityStream.slice(0, 3)"
                :key="evt.id"
                class="stream-preview-row"
              >
                <span class="stream-icon-sm">{{ evt.icon }}</span>
                <span class="stream-preview-text">{{ evt.actor }}: {{ evt.detail }}</span>
              </div>
              <div v-if="roomActivityStream.length > 3" class="stream-preview-more">
                还有 {{ roomActivityStream.length - 3 }} 条活动
              </div>
            </div>
          </div>

          <div class="sidebar-section">
            <div class="sidebar-title">房间信息</div>
            <div class="info-row">
              <span class="info-label">房间号</span>
              <span class="info-value">{{ currentRoom?.room_number }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">当前阶段</span>
              <span class="info-value">{{ phaseLabel[currentPhase?.current_phase] || '-' }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">模式</span>
              <span class="info-value">{{ currentRoom?.mode || 'hierarchical' }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">版本</span>
              <span class="info-value">{{ currentRoom?.version || currentRoom?.current_version || '-' }}</span>
            </div>
          </div>
        </aside>
      </div>
    </div>

    <!-- 签收圣旨 Modal -->
    <div v-if="showAckForm" class="modal-overlay" @click.self="showAckForm = false">
      <div class="modal-content ack-modal">
        <div class="modal-header">
          <h3>确认收到圣旨</h3>
          <button class="modal-close" @click="showAckForm = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>签收人 *</label>
            <input v-model="ackForm.acknowledged_by" placeholder="请输入姓名" @keyup.enter="handleAcknowledgeEdict" />
          </div>
          <div class="form-group">
            <label>层级 (L1-L7) *</label>
            <input type="number" v-model.number="ackForm.level" min="1" max="7" />
          </div>
          <div class="form-group">
            <label>备注</label>
            <textarea v-model="ackForm.comment" placeholder="可选" rows="2"></textarea>
          </div>
          <div class="modal-actions">
            <button class="btn-primary" @click="handleAcknowledgeEdict">确认签收</button>
            <button class="btn-secondary" @click="showAckForm = false">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Task Detail Modal -->
    <div v-if="showTaskDetail" class="modal-overlay" @click.self="showTaskDetail = false">
      <div class="modal-content task-detail-modal">
        <div class="modal-header">
          <h3>{{ selectedTaskForDetail?.title || '任务详情' }}</h3>
          <button class="modal-close" @click="showTaskDetail = false">×</button>
        </div>
        <div class="task-detail-body">
          <!-- Task Meta -->
          <div class="task-detail-meta">
            <div class="task-meta-item">
              <span class="meta-label">状态</span>
              <span class="status-chip" :class="'s-' + selectedTaskForDetail?.status">
                {{ selectedTaskForDetail?.status === 'completed' ? '✅ 完成' : selectedTaskForDetail?.status === 'in_progress' ? '🔄 进行中' : selectedTaskForDetail?.status === 'blocked' ? '🚫 阻塞' : '⏳ 待处理' }}
              </span>
            </div>
            <div class="task-meta-item">
              <span class="meta-label">优先级</span>
              <span>{{ selectedTaskForDetail?.priority === 'critical' ? '🔴 紧急' : selectedTaskForDetail?.priority === 'high' ? '🟠 高' : selectedTaskForDetail?.priority === 'medium' ? '🟡 中' : '🟢 低' }}</span>
            </div>
            <div class="task-meta-item">
              <span class="meta-label">进度</span>
              <span>{{ selectedTaskForDetail?.progress || 0 }}%</span>
            </div>
            <div class="task-meta-item" v-if="selectedTaskForDetail?.assigned_to">
              <span class="meta-label">负责人</span>
              <span>{{ selectedTaskForDetail?.assigned_to }}</span>
            </div>
            <div class="task-meta-item" v-if="selectedTaskForDetail?.deadline">
              <span class="meta-label">截止日期</span>
              <span>{{ new Date(selectedTaskForDetail.deadline).toLocaleDateString() }}</span>
            </div>
            <div class="task-meta-item" v-if="selectedTaskForDetail?.owner_name">
              <span class="meta-label">创建人</span>
              <span>{{ selectedTaskForDetail?.owner_name }}</span>
            </div>
          </div>
          <div v-if="selectedTaskForDetail?.description" class="task-detail-desc">
            <div class="detail-section-title">描述</div>
            <p>{{ selectedTaskForDetail?.description }}</p>
          </div>

          <!-- Tabs: Comments / Checkpoints / Time Tracking -->
          <div class="task-detail-tabs">
            <button
              :class="{ active: taskDetailActiveTab === 'comments' }"
              @click="taskDetailActiveTab = 'comments'"
            >
              💬 评论 ({{ taskDetailComments.length }})
            </button>
            <button
              :class="{ active: taskDetailActiveTab === 'checkpoints' }"
              @click="taskDetailActiveTab = 'checkpoints'"
            >
              🏁 检查点 ({{ taskDetailCheckpoints.length }})
            </button>
            <button
              :class="{ active: taskDetailActiveTab === 'timetracking' }"
              @click="taskDetailActiveTab = 'timetracking'"
            >
              ⏱ 工时 ({{ taskTimeEntries.length }})
            </button>
          </div>

          <!-- Comments Tab -->
          <div v-if="taskDetailActiveTab === 'comments'" class="task-detail-tab-content">
            <div v-if="taskDetailLoading" class="loading-state">加载中...</div>
            <div v-else-if="taskDetailComments.length === 0" class="empty-mini">暂无评论</div>
            <div v-else class="comment-list">
              <div v-for="comment in taskDetailComments" :key="comment.comment_id" class="comment-item">
                <div class="comment-header">
                  <span class="comment-author">{{ comment.author_name || '匿名' }}</span>
                  <span class="comment-time">{{ new Date(comment.created_at || comment.timestamp || Date.now()).toLocaleString() }}</span>
                </div>
                <div class="comment-content">{{ comment.content }}</div>
              </div>
            </div>
            <!-- Add Comment Form -->
            <div class="add-comment-form">
              <input
                v-model="newCommentForm.author_name"
                class="input"
                placeholder="你的名字（可选）"
              />
              <textarea
                v-model="newCommentForm.content"
                class="input"
                placeholder="添加评论..."
                rows="2"
                @keyup.enter.exact.prevent="handleCreateComment"
              ></textarea>
              <button class="btn-primary" @click="handleCreateComment" :disabled="!newCommentForm.content.trim()">
                发表
              </button>
            </div>
          </div>

          <!-- Checkpoints Tab -->
          <div v-if="taskDetailActiveTab === 'checkpoints'" class="task-detail-tab-content">
            <div v-if="taskDetailLoading" class="loading-state">加载中...</div>
            <div v-else-if="taskDetailCheckpoints.length === 0" class="empty-mini">暂无检查点</div>
            <div v-else class="checkpoint-list">
              <div v-for="cp in taskDetailCheckpoints" :key="cp.checkpoint_id" class="checkpoint-item">
                <span class="checkpoint-status-icon">
                  {{ cp.status === 'completed' ? '✅' : cp.status === 'in_progress' ? '🔄' : '⏳' }}
                </span>
                <span class="checkpoint-name">{{ cp.name }}</span>
                <span class="checkpoint-status-label">{{ cp.status === 'completed' ? '已完成' : cp.status === 'in_progress' ? '进行中' : '待处理' }}</span>
              </div>
            </div>
            <!-- Add Checkpoint Form -->
            <div class="add-checkpoint-form">
              <input
                v-model="newCheckpointForm.name"
                class="input"
                placeholder="检查点名称"
                @keyup.enter.exact.prevent="handleCreateCheckpoint"
              />
              <select v-model="newCheckpointForm.status" class="input">
                <option value="pending">待处理</option>
                <option value="in_progress">进行中</option>
                <option value="completed">已完成</option>
              </select>
              <button class="btn-primary" @click="handleCreateCheckpoint" :disabled="!newCheckpointForm.name.trim()">
                添加
              </button>
            </div>
          </div>

          <!-- Time Tracking Tab (Step 65) -->
          <div v-if="taskDetailActiveTab === 'timetracking'" class="task-detail-tab-content">
            <!-- Time Summary -->
            <div v-if="taskTimeSummary" class="time-summary-bar">
              <div class="time-summary-item">
                <div class="time-summary-val">{{ taskTimeSummary.total_hours || 0 }}h</div>
                <div class="time-summary-label">总工时</div>
              </div>
              <div class="time-summary-item">
                <div class="time-summary-val">{{ taskTimeSummary.entry_count || 0 }}</div>
                <div class="time-summary-label">记录数</div>
              </div>
              <div class="time-summary-item">
                <div class="time-summary-val">{{ taskTimeSummary.contributor_count || 0 }}</div>
                <div class="time-summary-label">贡献者</div>
              </div>
              <div class="time-summary-item" v-if="selectedTaskForDetail?.estimated_hours">
                <div class="time-summary-val">{{ ((taskTimeSummary.total_hours / selectedTaskForDetail.estimated_hours) * 100).toFixed(0) }}%</div>
                <div class="time-summary-label">预估比例</div>
              </div>
            </div>

            <!-- Time Entries List -->
            <div v-if="taskTimeLoading" class="loading-state">加载中...</div>
            <div v-else-if="taskTimeEntries.length === 0" class="empty-mini">暂无工时记录</div>
            <div v-else class="time-entry-list">
              <div v-for="entry in taskTimeEntries" :key="entry.time_entry_id" class="time-entry-item">
                <div class="time-entry-header">
                  <span class="time-entry-user">{{ entry.user_name || 'Guest' }}</span>
                  <span class="time-entry-hours">{{ entry.hours }}h</span>
                  <button class="btn-delete-sm" @click="handleDeleteTimeEntry(entry.time_entry_id)" title="删除">✕</button>
                </div>
                <div class="time-entry-desc">{{ entry.description || '无描述' }}</div>
                <div class="time-entry-date">{{ new Date(entry.logged_at || entry.created_at || Date.now()).toLocaleString() }}</div>
              </div>
            </div>

            <!-- Add Time Entry Form -->
            <div class="time-entry-form">
              <div class="time-entry-form-row">
                <input
                  v-model="newTimeEntryForm.user_name"
                  class="input"
                  placeholder="姓名（可选）"
                />
                <input
                  v-model="newTimeEntryForm.hours"
                  class="input"
                  type="number"
                  min="0.1"
                  max="24"
                  step="0.1"
                  placeholder="工时 *"
                  @keyup.enter.exact.prevent="handleCreateTimeEntry"
                />
              </div>
              <input
                v-model="newTimeEntryForm.description"
                class="input"
                placeholder="工作描述"
                @keyup.enter.exact.prevent="handleCreateTimeEntry"
              />
              <button
                class="btn-primary"
                @click="handleCreateTimeEntry"
                :disabled="!newTimeEntryForm.hours || parseFloat(newTimeEntryForm.hours) <= 0"
              >
                记录工时
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* ─── Reset & Base ─── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; }

body {
  background: #0a0a0f;
  color: #e2e8f0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 15px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

/* ─── App Shell ─── */
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ─── Header ─── */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  height: 60px;
  background: #111118;
  border-bottom: 1px solid #1e1e2e;
  position: sticky;
  top: 0;
  z-index: 100;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}
.logo-icon { font-size: 1.5rem; }
.logo-text { font-size: 1.2rem; font-weight: 700; color: #fff; }
.logo-version {
  font-size: 0.7rem;
  background: #2d2d3d;
  color: #8b8ba0;
  padding: 2px 6px;
  border-radius: 4px;
}

/* ─── Buttons ─── */
.btn-primary {
  background: #5b5bd6;
  border: none;
  color: #fff;
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-primary:hover { background: #6e6edb; }
.btn-secondary {
  background: transparent;
  border: 1px solid #3f3f5a;
  color: #a0a0c0;
  padding: 6px 16px;
  border-radius: 8px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-secondary:hover { border-color: #5b5bd6; color: #a0a0ff; }
.btn-sm { padding: 4px 12px; font-size: 0.8rem; }

.btn-copy-plan {
  background: transparent;
  border: 1px solid #2d4a2d;
  color: #6bcf6b;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
  margin-left: auto;
}
.btn-copy-plan:hover { border-color: #4ade80; color: #86efac; background: rgba(74, 222, 128, 0.1); }

.btn-back {
  background: transparent;
  border: 1px solid #2d2d3d;
  color: #8b8ba0;
  padding: 6px 16px;
  border-radius: 8px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-back:hover { border-color: #5b5bd6; color: #8b8ba0; }

.btn-send {
  background: #5b5bd6;
  border: none;
  color: #fff;
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
}
.btn-send:hover { background: #6e6edb; }

/* ─── Home/Dashboard ─── */
.home {
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 24px 48px;
  width: 100%;
}

/* ─── Create Panel ─── */
.create-panel {
  padding: 20px 0 8px;
  animation: slideDown 0.2s ease;
}
@keyframes slideDown {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}
.create-inner {
  background: #13131f;
  border: 1px solid #2d2d4a;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ─── Search Bar ─── */
.search-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 0 16px;
}
.search-input {
  flex: 1;
  background: #13131f;
  border: 1px solid #2d2d4a;
  border-radius: 10px;
  padding: 10px 16px;
  color: #e2e8f0;
  font-size: 0.95rem;
}
.search-input:focus { border-color: #5b5bd6; outline: none; }
.search-input::placeholder { color: #4a4a6a; }
.plan-count { color: #4a4a6a; font-size: 0.85rem; white-space: nowrap; }

/* ─── Dashboard Stats Bar ─── */
.dashboard-stats-bar {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  background: #13131f;
  border: 1px solid #2d2d4a;
  border-radius: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  align-items: flex-start;
}
.stat-card {
  background: #1a1a28;
  border: 1px solid #2d2d4a;
  border-radius: 10px;
  padding: 10px 16px;
  min-width: 80px;
  text-align: center;
}
.stat-card-wide {
  flex: 1;
  min-width: 200px;
  text-align: left;
}
.stat-value {
  font-size: 1.6rem;
  font-weight: 700;
  color: #7c7cff;
  line-height: 1;
}
.stat-label {
  font-size: 0.75rem;
  color: #6b7280;
  margin-top: 4px;
}
.phase-bars {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
}
.phase-bar-item {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #2d2d4a;
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 0.75rem;
}
.phase-bar-label {
  color: #a0a0c0;
}
.phase-bar-count {
  color: #7c7cff;
  font-weight: 600;
}

.sort-controls {
  display: flex;
  gap: 4px;
  background: #13131f;
  border: 1px solid #2d2d4a;
  border-radius: 8px;
  padding: 2px;
}
.sort-btn {
  background: transparent;
  border: none;
  color: #4a4a6a;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s;
}
.sort-btn.active {
  background: #2d2d4a;
  color: #a0a0c0;
}

/* ─── Input ─── */
.input {
  background: #1a1a28;
  border: 1px solid #2d2d4a;
  border-radius: 8px;
  color: #e2e8f0;
  padding: 10px 14px;
  font-size: 0.95rem;
  width: 100%;
  transition: border-color 0.15s;
}
.input:focus { outline: none; border-color: #5b5bd6; }
.input::placeholder { color: #4a4a6a; }

/* ─── Plan Grid ─── */
.plans-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.plan-card {
  background: #13131f;
  border: 1px solid #1e1e2e;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.plan-card:hover {
  border-color: #5b5bd6;
  background: #16162a;
  transform: translateY(-2px);
}

.plan-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.plan-card-title {
  color: #fff;
  font-size: 1rem;
  font-weight: 600;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.plan-card-topic {
  color: #6a6a8a;
  font-size: 0.85rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.plan-number { color: #4a4a6a; font-size: 0.75rem; }
.version-badge {
  background: #2d2d4a;
  color: #8b8ba0;
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: 4px;
}
.plan-card-metrics {
  display: flex;
  gap: 8px;
}
.metric-chip {
  background: #1e1e2e;
  color: #6a6a8a;
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: 4px;
}
.plan-card-footer {
  display: flex;
  justify-content: space-between;
  color: #4a4a6a;
  font-size: 0.8rem;
}

/* ─── Phase Pill ─── */
.phase-pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 0.72rem;
  color: #fff;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.phase-pill.small {
  font-size: 0.65rem;
  padding: 2px 7px;
}

/* ─── Empty State ─── */
.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 80px 20px;
  color: #4a4a6a;
}
.empty-icon { font-size: 3rem; margin-bottom: 12px; }
.empty-text { font-size: 1.1rem; color: #6a6a8a; margin-bottom: 8px; }
.empty-sub { font-size: 0.85rem; }

/* ─── Plan Detail ─── */
.plan-detail {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.plan-header-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  overflow: hidden;
}
.plan-header-title {
  color: #fff;
  font-weight: 600;
  font-size: 1rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ─── Plan Tabs ─── */
.plan-tabs {
  display: flex;
  gap: 0;
  padding: 0 24px;
  background: #0e0e18;
  border-bottom: 1px solid #1e1e2e;
}
.plan-tab {
  background: transparent;
  border: none;
  color: #6a6a8a;
  padding: 12px 24px;
  font-size: 0.9rem;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}
.plan-tab:hover { color: #a0a0c0; }
.plan-tab.active {
  color: #fff;
  border-bottom-color: #5b5bd6;
}

/* ─── Plan Content ─── */
.plan-content {
  flex: 1;
  padding: 24px;
  max-width: 1100px;
  margin: 0 auto;
  width: 100%;
}

/* ─── Overview Grid ─── */
.overview-grid {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 16px;
}

.overview-card {
  background: #13131f;
  border: 1px solid #1e1e2e;
  border-radius: 12px;
  padding: 20px;
}
.overview-card-title {
  color: #4a4a6a;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 12px;
}
.overview-card.rooms-summary,
.overview-card.tasks-summary {
  grid-column: 1 / -1;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid #1e1e2e;
}
.info-row:last-child { border-bottom: none; }
.info-label { color: #4a4a6a; font-size: 0.85rem; }
.info-value { color: #a0a0c0; font-size: 0.85rem; }

.metrics-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.metric-box {
  background: #1a1a28;
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}
.metric-val {
  font-size: 1.5rem;
  font-weight: 700;
  color: #fff;
}
.metric-val.completed { color: #22c55e; }
.metric-val.rate { color: #3b82f6; }
.metric-key {
  font-size: 0.72rem;
  color: #6a6a8a;
  margin-top: 4px;
}

/* ─── Room Mini Rows ─── */
.room-mini-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid #1e1e2e;
  cursor: pointer;
}
.room-mini-row:last-child { border-bottom: none; }
.room-mini-row:hover .room-mini-topic { color: #a0a0ff; }
.room-mini-topic {
  flex: 1;
  color: #d0d0e8;
  font-size: 0.85rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.15s;
}
.room-mini-num { color: #4a4a6a; font-size: 0.75rem; }

.see-more {
  color: #6e6edb;
  font-size: 0.8rem;
  padding-top: 10px;
  cursor: pointer;
  text-align: center;
}

/* ─── Task Mini Rows ─── */
.task-mini-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid #1e1e2e;
}
.task-mini-row:last-child { border-bottom: none; }
.task-mini-title {
  color: #d0d0e8;
  font-size: 0.85rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.task-mini-progress { color: #6a6a8a; font-size: 0.8rem; }

/* ─── Plan Room Cards ─── */
.rooms-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}
.plan-room-card {
  background: #13131f;
  border: 1px solid #1e1e2e;
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.plan-room-card:hover {
  border-color: #5b5bd6;
  transform: translateY(-2px);
}
.plan-room-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.plan-room-topic {
  color: #fff;
  font-weight: 500;
  font-size: 0.95rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.plan-room-meta {
  display: flex;
  gap: 12px;
  color: #4a4a6a;
  font-size: 0.8rem;
}

/* ─── Room Hierarchy UI ─── */
.room-hierarchy-indicators {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
}
.hierarchy-badge {
  font-size: 0.7rem;
  padding: 1px 6px;
  border-radius: 10px;
  cursor: default;
}
.hierarchy-badge.parent { background: rgba(168, 85, 247, 0.2); color: #c084fc; }
.hierarchy-badge.child { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
.hierarchy-badge.related { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
.hierarchy-btn {
  background: none;
  border: 1px solid #3f3f5a;
  color: #6b7280;
  font-size: 0.75rem;
  padding: 1px 6px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
  margin-left: auto;
}
.hierarchy-btn:hover { background: rgba(91, 91, 214, 0.3); border-color: #5b5bd6; color: #a5a5f0; }

/* ─── Room Hierarchy Modal ─── */
.room-hierarchy-modal { max-width: 560px; width: 95vw; }
.hierarchy-room-info {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 8px;
}
.hierarchy-room-topic { color: #e0e0f0; font-weight: 500; font-size: 0.95rem; flex: 1; }
.hierarchy-room-num { color: #6b7280; font-size: 0.8rem; }
.hierarchy-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
  border-bottom: 1px solid #2a2a3a;
  padding-bottom: 4px;
}
.hierarchy-tabs button {
  background: none;
  border: none;
  color: #6b7280;
  font-size: 0.85rem;
  padding: 6px 12px;
  cursor: pointer;
  border-radius: 6px 6px 0 0;
  transition: all 0.15s;
}
.hierarchy-tabs button:hover { color: #a0a0c0; background: rgba(255, 255, 255, 0.05); }
.hierarchy-tabs button.active { color: #7c7cf0; background: rgba(91, 91, 214, 0.15); }
.hierarchy-view-tab { display: flex; flex-direction: column; gap: 12px; }
.hierarchy-section { }
.hierarchy-section-title { color: #8080a0; font-size: 0.78rem; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.05em; }
.hierarchy-items-list { display: flex; flex-direction: column; gap: 4px; }
.hierarchy-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  font-size: 0.85rem;
}
.hierarchy-item:hover { background: rgba(255, 255, 255, 0.06); }
.hierarchy-icon { color: #6b7280; font-size: 0.9rem; }
.hierarchy-item.parent-item .hierarchy-icon { color: #c084fc; }
.hierarchy-item.child-item .hierarchy-icon { color: #60a5fa; }
.hierarchy-item.related-item .hierarchy-icon { color: #4ade80; }
.hierarchy-item-topic { flex: 1; color: #d0d0e8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hierarchy-item-phase { font-size: 0.7rem; color: #6b7280; padding: 1px 6px; background: rgba(255,255,255,0.05); border-radius: 4px; }
.hierarchy-empty { color: #4a4a6a; font-size: 0.82rem; padding: 6px 0; }
.loading-state { color: #6b7280; text-align: center; padding: 20px; }
.checkbox-group { display: flex; flex-direction: column; gap: 6px; max-height: 180px; overflow-y: auto; background: rgba(255,255,255,0.02); border-radius: 8px; padding: 8px; }
.checkbox-item { display: flex; align-items: center; gap: 8px; color: #a0a0c0; font-size: 0.85rem; cursor: pointer; padding: 4px 6px; border-radius: 4px; }
.checkbox-item:hover { background: rgba(255,255,255,0.05); }
.checkbox-item input[type="checkbox"] { accent-color: #5b5bd6; }
.hierarchy-conclude-tab .btn-danger {
  background: rgba(220, 38, 38, 0.2);
  border: 1px solid rgba(220, 38, 38, 0.4);
  color: #f87171;
  padding: 8px 20px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.15s;
}
.hierarchy-conclude-tab .btn-danger:hover { background: rgba(220, 38, 38, 0.35); }
.hierarchy-conclude-tab .btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

/* ─── Tasks Toolbar ─── */
.tasks-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 16px;
}
.version-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}
.version-label { color: #6a6a8a; font-size: 0.85rem; }
.version-select { width: auto; padding: 6px 12px; font-size: 0.85rem; }

.add-task-panel {
  background: #13131f;
  border: 1px solid #2d2d4a;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}
.task-desc-input { resize: vertical; min-height: 50px; }
.task-form-row { display: flex; gap: 10px; }
.task-form-row .input { flex: 1; }
.priority-select { width: 120px; }

.tasks-metrics {
  display: flex;
  align-items: center;
  gap: 16px;
  color: #6a6a8a;
  font-size: 0.85rem;
  margin-bottom: 16px;
}
.metric-rate { color: #10b981; font-weight: 600; }

.tasks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-card {
  background: #13121c;
  border: 1px solid #1e1e2e;
  border-radius: 10px;
  padding: 16px;
}
.task-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.task-card-title {
  color: #d0d0e8;
  font-size: 0.9rem;
  font-weight: 500;
  flex: 1;
}
.task-card-badges {
  display: flex;
  gap: 6px;
}
.task-card-desc {
  color: #6a6a8a;
  font-size: 0.8rem;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-progress-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.task-progress-bar {
  flex: 1;
  height: 4px;
  background: #2d2d4a;
  border-radius: 2px;
  overflow: hidden;
}
.task-progress-fill {
  height: 100%;
  transition: width 0.3s;
}
.fill-completed { background: #22c55e; }
.fill-in_progress { background: #3b82f6; }
.fill-pending { background: #6b7280; }
.task-progress-val { color: #6a6a8a; font-size: 0.75rem; width: 36px; text-align: right; }
.task-slider { width: 100%; height: 18px; cursor: pointer; accent-color: #5b5bd6; }

/* ─── Decisions ─── */
.decisions-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 16px;
}
.add-decision-panel {
  background: #13131f;
  border: 1px solid #2d2d4a;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}
.decision-form-header {
  color: #a0a0ff;
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 4px;
}
.decision-text-input { resize: vertical; min-height: 50px; }
.decision-form-row { display: flex; gap: 10px; }
.decision-form-row .input { flex: 1; }
.decision-form-actions { display: flex; gap: 10px; }
.btn-cancel {
  background: #1e1e2e;
  border: 1px solid #2d2d4a;
  color: #8b8ba0;
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-cancel:hover { border-color: #5b5bd6; color: #a0a0ff; }
.decisions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.decision-card {
  background: #13121c;
  border: 1px solid #1e1e2e;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.decision-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.decision-card-title {
  color: #fff;
  font-size: 0.95rem;
  font-weight: 600;
  flex: 1;
}
.decision-card-actions { display: flex; gap: 6px; flex-shrink: 0; }
.btn-edit {
  background: #1e1e2e;
  border: 1px solid #2d2d4a;
  color: #8b8ba0;
  padding: 3px 10px;
  border-radius: 5px;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-edit:hover { border-color: #5b5bd6; color: #a0a0ff; }
.decision-card-number {
  color: #4a4a6a;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.decision-card-text {
  color: #d0d0e8;
  font-size: 0.9rem;
  line-height: 1.5;
}
.decision-card-desc {
  color: #6a6a8a;
  font-size: 0.82rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.decision-card-rationale {
  color: #8a8aaa;
  font-size: 0.82rem;
  line-height: 1.4;
}
.decision-card-alts {
  color: #6a6a8a;
  font-size: 0.8rem;
}
.alt-item { padding-left: 12px; margin-top: 2px; }
.decision-label { color: #4a4a6a; font-size: 0.75rem; }
.decision-card-footer {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
}
.decision-party { color: #8a8aaa; font-size: 0.8rem; }
.decision-party.agreed { color: #22c55e; }
.decision-party.disagreed { color: #ef4444; }

/* ─── Edicts (L7 圣旨) ─── */
.edicts-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 16px;
}
.add-edict-panel {
  background: #13131f;
  border: 1px solid #2d2d4a;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}
.edict-form-header {
  color: #f0c040;
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 4px;
}
.edict-text-input { resize: vertical; min-height: 80px; }
.edict-form-row { display: flex; gap: 10px; }
.edict-form-row .input { flex: 1; }
.edict-form-actions { display: flex; gap: 10px; }
.edicts-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.edict-card {
  background: #13121c;
  border: 1px solid #1e1e2e;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.edict-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.edict-card-title {
  color: #f0c040;
  font-size: 0.95rem;
  font-weight: 600;
  flex: 1;
}
.edict-card-actions { display: flex; gap: 6px; flex-shrink: 0; }
.edict-card-number {
  color: #f0c040;
  font-size: 0.75rem;
  opacity: 0.7;
}
.edict-card-status {
  display: inline-block;
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
  width: fit-content;
}
.edict-card-status.status-published { background: #14532d; color: #4ade80; }
.edict-card-status.status-draft { background: #1e1e2e; color: #a0a0ff; }
.edict-card-status.status-revoked { background: #2d1f1f; color: #f87171; }
.edict-card-content { color: #ccc; font-size: 0.85rem; line-height: 1.5; white-space: pre-wrap; }
.edict-card-meta { color: #8a8aaa; font-size: 0.75rem; }
.edict-label { color: #4a4a6a; font-size: 0.75rem; }
.btn-delete { color: #f87171 !important; }
.btn-delete:hover { border-color: #f87171 !important; }

/* ─── Versions ─── */
.versions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.version-row {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #13121c;
  border: 1px solid #1e1e2e;
  border-radius: 10px;
  padding: 14px 20px;
}
.version-badge-lg {
  background: #2d2d4a;
  color: #a0a0c0;
  font-size: 0.85rem;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 6px;
}
.version-info {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.version-name { color: #d0d0e8; font-size: 0.9rem; }
.btn-switch-version {
  background: #1e1e2e;
  border: 1px solid #2d2d4a;
  color: #8b8ba0;
  padding: 4px 14px;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-switch-version:hover { border-color: #5b5bd6; color: #a0a0ff; }

.versions-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.version-compare-panel {
  margin-top: 20px;
  background: #13121c;
  border: 1px solid #2d2d4a;
  border-radius: 12px;
  padding: 20px;
}
.compare-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.compare-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: #d0d0e8;
}
.compare-selectors {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 16px;
}
.compare-selectors .form-group { flex: 1; margin: 0; }
.compare-arrow {
  font-size: 1.4rem;
  color: #5b5bd6;
  padding-bottom: 8px;
}
.compare-content { margin-top: 12px; }
.compare-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.compare-col {
  background: #1a1a2e;
  border-radius: 8px;
  padding: 12px 16px;
}
.compare-col-header {
  font-size: 1rem;
  font-weight: 700;
  color: #a0a0ff;
  margin-bottom: 8px;
}
.compare-stat {
  font-size: 0.85rem;
  color: #8b8ba0;
  padding: 3px 0;
}
.compare-details { margin-top: 12px; }
.compare-section-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: #d0d0e8;
  margin-bottom: 8px;
}
.compare-task-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid #1e1e2e;
  font-size: 0.85rem;
}
.task-num { color: #5b5bd6; font-weight: 600; min-width: 40px; }
.task-title { flex: 1; color: #c0c0d8; }
.task-status {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
}
.status-completed, .status-done { background: #0f3020; color: #4ade80; }
.status-in_progress, .status-in-progress { background: #1a2a0f; color: #a3e635; }
.status-pending { background: #1e1e2e; color: #8b8ba0; }
.status-blocked { background: #2a0f0f; color: #f87171; }
.empty-compare { color: #5a5a7a; font-size: 0.85rem; padding: 12px 0; }

/* ─── Risks Tab ─── */
.risks-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 16px;
}

.risk-summary {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #13131f;
  border: 1px solid #1e1e2e;
  border-radius: 10px;
}
.risk-stat { font-size: 0.85rem; }
.risk-stat.critical { color: #f87171; }
.risk-stat.high { color: #fb923c; }
.risk-stat.medium { color: #fbbf24; }
.risk-stat.low { color: #4ade80; }

.add-risk-panel {
  background: #13131f;
  border: 1px solid #2d2d4a;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}
.risk-form-header {
  color: #fb923c;
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 4px;
}
.risk-text-input { resize: vertical; min-height: 50px; }
.risk-form-row { display: flex; gap: 10px; }
.risk-form-row .form-group { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.form-label { color: #6a6a8a; font-size: 0.78rem; }
.risk-form-actions { display: flex; gap: 10px; }

.risks-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.risk-card {
  background: #13121c;
  border: 1px solid #1e1e2e;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.risk-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.risk-card-title {
  color: #fff;
  font-size: 0.95rem;
  font-weight: 600;
  flex: 1;
}
.risk-card-actions { display: flex; gap: 6px; flex-shrink: 0; align-items: center; }
.severity-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}
.sev-critical { background: #2d1f1f; color: #f87171; }
.sev-high { background: #2d251f; color: #fb923c; }
.sev-medium { background: #2d2b1f; color: #fbbf24; }
.sev-low { background: #1f2d1f; color: #4ade80; }

.risk-card-desc { color: #8a8aaa; font-size: 0.82rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.risk-card-meta { display: flex; gap: 16px; flex-wrap: wrap; }
.risk-meta-item { color: #6a6a8a; font-size: 0.78rem; }
.risk-val { color: #a0a0c0; }
.status-risk { padding: 1px 6px; border-radius: 3px; font-size: 0.72rem; }
.status-identified { background: #1e1e2e; color: #a0a0ff; }
.status-monitoring { background: #1e2a2e; color: #38bdf8; }
.status-mitigating { background: #2a2a1e; color: #fbbf24; }
.status-resolved { background: #1e2d1f; color: #4ade80; }

.risk-card-mitigation,
.risk-card-contingency {
  color: #6a6a8a;
  font-size: 0.8rem;
  line-height: 1.4;
}
.risk-label { color: #4a4a6a; font-size: 0.75rem; }

/* ─── Requirements Tab ─── */
.requirements-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 16px;
}
.requirement-summary {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #13131f;
  border: 1px solid #1e1e2e;
  border-radius: 10px;
  flex-wrap: wrap;
}
.req-stat { font-size: 0.85rem; }
.req-stat.pending { color: #fb923c; }
.req-stat.in-progress { color: #38bdf8; }
.req-stat.met { color: #4ade80; }
.req-stat.partially-met { color: #fbbf24; }
.req-stat.not-met { color: #f87171; }
.req-stat.deprecated { color: #6b7280; }

.add-requirement-panel {
  background: #13131f;
  border: 1px solid #2d2d4a;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}
.requirement-form-header {
  color: #a78bfa;
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 4px;
}
.requirement-text-input { resize: vertical; min-height: 60px; }
.requirement-notes-input { resize: vertical; min-height: 40px; }
.requirement-form-row { display: flex; gap: 10px; }
.requirement-form-row .form-group { flex: 1; display: flex; flex-direction: column; gap: 4px; }
.requirement-form-actions { display: flex; gap: 10px; }

.requirements-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.requirement-card {
  background: #13121c;
  border: 1px solid #1e1e2e;
  border-radius: 10px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.requirement-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.requirement-card-title {
  color: #e2e8f0;
  font-size: 0.95rem;
  font-weight: 500;
  flex: 1;
  line-height: 1.5;
}
.requirement-card-actions { display: flex; gap: 6px; flex-shrink: 0; align-items: center; flex-wrap: wrap; }
.requirement-card-notes { color: #8a8aaa; font-size: 0.82rem; line-height: 1.4; }
.priority-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}
.priority-high { background: rgba(248, 113, 113, 0.15); color: #f87171; }
.priority-medium { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
.priority-low { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
.priority-critical { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
.category-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  background: rgba(139, 92, 246, 0.15);
  color: #a78bfa;
}
.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
}
.status-pending { background: rgba(251, 146, 60, 0.15); color: #fb923c; }
.status-in_progress { background: rgba(56, 189, 248, 0.15); color: #38bdf8; }
.status-met { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
.status-partially_met { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
.status-not_met { background: rgba(248, 113, 113, 0.15); color: #f87171; }
.status-deprecated { background: rgba(107, 114, 128, 0.15); color: #6b7280; }

/* ─── Mode Select ─── */
.mode-select-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.mode-label { color: #6a6a8a; font-size: 0.9rem; white-space: nowrap; }
.mode-select { width: auto; flex: 1; }

/* ─── Activity Tab ─── */
.activity-scope-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
  flex-wrap: wrap;
}
.scope-tabs {
  display: flex;
  gap: 4px;
  background: #1a1a2e;
  border: 1px solid #2a2a3e;
  border-radius: 8px;
  padding: 4px;
}
.scope-tab {
  background: transparent;
  border: none;
  color: #6a6a8a;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
}
.scope-tab:hover {
  color: #e2e8f0;
}
.scope-tab.active {
  background: #3b82f6;
  color: #ffffff;
  font-weight: 600;
}
.activity-scope-select {
  width: auto;
  flex: 0 0 auto;
  min-width: 180px;
}
.activity-stats {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.activity-stat-card {
  background: #1a1a2e;
  border: 1px solid #2a2a3e;
  border-radius: 10px;
  padding: 12px 20px;
  text-align: center;
  min-width: 80px;
}
.activity-stat-num {
  font-size: 1.8rem;
  font-weight: 700;
  color: #60a5fa;
}
.activity-stat-label {
  font-size: 0.75rem;
  color: #6a6a8a;
  margin-top: 2px;
  text-transform: capitalize;
}
.activity-filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}
.activity-filter-select {
  width: auto;
  flex: 0 0 auto;
}
.activity-detail-panel {
  background: #1a1a2e;
  border: 1px solid #2a2a3e;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 16px;
}
.activity-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.activity-detail-title {
  font-size: 1rem;
  font-weight: 600;
  color: #e2e8f0;
}
.activity-detail-content {
  color: #cbd5e1;
  font-size: 0.9rem;
  line-height: 1.5;
  margin-top: 8px;
  white-space: pre-wrap;
}
.activities-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.activity-card {
  background: #13131f;
  border: 1px solid #1e1e2e;
  border-radius: 8px;
  padding: 12px 16px;
  cursor: pointer;
  transition: border-color 0.2s;
}
.activity-card:hover {
  border-color: #3a3a5e;
}
.activity-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.activity-type-badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(96, 165, 250, 0.15);
  color: #60a5fa;
  font-family: monospace;
}
.activity-type-badge.activity-type-plan { background: rgba(96, 165, 250, 0.15); color: #60a5fa; }
.activity-type-badge.activity-type-room { background: rgba(167, 139, 250, 0.15); color: #a78bfa; }
.activity-type-badge.activity-type-task { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
.activity-type-badge.activity-type-decision { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
.activity-type-badge.activity-type-edict { background: rgba(251, 146, 60, 0.15); color: #fb923c; }
.activity-type-badge.activity-type-problem { background: rgba(248, 113, 113, 0.15); color: #f87171; }
.activity-type-badge.activity-type-approval { background: rgba(192, 132, 252, 0.15); color: #c084fc; }
.activity-type-badge.activity-type-risk { background: rgba(248, 113, 113, 0.15); color: #f87171; }
.activity-type-badge.activity-type-constraint { background: rgba(96, 165, 250, 0.15); color: #60a5fa; }
.activity-type-badge.activity-type-stakeholder { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
.activity-type-badge.activity-type-participant { background: rgba(167, 139, 250, 0.15); color: #a78bfa; }
.activity-type-badge.activity-type-subtask { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
.activity-type-badge.activity-type-escalation { background: rgba(248, 113, 113, 0.15); color: #f87171; }
.activity-time {
  font-size: 0.75rem;
  color: #6a6a8a;
}
.activity-card-content {
  font-size: 0.85rem;
  color: #cbd5e1;
  line-height: 1.4;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.activity-card-footer {
  display: flex;
  gap: 12px;
  align-items: center;
}
.activity-performer {
  font-size: 0.75rem;
  color: #6a6a8a;
}
.activity-level {
  font-size: 0.75rem;
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.1);
  padding: 1px 6px;
  border-radius: 6px;
}

/* ─── Debate Section ─── */
.debate-section {
  background: #13131f;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid #2a2a3e;
}
.consensus-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.consensus-label {
  font-size: 0.8rem;
  color: #8b8ba0;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
.consensus-level {
  font-size: 0.7rem;
  padding: 1px 6px;
  border-radius: 6px;
  font-weight: 600;
}
.consensus-level.level-high { background: rgba(34,197,94,0.2); color: #4ade80; }
.consensus-level.level-mid { background: rgba(251,191,36,0.2); color: #fbbf24; }
.consensus-level.level-low { background: rgba(249,115,22,0.2); color: #f97316; }
.consensus-level.level-dispute { background: rgba(239,68,68,0.2); color: #f87171; }
.consensus-track {
  flex: 1;
  height: 6px;
  background: #1e1e2e;
  border-radius: 3px;
  overflow: hidden;
}
.consensus-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}
.consensus-fill.fill-high { background: #4ade80; }
.consensus-fill.fill-mid { background: #fbbf24; }
.consensus-fill.fill-low { background: #f97316; }
.consensus-score {
  font-size: 0.8rem;
  font-weight: 600;
  color: #e2e8f0;
  min-width: 36px;
  text-align: right;
}
.add-debate-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}
.debate-points {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}
.points-label {
  font-size: 0.75rem;
  color: #6a6a8a;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.debate-point-row {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 8px 10px;
  border: 1px solid #2a2a3e;
}
.debate-point-row.converged {
  border-left: 3px solid #4ade80;
}
.debate-point-row.disputed {
  border-left: 3px solid #f97316;
}
.point-content {
  font-size: 0.85rem;
  color: #e2e8f0;
  margin-bottom: 4px;
  line-height: 1.4;
}
.point-header-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.point-type-badge {
  font-size: 0.65rem;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(167,139,250,0.15);
  color: #a78bfa;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.point-status-badge {
  font-size: 0.65rem;
  padding: 1px 6px;
  border-radius: 4px;
}
.point-status-badge.status-converged { background: rgba(34,197,94,0.15); color: #4ade80; }
.point-status-badge.status-disputed { background: rgba(249,115,22,0.15); color: #f97316; }
.point-agents {
  font-size: 0.7rem;
  color: #6a6a8a;
  margin-bottom: 2px;
}
.agreed-by {
  font-size: 0.7rem;
  color: #4ade80;
}
.point-stances {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
}
.supporters { font-size: 0.75rem; color: #4ade80; }
.opposers { font-size: 0.75rem; color: #f87171; }
.debate-actions {
  display: flex;
  gap: 6px;
}
.stance-btn {
  font-size: 0.7rem;
  padding: 2px 10px;
  border-radius: 4px;
  border: 1px solid #3a3a5e;
  background: transparent;
  color: #8b8ba0;
  cursor: pointer;
  transition: all 0.15s;
}
.stance-btn.support:hover, .stance-btn.support.active {
  background: rgba(34,197,94,0.15);
  border-color: #4ade80;
  color: #4ade80;
}
.stance-btn.oppose:hover, .stance-btn.oppose.active {
  background: rgba(239,68,68,0.15);
  border-color: #f87171;
  color: #f87171;
}
.recent-exchanges {
  margin-top: 8px;
}
.exchange-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  border-bottom: 1px solid #1e1e2e;
  font-size: 0.75rem;
}
.exchange-agent { color: #a78bfa; font-weight: 500; }
.exchange-position { font-size: 0.9rem; }
.exchange-point { color: #8b8ba0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.exchange-type-badge { font-size: 0.75rem; }
.exchange-target { color: #6b7280; font-size: 0.7rem; }
.exchange-content { color: #d1d5db; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.debate-title-btns { display: flex; gap: 4px; }
.sidebar-textarea { resize: vertical; min-height: 48px; font-family: inherit; }
.advance-round-row { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; padding-top: 8px; border-top: 1px solid #2a2a3e; }
.round-info { font-size: 0.75rem; color: #8b8ba0; }
.btn-advance-round { font-size: 0.75rem; padding: 4px 10px; background: rgba(59,130,246,0.15); border: 1px solid #60a5fa; color: #60a5fa; border-radius: 6px; cursor: pointer; transition: all 0.2s; }
.btn-advance-round:hover:not(:disabled) { background: rgba(59,130,246,0.3); }
.btn-advance-round:disabled { opacity: 0.4; cursor: not-allowed; }

/* ─── Hierarchical Review Section ─── */
.hierarchical-review-section {
  background: #13121f;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid #6366f1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.review-section-label {
  font-size: 0.75rem;
  color: #8b8ba0;
  margin-bottom: 6px;
  font-weight: 500;
}
.review-consensus-block {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 8px 10px;
}
.consensus-point-chip {
  display: inline-block;
  background: rgba(99,102,241,0.15);
  border: 1px solid rgba(99,102,241,0.3);
  color: #a5b4fc;
  border-radius: 12px;
  padding: 3px 10px;
  font-size: 0.75rem;
  margin: 2px 4px 2px 0;
}
.review-hierarchy-block {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 8px 10px;
}
.approval-chain {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.approval-level-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 4px;
  font-size: 0.75rem;
  color: #8b8ba0;
}
.approval-level-row.is-current {
  background: rgba(99,102,241,0.2);
  color: #c7d2fe;
}
.level-num { font-weight: 600; min-width: 20px; }
.level-name { flex: 1; color: #a0a0c0; }
.approval-status-chip { font-size: 0.7rem; }
.approval-status-chip.status-approved { color: #4ade80; }
.approval-status-chip.status-rejected { color: #f87171; }
.approval-status-chip.status-pending { color: #fbbf24; }
.review-no-context {
  text-align: center;
  padding: 12px;
  background: #1a1a2e;
  border-radius: 6px;
}
.review-hint { font-size: 0.8rem; color: #a0a0c0; }
.review-hint-sub { font-size: 0.7rem; color: #6b7280; margin-top: 4px; }
.review-notes-block { background: #1a1a2e; border-radius: 6px; padding: 8px 10px; }
.review-textarea { resize: vertical; min-height: 48px; font-family: inherit; font-size: 0.8rem; }

/* ─── Converging Section ─── */
.converging-section {
  background: #13121a;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid #f59e0b;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.converging-points-block {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 8px 10px;
}
.consensus-point-item {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 4px 0;
  border-bottom: 1px solid #1e1e2e;
  font-size: 0.75rem;
}
.consensus-point-item:last-child { border-bottom: none; }
.point-check { color: #4ade80; flex-shrink: 0; }
.point-desc { color: #d1d5db; }
.converging-no-points {
  text-align: center;
  padding: 12px;
  background: #1a1a2e;
  border-radius: 6px;
}
.converging-hint-block {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 8px 10px;
}
.phase-badge-sm {
  font-size: 0.65rem;
  padding: 2px 8px;
  border-radius: 10px;
  color: #fff;
  font-weight: 600;
}

/* ─── Problem Section ─── */
.problem-section {
  background: #13131f;
  border-radius: 8px;
  padding: 12px;
  border: 1px solid #dc2626;
}
.problem-phase-badge {
  font-size: 0.65rem;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
  text-transform: uppercase;
}
.problem-phase-badge.phase-problem_detected { background: rgba(239,68,68,0.2); color: #f87171; }
.problem-phase-badge.phase-problem_analysis { background: rgba(251,191,36,0.2); color: #fbbf24; }
.problem-phase-badge.phase-problem_discussion { background: rgba(167,139,250,0.2); color: #a78bfa; }
.problem-phase-badge.phase-plan_update { background: rgba(59,130,246,0.2); color: #60a5fa; }
.problem-phase-badge.phase-resuming { background: rgba(34,197,94,0.2); color: #4ade80; }
.problem-info {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
}
.problem-desc {
  font-size: 0.82rem;
  color: #9ca3af;
  margin-top: 6px;
  line-height: 1.5;
}
.problem-phase-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.problem-section-title {
  font-size: 0.78rem;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.problem-hint {
  font-size: 0.8rem;
  color: #6b7280;
  text-align: center;
  padding: 8px 0;
}
.problem-textarea {
  resize: vertical;
  min-height: 60px;
  font-size: 0.82rem;
}
.problem-slider {
  flex: 1;
  accent-color: #dc2626;
}
.slider-value {
  font-size: 0.78rem;
  color: #9ca3af;
  min-width: 36px;
  text-align: right;
}
.form-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.form-label {
  font-size: 0.78rem;
  color: #9ca3af;
  min-width: 60px;
}
.solution-option {
  background: #1e1e2e;
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 6px;
}
.option-pros-cons {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
}
.analysis-summary {
  background: #1e1e2e;
  border-radius: 6px;
  padding: 8px;
  margin-bottom: 8px;
}
.solutions-voting {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}
.solution-vote-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #1a1a2e;
  border-radius: 6px;
  padding: 6px 10px;
}
.solution-desc {
  font-size: 0.82rem;
  color: #e2e8f0;
  flex: 1;
}
.vote-btn {
  font-size: 0.72rem;
  padding: 2px 10px;
  border-radius: 4px;
  border: 1px solid #3a3a5e;
  background: transparent;
  color: #8b8ba0;
  cursor: pointer;
  transition: all 0.15s;
}
.vote-btn.selected {
  background: rgba(34,197,94,0.15);
  border-color: #4ade80;
  color: #4ade80;
}
.severity-badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}
.severity-badge.severity-low { background: rgba(34,197,94,0.15); color: #4ade80; }
.severity-badge.severity-medium { background: rgba(251,191,36,0.15); color: #fbbf24; }
.severity-badge.severity-high { background: rgba(249,115,22,0.15); color: #f97316; }
.severity-badge.severity-critical { background: rgba(239,68,68,0.15); color: #f87171; }
.problem-report-area {
  margin-top: 8px;
}
.btn-report-problem {
  width: 100%;
  padding: 8px;
  border-radius: 6px;
  border: 1px dashed #dc2626;
  background: rgba(239,68,68,0.05);
  color: #f87171;
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-report-problem:hover {
  background: rgba(239,68,68,0.1);
  border-style: solid;
}
.report-problem-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}

/* ─── Task Dependencies Modal ─── */
.task-dependencies-modal { max-width: 600px; width: 95vw; max-height: 85vh; overflow-y: auto; }
.dep-summary-bar {
  display: flex;
  gap: 16px;
  padding: 12px;
  background: #1e1e2e;
  border-radius: 8px;
  margin-bottom: 16px;
}
.dep-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.dep-stat-num { font-size: 1.5rem; font-weight: 700; color: #818cf8; }
.dep-stat.blocked .dep-stat-num { color: #f87171; }
.dep-stat.edges .dep-stat-num { color: #34d399; }
.dep-stat-label { font-size: 0.7rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
.dep-section { margin-bottom: 16px; }
.dep-section-title { font-size: 0.8rem; font-weight: 600; color: #9ca3af; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; }
.dep-empty { color: #6b7280; text-align: center; padding: 20px 0; font-size: 0.85rem; }
.dep-blocked-task {
  background: rgba(239,68,68,0.08);
  border: 1px solid rgba(239,68,68,0.2);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
}
.dep-task-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.dep-task-num { font-size: 0.7rem; color: #6b7280; font-weight: 600; }
.dep-task-title { font-size: 0.85rem; color: #e5e7eb; font-weight: 500; flex: 1; }
.dep-blocked-by { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.dep-blocked-label { font-size: 0.72rem; color: #9ca3af; }
.dep-blocker-chip {
  background: rgba(239,68,68,0.15);
  color: #fca5a5;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.72rem;
}
.dep-graph-list { display: flex; flex-direction: column; gap: 6px; }
.dep-node {
  background: #1a1a2e;
  border: 1px solid #2a2a3e;
  border-radius: 8px;
  padding: 10px 12px;
}
.dep-node-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.dep-blocked-badge { font-size: 0.8rem; }
.dep-node-num { font-size: 0.7rem; color: #6b7280; font-weight: 600; min-width: 60px; }
.dep-node-title { font-size: 0.85rem; color: #e5e7eb; flex: 1; }
.dep-node-status { font-size: 0.72rem; padding: 2px 8px; border-radius: 10px; }
.dep-node-status.s-completed { background: rgba(52,211,153,0.15); color: #34d399; }
.dep-node-status.s-in_progress { background: rgba(129,140,248,0.15); color: #818cf8; }
.dep-node-status.s-pending { background: rgba(107,114,128,0.15); color: #9ca3af; }
.dep-node-status.s-blocked { background: rgba(239,68,68,0.15); color: #f87171; }
.dep-node-deps { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; padding-left: 68px; }
.dep-deps-label { font-size: 0.7rem; color: #6b7280; }
.dep-dep-chip {
  background: rgba(129,140,248,0.12);
  color: #a5b4fc;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.72rem;
}
.dep-dep-chip.dep-missing { background: rgba(107,114,128,0.15); color: #6b7280; text-decoration: line-through; }
.loading-state { text-align: center; padding: 40px; color: #6b7280; }

/* ─── Room Tags ─── */
.room-tags-row { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 4px; }
.room-tag {
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
}
.room-tag.more { background: rgba(107, 114, 128, 0.15); color: #9ca3af; }
.room-header-tags { display: flex; gap: 4px; flex-wrap: wrap; padding: 4px 16px; background: rgba(30, 30, 46, 0.5); }
.header-tag {
  background: rgba(99, 102, 241, 0.12);
  color: #a5b4fc;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
}
.room-tags-btn {
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.25);
  color: #a5b4fc;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
}
.room-tags-btn:hover { background: rgba(99, 102, 241, 0.2); }

/* ─── Room Tags Modal ─── */
.room-tags-modal { max-width: 440px; width: 95vw; }
.room-tags-room-info { display: flex; align-items: center; gap: 8px; padding-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.06); margin-bottom: 16px; }
.room-tags-topic { color: #e0e0f0; font-weight: 500; flex: 1; }
.room-tags-num { color: #6b7280; font-size: 0.85rem; }
.room-tags-section { margin-bottom: 16px; }
.room-tags-section-title { font-size: 0.8rem; font-weight: 600; color: #9ca3af; margin-bottom: 8px; }
.room-tags-list { display: flex; flex-wrap: wrap; gap: 6px; }
.room-tag-item {
  background: rgba(99, 102, 241, 0.15);
  color: #a5b4fc;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 4px;
}
.tag-remove-btn { background: none; border: none; color: #f87171; cursor: pointer; font-size: 1rem; padding: 0 2px; }
.tag-remove-btn:hover { color: #fca5a5; }
.tag-remove-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.room-tags-empty { color: #6b7280; font-size: 0.85rem; font-style: italic; }
.room-tags-add-form { display: flex; gap: 8px; }
.room-tags-add-form .input { flex: 1; }

/* ─── Escalation Modal ─── */
.escalation-modal { max-width: 520px; width: 95vw; }
.escalation-form { padding: 8px 4px; }
.escalation-form .form-group { margin-bottom: 16px; }
.escalation-form label { display: block; font-size: 0.8rem; font-weight: 600; color: #9ca3af; margin-bottom: 6px; }
.escalation-form .required { color: #f87171; }
.escalation-form textarea.input { resize: vertical; min-height: 60px; }
.escalation-path-preview {
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 8px;
  padding: 10px 14px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.escalation-path-preview .path-label { font-size: 0.8rem; color: #9ca3af; }
.escalation-path-preview .path-steps { font-size: 0.85rem; color: #a5b4fc; font-weight: 600; }
.escalation-form .modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }

/* ─── Escalate Button ─── */
.escalate-btn {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.escalate-btn:hover {
  background: rgba(239, 68, 68, 0.25);
  border-color: rgba(239, 68, 68, 0.5);
}

/* ─── Room View ─── */
.room {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.room-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 24px;
  height: 60px;
  background: #111118;
  border-bottom: 1px solid #1e1e2e;
  flex-shrink: 0;
}
.room-title {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  overflow: hidden;
}
.room-name {
  color: #fff;
  font-weight: 600;
  font-size: 1rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.room-meta-header { color: #6a6a8a; font-size: 0.85rem; }
.ws-status-dot { margin-left: 6px; cursor: default; font-size: 0.9rem; }

.room-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* ─── Room Main ─── */
.room-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.phase-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  background: #13131f;
  border-bottom: 1px solid #1e1e2e;
  flex-shrink: 0;
  overflow-x: auto;
}
.phase-bar-label { color: #4a4a6a; font-size: 0.8rem; white-space: nowrap; }
.phase-btn {
  background: #1e1e2e;
  border: 1px solid #2d2d4a;
  color: #a0a0c0;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 0.8rem;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}
.phase-btn:hover { background: #2d2d4a; color: #fff; }

.message-search-bar {
  display: flex;
  gap: 8px;
  padding: 8px 0;
  margin-bottom: 8px;
}
.message-search-input { flex: 1; }
.search-results-indicator {
  font-size: 0.8rem;
  color: #a78bfa;
  padding: 4px 0 8px;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.messages-empty {
  text-align: center;
  color: #4a4a6a;
  padding: 60px;
  font-size: 0.9rem;
}

.message-row { display: flex; flex-direction: column; }
.message-bubble {
  background: #13131f;
  border: 1px solid #1e1e2e;
  border-radius: 10px;
  padding: 12px 16px;
  max-width: 80%;
}
.message-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.message-agent { color: #7c7cff; font-weight: 600; font-size: 0.85rem; }
.message-time { color: #4a4a6a; font-size: 0.75rem; }
.message-content { color: #d0d0e8; font-size: 0.95rem; word-break: break-word; }

.input-bar {
  display: flex;
  gap: 10px;
  padding: 16px 20px;
  background: #111118;
  border-top: 1px solid #1e1e2e;
  flex-shrink: 0;
}
.message-input {
  flex: 1;
  margin-bottom: 0;
}

/* ─── Sidebar ─── */
.room-sidebar {
  width: 240px;
  flex-shrink: 0;
  background: #0e0e18;
  border-left: 1px solid #1e1e2e;
  overflow-y: auto;
  padding: 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.sidebar-section { display: flex; flex-direction: column; gap: 10px; }
.sidebar-title-row { display: flex; align-items: center; justify-content: space-between; }
.sidebar-title { color: #4a4a6a; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; }
.sidebar-empty { color: #3a3a5a; font-size: 0.85rem; padding: 8px 0; }

/* Step 63: Phase Timeline */
.phase-timeline-count { color: #5a5a8a; font-size: 0.72rem; }
.phase-timeline-list { display: flex; flex-direction: column; gap: 0; }
.timeline-entry {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  position: relative;
  padding-bottom: 12px;
}
.timeline-entry:last-child { padding-bottom: 0; }
.timeline-entry:not(:last-child)::after {
  content: '';
  position: absolute;
  left: 5px;
  top: 14px;
  bottom: 0;
  width: 1px;
  background: #2d2d4a;
}
.timeline-phase-dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 2px;
  background: #2d2d4a;
  border: 2px solid #3d3d5a;
}
.timeline-current .timeline-phase-dot {
  background: #5b5bd6;
  border-color: #7b7bff;
  box-shadow: 0 0 6px rgba(91, 91, 214, 0.6);
}
.timeline-completed .timeline-phase-dot { background: #2d8a4e; border-color: #3aaa6a; }
.timeline-content { flex: 1; min-width: 0; }
.timeline-phase-name { color: #a0a0c0; font-size: 0.8rem; font-weight: 500; }
.timeline-time { color: #4a4a6a; font-size: 0.72rem; margin-top: 2px; display: flex; gap: 6px; }
.timeline-enter { color: #6a6a8a; }
.timeline-exit { color: #4a4a6a; }
.timeline-running { color: #7b7bff; }
.timeline-duration { color: #5a5a8a; font-size: 0.72rem; margin-top: 2px; }
.timeline-via { color: #4a4a6a; font-size: 0.72rem; margin-top: 1px; }
.sidebar-input {
  background: #13131f;
  border: 1px solid #2d2d4a;
  border-radius: 6px;
  color: #e2e8f0;
  padding: 6px 10px;
  font-size: 0.82rem;
  width: 100%;
}
.sidebar-input:focus { outline: none; border-color: #5b5bd6; }
.sidebar-btn { padding: 5px 12px; font-size: 0.8rem; }
.add-participant-form { display: flex; flex-direction: column; gap: 6px; padding: 8px; background: #13131f; border-radius: 8px; }
.btn-add-participant { background: transparent; border: 1px solid #2d2d4a; color: #6a6a8a; padding: 2px 8px; border-radius: 4px; font-size: 0.72rem; cursor: pointer; transition: all 0.15s; }
.btn-add-participant:hover { border-color: #5b5bd6; color: #8b8bb0; }
.level-row { display: flex; align-items: center; gap: 6px; }
.level-label { color: #4a4a6a; font-size: 0.8rem; }
.level-input { width: 60px !important; }

/* Step 64: Room Activity Stream */
.activity-stream-section { border-left: 2px solid #1e1e32; padding-left: 6px; }
.activity-stream-list { display: flex; flex-direction: column; gap: 0; max-height: 320px; overflow-y: auto; scrollbar-width: thin; scrollbar-color: #2d2d4a transparent; }
.stream-entry {
  display: flex;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid #1a1a2e;
}
.stream-entry:last-child { border-bottom: none; }
.stream-icon { font-size: 0.9rem; flex-shrink: 0; margin-top: 1px; }
.stream-body { flex: 1; min-width: 0; }
.stream-actor { color: #a0a0c0; font-size: 0.78rem; font-weight: 500; }
.stream-detail { color: #c0c0d8; font-size: 0.75rem; margin-top: 1px; line-height: 1.3; }
.stream-time { color: #4a4a6a; font-size: 0.68rem; margin-top: 2px; }
.stream-phase_change .stream-icon { color: #8b5cf6; }
.stream-speech .stream-icon { color: #3b82f6; }
.stream-participant_joined .stream-icon { color: #22c55e; }
.stream-participant_left .stream-icon { color: #ef4444; }
.activity-stream-preview { display: flex; flex-direction: column; gap: 4px; }
.stream-preview-row { display: flex; align-items: center; gap: 6px; }
.stream-icon-sm { font-size: 0.75rem; }
.stream-preview-text { color: #6a6a8a; font-size: 0.72rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stream-preview-more { color: #4a4a6a; font-size: 0.68rem; margin-top: 2px; }

.participant-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.participant-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #2d2d4a;
  color: #a0a0c0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;
}
.participant-info { display: flex; flex-direction: column; gap: 1px; overflow: hidden; }
.participant-name { color: #d0d0e8; font-size: 0.85rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.participant-role { color: #4a4a6a; font-size: 0.72rem; }

.info-row { display: flex; justify-content: space-between; align-items: center; }
.info-label { color: #4a4a6a; font-size: 0.8rem; }
.info-value { color: #8b8ba0; font-size: 0.8rem; }

/* ─── Task Styles ─── */
.task-metrics { display: flex; align-items: center; gap: 4px; font-size: 0.75rem; color: #6a6a8a; padding: 4px 0; }
.metric-item { }
.metric-divider { color: #3a3a5a; }
.metric-progress { margin-left: 8px; color: #10b981; font-weight: 600; }

.add-task-form { display: flex; flex-direction: column; gap: 6px; padding: 8px; background: #13131f; border-radius: 8px; }
.task-desc-input { resize: vertical; min-height: 40px; }

.task-row { display: flex; flex-direction: column; gap: 4px; padding: 8px 0; border-bottom: 1px solid #1e1e2e; }
.task-row:last-child { border-bottom: none; }
.task-info { display: flex; justify-content: space-between; align-items: flex-start; }
.task-title { color: #d0d0e8; font-size: 0.82rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-meta { display: flex; gap: 4px; font-size: 0.75rem; }
.task-priority, .task-status { }
.task-progress-bar { height: 3px; background: #2d2d4a; border-radius: 2px; overflow: hidden; }
.task-progress-fill { height: 100%; transition: width 0.3s; }
.progress-completed { background: #22c55e; }
.progress-in_progress { background: #3b82f6; }
.progress-pending { background: #6b7280; }
.task-slider { width: 100%; height: 16px; cursor: pointer; accent-color: #5b5bd6; }

/* ─── Scrollbar ─── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #2d2d4a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #3d3d5a; }

/* ─── Edict Acknowledgment ─── */
.btn-ack {
  background: #14532d;
  color: #4ade80;
  border: 1px solid #166534;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-ack:hover { background: #166534; }
.edict-acks { margin-top: 8px; padding-top: 8px; border-top: 1px solid #1e1e2e; }
.edict-acks-header { color: #4ade80; font-size: 0.75rem; margin-bottom: 4px; }
.edict-ack-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
  font-size: 0.75rem;
  color: #8a8aaa;
}
.ack-level { color: #a0a0ff; font-weight: 600; }
.ack-name { color: #ccc; flex: 1; }
.ack-time { color: #6a6a8a; }
.btn-del-ack {
  background: none;
  border: none;
  color: #6a6a8a;
  cursor: pointer;
  font-size: 0.9rem;
  padding: 0 2px;
}
.btn-del-ack:hover { color: #f87171; }

/* ─── Modal ─── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-content {
  background: #13121c;
  border: 1px solid #2d2d4a;
  border-radius: 14px;
  padding: 24px;
  width: 420px;
  max-width: 90vw;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.modal-header h3 { color: #d0d0e8; margin: 0; font-size: 1rem; }
.modal-close {
  background: none;
  border: none;
  color: #6a6a8a;
  font-size: 1.4rem;
  cursor: pointer;
  line-height: 1;
}
.modal-close:hover { color: #f87171; }
.modal-body .form-group { margin-bottom: 14px; }
.modal-body label {
  display: block;
  color: #8a8aaa;
  font-size: 0.78rem;
  margin-bottom: 4px;
}
.modal-body input,
.modal-body textarea {
  width: 100%;
  background: #0e0d14;
  border: 1px solid #2d2d4a;
  border-radius: 6px;
  color: #d0d0e8;
  padding: 7px 10px;
  font-size: 0.85rem;
  box-sizing: border-box;
}
.modal-body textarea { resize: vertical; }
.modal-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 16px;
}

/* ─── Notification Bell ─────────────────────────────────── */
.notification-bell {
  position: relative;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 1.1rem;
  transition: background 0.2s;
  margin-left: 8px;
}
.notification-bell:hover {
  background: rgba(255, 255, 255, 0.14);
}
.notification-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: #ef4444;
  color: white;
  border-radius: 50%;
  font-size: 0.65rem;
  font-weight: 700;
  min-width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 3px;
  line-height: 1;
}

/* ─── Notification Panel ────────────────────────────────── */
.notification-panel {
  position: fixed;
  top: 60px;
  right: 16px;
  width: 360px;
  max-height: 520px;
  background: #1a1930;
  border: 1px solid #2d2d4a;
  border-radius: 12px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
}
.notification-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 10px;
  border-bottom: 1px solid #2d2d4a;
}
.notification-panel-title {
  font-weight: 700;
  font-size: 1rem;
  color: #e0e0f0;
}
.notification-panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.notification-action-btn {
  background: none;
  border: none;
  color: #3b82f6;
  font-size: 0.8rem;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}
.notification-action-btn:hover {
  background: rgba(59, 130, 246, 0.15);
}
.notification-close-btn {
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  font-size: 0.9rem;
  padding: 2px 6px;
  border-radius: 4px;
}
.notification-close-btn:hover {
  background: rgba(255, 255, 255, 0.08);
}
.notification-list {
  overflow-y: auto;
  flex: 1;
}
.notification-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 20px;
  color: #6b7280;
}
.notification-empty-icon { font-size: 2rem; margin-bottom: 8px; }
.notification-empty-text { font-size: 0.9rem; }
.notification-item {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(45, 45, 74, 0.6);
  transition: background 0.15s;
}
.notification-item:last-child { border-bottom: none; }
.notification-item.unread {
  background: rgba(59, 130, 246, 0.06);
}
.notification-item:hover {
  background: rgba(255, 255, 255, 0.04);
}
.notification-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.notification-type-badge {
  font-size: 0.7rem;
  font-weight: 600;
  color: white;
  padding: 2px 7px;
  border-radius: 10px;
  white-space: nowrap;
}
.notification-delete-btn {
  background: none;
  border: none;
  color: #4b5563;
  cursor: pointer;
  font-size: 0.75rem;
  padding: 2px 4px;
  border-radius: 3px;
  opacity: 0;
  transition: opacity 0.2s;
}
.notification-item:hover .notification-delete-btn {
  opacity: 1;
}
.notification-delete-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}
.notification-item-title {
  font-size: 0.85rem;
  font-weight: 500;
  color: #d0d0e8;
  line-height: 1.4;
}
.notification-item-message {
  font-size: 0.78rem;
  color: #9ca3af;
  margin-top: 3px;
  line-height: 1.4;
}
.notification-item-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
}
.notification-time {
  font-size: 0.72rem;
  color: #6b7280;
}
.notification-mark-read-btn {
  background: rgba(59, 130, 246, 0.15);
  border: none;
  color: #3b82f6;
  font-size: 0.72rem;
  padding: 2px 7px;
  border-radius: 4px;
  cursor: pointer;
}
.notification-mark-read-btn:hover {
  background: rgba(59, 130, 246, 0.3);
}

/* ─── Snapshots Tab ──────────────────────────────────────── */
.tab-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.tab-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: #e0e0f0;
}
.snapshot-detail-panel {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  padding: 18px;
  margin-bottom: 20px;
}
.snapshot-detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.snapshot-detail-title {
  font-size: 1rem;
  font-weight: 600;
  color: #e0e0f0;
}
.snapshot-context {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 0.85rem;
  color: #9ca3af;
  line-height: 1.6;
  margin-top: 6px;
  white-space: pre-wrap;
}
.snapshots-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.snapshot-card {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 14px 16px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.snapshot-card:hover {
  background: rgba(255, 255, 255, 0.07);
  border-color: rgba(255, 255, 255, 0.15);
}
.snapshot-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.snapshot-time {
  font-size: 0.78rem;
  color: #6b7280;
}
.snapshot-card-summary {
  font-size: 0.88rem;
  color: #c0c0d8;
  line-height: 1.5;
  margin-bottom: 6px;
}
.snapshot-card-id {
  font-size: 0.72rem;
  color: #4b5563;
}

/* ─── Escalations Tab ─── */
.escalations-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.escalation-card {
  background: #1e2130;
  border-radius: 8px;
  padding: 14px;
  border: 1px solid #2d3148;
}
.escalation-card.escalation-pending {
  border-color: #f59e0b;
}
.escalation-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.escalation-levels {
  display: flex;
  align-items: center;
  gap: 6px;
}
.level-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.78rem;
  font-weight: 600;
}
.level-from {
  background: #374151;
  color: #d1d5db;
}
.level-to {
  background: #1e40af;
  color: #dbeafe;
}
.level-arrow {
  color: #9ca3af;
  font-size: 0.85rem;
}
.escalation-status {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 600;
}
.escalation-status.status-pending {
  background: #78350f;
  color: #fef3c7;
}
.escalation-status.status-approved {
  background: #14532d;
  color: #dcfce7;
}
.escalation-status.status-rejected {
  background: #7f1d1d;
  color: #fee2e2;
}
.escalation-status.status-resolved {
  background: #14532d;
  color: #dcfce7;
}
.escalation-card-body {
  margin-bottom: 10px;
}
.escalation-info {
  display: flex;
  gap: 6px;
  font-size: 0.82rem;
  margin-bottom: 4px;
}
.escalation-info .info-label {
  color: #6b7280;
}
.escalation-info .info-value {
  color: #d1d5db;
}
.escalation-room-id {
  font-family: monospace;
  font-size: 0.75rem;
  color: #9ca3af;
}
.escalation-reason {
  font-size: 0.85rem;
  color: #e5e7eb;
  margin-top: 6px;
  padding: 6px 8px;
  background: #272a3a;
  border-radius: 4px;
}
.escalation-notes {
  font-size: 0.78rem;
  color: #9ca3af;
  margin-top: 4px;
  font-style: italic;
}
.escalation-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px solid #2d3148;
}
.escalation-time {
  font-size: 0.72rem;
  color: #6b7280;
}

/* ─── Task Detail Modal ─── */
.task-detail-modal {
  max-width: 640px;
  width: 90vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}
.task-detail-body {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}
.task-detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #1f2937;
}
.task-meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.88rem;
}
.meta-label {
  color: #6b7280;
  font-size: 0.82rem;
}
.task-detail-desc {
  margin-bottom: 16px;
}
.detail-section-title {
  font-size: 0.82rem;
  color: #6b7280;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.task-detail-desc p {
  color: #d1d5db;
  font-size: 0.9rem;
  line-height: 1.6;
}
.task-detail-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
  border-bottom: 1px solid #1f2937;
  padding-bottom: 0;
}
.task-detail-tabs button {
  background: none;
  border: none;
  color: #9ca3af;
  padding: 8px 14px;
  cursor: pointer;
  font-size: 0.88rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all 0.2s;
}
.task-detail-tabs button.active {
  color: #60a5fa;
  border-bottom-color: #60a5fa;
}
.task-detail-tabs button:hover {
  color: #d1d5db;
}
.task-detail-tab-content {
  min-height: 120px;
}
.loading-state {
  text-align: center;
  padding: 24px;
  color: #6b7280;
  font-size: 0.88rem;
}
.empty-mini {
  text-align: center;
  padding: 20px;
  color: #4b5563;
  font-size: 0.85rem;
}
.comment-list, .checkpoint-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
  max-height: 260px;
  overflow-y: auto;
}
.comment-item {
  background: #111827;
  border-radius: 8px;
  padding: 10px 12px;
}
.comment-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}
.comment-author {
  font-size: 0.85rem;
  color: #60a5fa;
  font-weight: 500;
}
.comment-time {
  font-size: 0.75rem;
  color: #4b5563;
}
.comment-content {
  font-size: 0.88rem;
  color: #d1d5db;
  line-height: 1.5;
}
.add-comment-form, .add-checkpoint-form {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 8px;
  border-top: 1px solid #1f2937;
}
.add-comment-form .btn-primary {
  align-self: flex-end;
}
.checkpoint-item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #111827;
  border-radius: 8px;
  padding: 10px 12px;
}
.checkpoint-status-icon {
  font-size: 1rem;
}
.checkpoint-name {
  flex: 1;
  font-size: 0.88rem;
  color: #d1d5db;
}
.checkpoint-status-label {
  font-size: 0.78rem;
  color: #6b7280;
}
.add-checkpoint-form {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 6px;
  align-items: center;
}
.add-checkpoint-form .input {
  flex: 1;
}

/* Step 65: Time Tracking Tab */
.time-summary-bar {
  display: flex;
  gap: 12px;
  background: #1a1f2e;
  border: 1px solid #2d3748;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 12px;
}
.time-summary-item {
  flex: 1;
  text-align: center;
}
.time-summary-val {
  font-size: 1.3rem;
  font-weight: 700;
  color: #34d399;
}
.time-summary-label {
  font-size: 0.75rem;
  color: #94a3b8;
  margin-top: 2px;
}
.time-entry-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
  max-height: 260px;
  overflow-y: auto;
}
.time-entry-item {
  background: #111827;
  border-radius: 8px;
  padding: 10px 12px;
}
.time-entry-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.time-entry-user {
  font-size: 0.85rem;
  font-weight: 600;
  color: #e2e8f0;
  flex: 1;
}
.time-entry-hours {
  font-size: 0.9rem;
  font-weight: 700;
  color: #34d399;
}
.time-entry-desc {
  font-size: 0.82rem;
  color: #94a3b8;
  margin-bottom: 4px;
}
.time-entry-date {
  font-size: 0.75rem;
  color: #64748b;
}
.btn-delete-sm {
  background: transparent;
  border: none;
  color: #64748b;
  cursor: pointer;
  font-size: 0.75rem;
  padding: 2px 4px;
}
.btn-delete-sm:hover {
  color: #f87171;
}
.time-entry-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.time-entry-form-row {
  display: flex;
  gap: 6px;
}
.time-entry-form .input[type="number"] {
  width: 90px;
  flex: none;
}

/* Approvals Tab */
.start-approval-form {
  background: #1a1f2e;
  border: 1px solid #2d3748;
  border-radius: 10px;
  padding: 16px;
  margin: 12px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.start-approval-form .form-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 4px;
}
.start-approval-form .form-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.start-approval-form label {
  font-size: 0.8rem;
  color: #94a3b8;
}
.approval-status-badge {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.82rem;
  font-weight: 600;
}
.approval-status-in_progress { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
.approval-status-approved { background: rgba(16, 185, 129, 0.2); color: #34d399; }
.approval-status-rejected { background: rgba(239, 68, 68, 0.2); color: #f87171; }
.approval-status-pending { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }

.approval-levels-ref {
  margin: 16px 0;
}
.approval-levels-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
  margin-top: 8px;
}
.approval-level-ref-card {
  background: #1a1f2e;
  border-radius: 8px;
  padding: 10px 12px;
  border-left: 3px solid #3b82f6;
}
.approval-level-ref-header {
  font-size: 0.82rem;
  font-weight: 600;
  color: #e2e8f0;
}
.approval-level-ref-role {
  font-size: 0.75rem;
  color: #94a3b8;
  margin-top: 2px;
}

.approval-flow-status {
  margin-top: 16px;
}
.approval-levels-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 10px;
}
.approval-level-row {
  background: #1a1f2e;
  border-radius: 10px;
  padding: 14px;
  border-left: 4px solid #374151;
}
.approval-level-approved { border-left-color: #10b981; }
.approval-level-rejected { border-left-color: #ef4444; }
.approval-level-skipped { border-left-color: #6b7280; }
.approval-level-current { border-left-color: #f59e0b; }

.approval-level-header {
  display: flex;
  align-items: center;
  gap: 10px;
}
.approval-level-badge {
  background: #374151;
  color: #e2e8f0;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 0.82rem;
  font-weight: 700;
  min-width: 42px;
  text-align: center;
}
.approval-level-info {
  flex: 1;
}
.approval-level-label {
  font-size: 0.88rem;
  font-weight: 600;
  color: #e2e8f0;
  margin-right: 6px;
}
.approval-level-reviewer {
  font-size: 0.78rem;
  color: #94a3b8;
}
.approval-status-tag {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
}
.status-approved { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.status-rejected { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.status-skipped { background: rgba(107, 114, 128, 0.15); color: #9ca3af; }
.status-current { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.status-pending { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }

.approval-level-records {
  margin-top: 8px;
  padding-left: 52px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.approval-record {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.78rem;
  color: #94a3b8;
}
.record-action { font-weight: 600; color: #d1d5db; }
.record-actor { color: #9ca3af; }
.record-time { color: #6b7280; }
.record-comment { color: #9ca3af; font-style: italic; }

.approval-level-actions {
  margin-top: 10px;
  padding-left: 52px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.approval-comment-input {
  flex: 1;
  min-width: 150px;
  max-width: 300px;
  font-size: 0.82rem;
}
.btn-approve {
  padding: 6px 14px;
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 6px;
  font-size: 0.82rem;
  cursor: pointer;
  font-weight: 600;
}
.btn-approve:hover { background: rgba(16, 185, 129, 0.25); }
.btn-reject {
  padding: 6px 14px;
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  font-size: 0.82rem;
  cursor: pointer;
  font-weight: 600;
}
.btn-reject:hover { background: rgba(239, 68, 68, 0.25); }
.btn-return {
  padding: 6px 14px;
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
  border: 1px solid rgba(251, 191, 36, 0.3);
  border-radius: 6px;
  font-size: 0.82rem;
  cursor: pointer;
  font-weight: 600;
}
.btn-return:hover { background: rgba(251, 191, 36, 0.25); }
.btn-escalate {
  padding: 6px 14px;
  background: rgba(239, 68, 68, 0.15);
  color: #fb923c;
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  font-size: 0.82rem;
  cursor: pointer;
  font-weight: 600;
}
.btn-escalate:hover { background: rgba(239, 68, 68, 0.25); }

/* ── Analytics Dashboard ─────────────────────────────── */
.analytics-summary-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}
.analytics-card {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
}
.analytics-card-icon {
  font-size: 2.2rem;
  line-height: 1;
}
.analytics-card-body {
  flex: 1;
}
.analytics-card-num {
  font-size: 2rem;
  font-weight: 700;
  color: #f1f5f9;
  line-height: 1.1;
}
.analytics-card-label {
  font-size: 0.85rem;
  color: #94a3b8;
  margin: 2px 0;
}
.analytics-card-sub {
  font-size: 0.75rem;
  color: #64748b;
}
.sub-div { margin: 0 4px; }
.sub-active { color: #34d399; }
.sub-done { color: #60a5fa; }
.sub-progress { color: #fbbf24; }

.analytics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.analytics-panel {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 12px;
  padding: 20px;
}
.analytics-panel.wide {
  grid-column: span 2;
}
.analytics-panel-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: #e2e8f0;
  margin-bottom: 16px;
}
.analytics-empty {
  color: #64748b;
  font-size: 0.85rem;
  text-align: center;
  padding: 20px 0;
}

/* Phase Distribution */
.phase-distribution {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.phase-row { display: flex; flex-direction: column; gap: 4px; }
.phase-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.phase-name { font-size: 0.82rem; color: #cbd5e1; }
.phase-count { font-size: 0.82rem; color: #94a3b8; font-weight: 600; }
.phase-bar-track {
  height: 8px;
  background: #0f172a;
  border-radius: 4px;
  overflow: hidden;
}
.phase-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s ease;
  min-width: 4px;
}

/* Task Status Breakdown */
.task-status-breakdown {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.task-status-row { display: flex; flex-direction: column; gap: 4px; }
.task-status-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.82rem;
  color: #cbd5e1;
}
.task-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-completed { background: #22c55e; }
.dot-in_progress { background: #fbbf24; }
.dot-blocked { background: #ef4444; }
.dot-pending { background: #64748b; }
.dot-default { background: #94a3b8; }
.task-status-count {
  margin-left: auto;
  font-weight: 600;
  color: #94a3b8;
}
.task-status-bar-track {
  height: 6px;
  background: #0f172a;
  border-radius: 3px;
  overflow: hidden;
}
.task-status-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s ease;
  min-width: 2px;
}
.fill-completed { background: #22c55e; }
.fill-in_progress { background: #fbbf24; }
.fill-blocked { background: #ef4444; }
.fill-pending { background: #64748b; }
.fill-default { background: #94a3b8; }

/* Priority Distribution */
.priority-breakdown {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
}
.priority-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.priority-label { font-size: 0.8rem; color: #cbd5e1; width: 60px; flex-shrink: 0; }
.priority-bar-track {
  flex: 1;
  height: 6px;
  background: #0f172a;
  border-radius: 3px;
  overflow: hidden;
}
.priority-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s ease;
  min-width: 2px;
}
.fill-critical { background: #ef4444; }
.fill-high { background: #f97316; }
.fill-medium { background: #eab308; }
.fill-low { background: #22c55e; }
.priority-count { font-size: 0.78rem; color: #94a3b8; width: 20px; text-align: right; }

/* Completion Ring */
.completion-overview {
  display: flex;
  align-items: center;
  gap: 32px;
}
.completion-big-ring {
  position: relative;
  width: 120px;
  height: 120px;
  flex-shrink: 0;
}
.ring-svg { width: 120px; height: 120px; }
.ring-label {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.ring-pct {
  font-size: 1.5rem;
  font-weight: 700;
  color: #f1f5f9;
  line-height: 1;
}
.ring-sub { font-size: 0.7rem; color: #64748b; }
.completion-stats {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.82rem;
}
.stat-lbl { color: #94a3b8; }
.stat-val { color: #e2e8f0; font-weight: 600; }
.stat-val.done { color: #22c55e; }
.stat-val.progress { color: #fbbf24; }
.stat-val.blocked { color: #ef4444; }
.stat-val.pending { color: #64748b; }

/* Hours Comparison */
.hours-comparison {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.hours-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.hours-label { font-size: 0.8rem; color: #94a3b8; width: 36px; flex-shrink: 0; }
.hours-bar-track {
  flex: 1;
  height: 8px;
  background: #0f172a;
  border-radius: 4px;
  overflow: hidden;
}
.hours-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s ease;
}
.hours-bar-fill.estimated { background: #60a5fa; }
.hours-bar-fill.actual { background: #34d399; }
.hours-num { font-size: 0.8rem; color: #cbd5e1; width: 50px; text-align: right; }
.hours-variance {
  font-size: 0.8rem;
  display: flex;
  gap: 6px;
  align-items: center;
  margin-top: 4px;
}
.variance-label { color: #64748b; }
.variance-val.over { color: #ef4444; }
.variance-val.under { color: #22c55e; }

/* Other Stats Grid */
.other-stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.other-stat-card {
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 8px;
  padding: 14px;
  text-align: center;
}
.other-stat-icon { font-size: 1.4rem; margin-bottom: 4px; }
.other-stat-num { font-size: 1.4rem; font-weight: 700; color: #f1f5f9; line-height: 1.1; }
.other-stat-label { font-size: 0.75rem; color: #64748b; margin-top: 2px; }

/* ─── Room Templates Modal ─────────────────────────────── */
.room-templates-modal {
  max-width: 640px;
  width: 95vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}
.modal-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.template-create-form {
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 16px;
}
.form-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}
.form-row label {
  font-size: 0.8rem;
  color: #94a3b8;
}
.form-row-inline {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
.form-field {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.form-field label {
  font-size: 0.8rem;
  color: #94a3b8;
}
.form-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  color: #cbd5e1;
  cursor: pointer;
}
.btn-small {
  padding: 4px 10px;
  font-size: 0.8rem;
  border-radius: 6px;
}
.templates-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  max-height: 55vh;
}
.template-card {
  background: #0f172a;
  border: 1px solid #1e293b;
  border-radius: 10px;
  padding: 14px;
}
.template-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 6px;
}
.template-card-title {
  font-weight: 600;
  color: #f1f5f9;
  font-size: 0.95rem;
}
.template-card-actions {
  display: flex;
  gap: 4px;
}
.template-card-desc {
  font-size: 0.8rem;
  color: #94a3b8;
  margin-bottom: 8px;
  line-height: 1.4;
}
.template-card-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.template-badge {
  font-size: 0.7rem;
  padding: 2px 7px;
  border-radius: 4px;
  background: #1e293b;
  color: #94a3b8;
}
.template-badge.purpose { background: #1e3a5f; color: #93c5fd; }
.template-badge.mode { background: #2d1f4f; color: #c4b5fd; }
.template-badge.phase { background: #1f3830; color: #6ee7b7; }
.template-card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.shared-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  background: #14532d;
  color: #86efac;
}

/* ─── Gantt Chart ─────────────────────────────────── */
.gantt-wrapper {
  margin: 16px 0;
  border: 1px solid #334155;
  border-radius: 8px;
  overflow: hidden;
  background: #0f172a;
}
.gantt-chart {
  position: relative;
}
.gantt-header-row {
  display: flex;
  background: #1e293b;
  border-bottom: 1px solid #334155;
  position: sticky;
  top: 0;
  z-index: 10;
}
.gantt-data-row {
  display: flex;
  border-bottom: 1px solid #1e293b;
  position: relative;
}
.gantt-rows-area {
  position: relative;
}
.gantt-label-col {
  width: 200px;
  min-width: 200px;
  padding: 8px 12px;
  border-right: 1px solid #334155;
  flex-shrink: 0;
  background: #0f172a;
}
.gantt-timeline-outer {
  flex: 1;
  position: relative;
  height: 48px;
}
.gantt-timeline-header {
  position: relative;
  height: 28px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
}
.gantt-day-label {
  position: absolute;
  font-size: 0.65rem;
  color: #64748b;
  transform: translateX(-50%);
  white-space: nowrap;
  padding-top: 4px;
}
.gantt-day-label.gantt-today {
  color: #f97316;
  font-weight: 600;
}
.gantt-grid-lines {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
}
.gantt-grid-line {
  flex: 1;
  border-right: 1px solid #1e293b;
}
.gantt-grid-line.gantt-today-col {
  background: rgba(249, 115, 22, 0.05);
}
.gantt-today-vline {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #f97316;
  opacity: 0.6;
  z-index: 5;
}
.gantt-bar {
  position: absolute;
  top: 10px;
  height: 28px;
  border-radius: 4px;
  cursor: pointer;
  z-index: 3;
  display: flex;
  align-items: center;
  overflow: hidden;
  transition: opacity 0.15s;
}
.gantt-bar:hover { opacity: 0.85; }
.gantt-bar-pending { background: #334155; border: 1px solid #475569; }
.gantt-bar-in_progress { background: #1e3a5f; border: 1px solid #3b82f6; }
.gantt-bar-completed { background: #14532d; border: 1px solid #22c55e; }
.gantt-bar-fill {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  border-radius: 3px 0 0 3px;
}
.gbf-pending { background: #475569; }
.gbf-in_progress { background: #3b82f6; }
.gbf-completed { background: #22c55e; }
.gantt-bar-label {
  position: relative;
  z-index: 1;
  font-size: 0.65rem;
  color: #fff;
  padding: 0 4px;
  white-space: nowrap;
  font-weight: 500;
}
.gantt-task-name {
  font-size: 0.78rem;
  color: #e2e8f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 3px;
}
.gantt-task-meta {
  display: flex;
  align-items: center;
  gap: 4px;
}
.gantt-priority-dot, .gantt-status-chip {
  font-size: 0.6rem;
}
.gantt-dep-badge {
  font-size: 0.6rem;
  background: #1e3a5f;
  color: #60a5fa;
  padding: 1px 4px;
  border-radius: 3px;
}
.gantt-dep-connector {
  position: absolute;
  width: 6px;
  height: 6px;
  background: #60a5fa;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  z-index: 4;
}
.gantt-svg-overlay {
  position: absolute;
  top: 28px;
  left: 200px;
  right: 0;
  pointer-events: none;
  z-index: 2;
}
.gantt-empty {
  padding: 40px 0;
  text-align: center;
}
.gantt-empty .empty-icon { font-size: 2rem; margin-bottom: 8px; }
.gantt-empty .empty-text { font-size: 1rem; color: #94a3b8; margin-bottom: 4px; }
.gantt-empty .empty-sub { font-size: 0.8rem; color: #64748b; }

/* Participants Tab */
.participant-summary-bar {
  display: flex;
  gap: 16px;
  padding: 12px 16px;
  background: #13131f;
  border-radius: 8px;
  margin-bottom: 16px;
}
.participant-summary-bar .summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
}
.participant-summary-bar .summary-value {
  font-size: 1.2rem;
  font-weight: 700;
  color: #818cf8;
}
.participant-summary-bar .summary-label {
  font-size: 0.72rem;
  color: #64748b;
  margin-top: 2px;
}
.participant-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.participant-card {
  background: #13131f;
  border-radius: 10px;
  padding: 14px 16px;
  border: 1px solid #1e1e32;
}
.participant-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.participant-card .participant-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #4338ca;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 0.9rem;
  flex-shrink: 0;
}
.participant-card .participant-info {
  flex: 1;
}
.participant-card .participant-name {
  font-size: 0.95rem;
  font-weight: 600;
  color: #d0d0e8;
}
.participant-card .participant-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 3px;
  flex-wrap: wrap;
}
.level-badge {
  background: #1e1e32;
  color: #a5b4fc;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 0.68rem;
  font-weight: 600;
}
.role-badge {
  background: #1e1e32;
  color: #86efac;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 0.68rem;
}
.rooms-badge {
  color: #64748b;
  font-size: 0.72rem;
}
.participant-stats {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.participant-stats .stat-item {
  flex: 1;
  background: #0a0a14;
  border-radius: 6px;
  padding: 6px 4px;
  text-align: center;
}
.participant-stats .stat-num {
  font-size: 1.1rem;
  font-weight: 700;
  color: #d0d0e8;
}
.participant-stats .stat-lbl {
  font-size: 0.62rem;
  color: #4a4a6a;
  margin-top: 1px;
}
.participant-bar {
  background: #0a0a14;
  border-radius: 6px;
  padding: 8px 10px;
}
.participant-bar .bar-label {
  font-size: 0.68rem;
  color: #4a4a6a;
  margin-bottom: 5px;
}
.participant-bar .bar-track {
  height: 6px;
  background: #1e1e32;
  border-radius: 3px;
  overflow: hidden;
  display: flex;
}
.participant-bar .bar-fill {
  height: 100%;
  transition: width 0.3s ease;
}
.participant-bar .bar-speech { background: #818cf8; }
.participant-bar .bar-challenge { background: #f87171; }
.participant-bar .bar-response { background: #34d399; }
.participant-bar .bar-legend {
  display: flex;
  gap: 10px;
  margin-top: 5px;
}
.participant-bar .legend-item {
  font-size: 0.62rem;
  color: #4a4a6a;
  display: flex;
  align-items: center;
  gap: 3px;
}
.participant-bar .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}
.participant-bar .dot-speech { background: #818cf8; }
.participant-bar .dot-challenge { background: #f87171; }
.participant-bar .dot-response { background: #34d399; }

/* Action Items Tab */
.filter-select {
  padding: 4px 8px;
  font-size: 0.8rem;
  min-width: 100px;
}
.tab-header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.action-items-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 4px;
}
.action-item-card {
  background: #12121e;
  border: 1px solid #1e1e32;
  border-radius: 8px;
  padding: 14px 16px;
  transition: border-color 0.2s;
}
.action-item-card:hover {
  border-color: #3b3b5c;
}
.action-item-card.action-item-completed {
  opacity: 0.7;
}
.action-item-card.action-item-completed .action-item-title {
  text-decoration: line-through;
  color: #6b7280;
}
.action-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.action-item-status .status-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 600;
}
.badge-open { background: #1e1e32; color: #fcd34d; }
.badge-in_progress { background: #1e1e32; color: #60a5fa; }
.badge-completed { background: #1e1e32; color: #34d399; }
.action-item-priority {
  font-size: 0.72rem;
  font-weight: 600;
}
.priority-critical { color: #ef4444; }
.priority-high { color: #f97316; }
.priority-medium { color: #eab308; }
.priority-low { color: #22c55e; }
.action-item-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: #d0d0e8;
  margin-bottom: 4px;
}
.action-item-desc {
  font-size: 0.8rem;
  color: #6b7280;
  margin-bottom: 8px;
  line-height: 1.4;
}
.action-item-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 0.72rem;
  color: #4a4a6a;
  margin-bottom: 10px;
}
.action-item-meta span {
  display: flex;
  align-items: center;
  gap: 3px;
}
.action-item-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px solid #1e1e32;
}
.action-item-time {
  font-size: 0.68rem;
  color: #4a4a6a;
}
.action-item-actions {
  display: flex;
  gap: 6px;
}
.btn-complete {
  background: #065f46;
  color: #6ee7b7;
  border: 1px solid #065f46;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 0.72rem;
  cursor: pointer;
}
.btn-complete:hover {
  background: #047857;
}
.btn-delete {
  background: transparent;
  color: #ef4444;
  border: 1px solid #ef4444;
  padding: 3px 10px;
  border-radius: 4px;
  font-size: 0.72rem;
  cursor: pointer;
}
.btn-delete:hover {
  background: #7f1d1d;
}

/* Meeting Minutes Styles */
.meeting-minutes-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 0 4px;
}
.meeting-minutes-card {
  background: #12121e;
  border: 1px solid #1e1e32;
  border-radius: 8px;
  padding: 14px 16px;
  cursor: pointer;
  transition: border-color 0.2s;
}
.meeting-minutes-card:hover {
  border-color: #3b3b5c;
}
.meeting-minutes-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.meeting-minutes-title {
  font-weight: 600;
  font-size: 0.95rem;
  color: #e2e8f0;
}
.meeting-minutes-time {
  font-size: 0.68rem;
  color: #4a4a6a;
}
.meeting-minutes-summary {
  font-size: 0.82rem;
  color: #94a3b8;
  margin-bottom: 8px;
}
.meeting-minutes-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.72rem;
  margin-right: 6px;
  margin-bottom: 4px;
}
.meeting-minutes-badge.decisions {
  background: #1e1e32;
  color: #c4b5fd;
}
.meeting-minutes-badge.actions {
  background: #1e1e32;
  color: #6ee7b7;
}
.meeting-minutes-meta {
  display: flex;
  gap: 12px;
  font-size: 0.72rem;
  color: #64748b;
  margin-top: 8px;
}
.meeting-minutes-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
.minutes-detail-meta {
  display: flex;
  gap: 16px;
  font-size: 0.82rem;
  color: #64748b;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #1e1e32;
}
.minutes-section {
  margin-bottom: 16px;
}
.minutes-section-title {
  font-weight: 600;
  font-size: 0.85rem;
  color: #e2e8f0;
  margin-bottom: 6px;
}
.minutes-section-content {
  font-size: 0.82rem;
  color: #94a3b8;
  line-height: 1.5;
}
.minutes-content {
  background: #0a0a14;
  border: 1px solid #1e1e32;
  border-radius: 6px;
  padding: 12px;
  font-size: 0.78rem;
  color: #94a3b8;
  white-space: pre-wrap;
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
}
.meeting-minutes-detail-modal {
  max-width: 700px;
  max-height: 80vh;
  overflow-y: auto;
}
</style>
