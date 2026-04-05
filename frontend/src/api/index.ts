import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_URL,
  timeout: 10000,
})

export default api

// Plans
export const createPlan = (data: { title: string; topic: string; requirements?: string[] }) =>
  api.post('/plans', data)

export const copyPlan = (planId: string, data?: { performed_by?: string }) =>
  api.post(`/plans/${planId}/copy`, data)

export const getPlan = (planId: string) =>
  api.get(`/plans/${planId}`)

export const listPlans = () =>
  api.get('/plans')

export const searchPlans = (query: string, params?: { status?: string; limit?: number; offset?: number }) =>
  api.get('/plans/search', { params: { q: query, ...params } })

export const searchRooms = (query: string, params?: { plan_id?: string; phase?: string; tags?: string; limit?: number; offset?: number }) =>
  api.get('/rooms/search', { params: { q: query, ...params } })

export const getRoomsByPlan = (planId: string) =>
  api.get(`/plans/${planId}/rooms`)

// Room Tags
export const getRoomTags = (roomId: string) =>
  api.get(`/rooms/${roomId}/tags`)

export const updateRoomTags = (roomId: string, tags: string[]) =>
  api.patch(`/rooms/${roomId}/tags`, { tags })

export const addRoomTags = (roomId: string, tags: string[]) =>
  api.post(`/rooms/${roomId}/tags/add`, { tags })

export const removeRoomTags = (roomId: string, tags: string[]) =>
  api.post(`/rooms/${roomId}/tags/remove`, { tags })

// Rooms
export const getRoom = (roomId: string) =>
  api.get(`/rooms/${roomId}`)

export const addParticipant = (roomId: string, data: { agent_id: string; name: string; level: number; role?: string }) =>
  api.post(`/rooms/${roomId}/participants`, data)

export const getPhase = (roomId: string) =>
  api.get(`/rooms/${roomId}/phase`)

export const transitionPhase = (roomId: string, toPhase: string) =>
  api.post(`/rooms/${roomId}/phase`, null, { params: { to_phase: toPhase } })

export const addSpeech = (roomId: string, data: { agent_id: string; content: string }) =>
  api.post(`/rooms/${roomId}/speech`, data)

export const getRoomPhaseTimeline = (roomId: string) =>
  api.get(`/rooms/${roomId}/phase-timeline`)

// Approval
export const startApproval = (planId: string, data: { initiator_id: string; initiator_name: string; skip_levels?: number[] }) =>
  api.post(`/plans/${planId}/approval/start`, data)

export const getApproval = (planId: string) =>
  api.get(`/plans/${planId}/approval`)

export const approvalAction = (planId: string, level: number, data: { action: string; actor_id: string; actor_name: string; comment?: string }) =>
  api.post(`/plans/${planId}/approval/${level}/action`, null, { params: { action: data.action, actor_id: data.actor_id, actor_name: data.actor_name, comment: data.comment || '' } })

export const getApprovalLevels = (planId: string) =>
  api.get(`/plans/${planId}/approval/levels`)

// WebSocket
export const wsUrl = (roomId: string) => {
  const wsProtocol = API_URL.startsWith('https') ? 'wss' : 'ws'
  const base = API_URL.replace(/^https?:\/\//, '')
  return `${wsProtocol}://${base}/ws/${roomId}`
}

// ─── Activities / Audit Trail ────────────────────────────────────────────────
export const listActivities = (planId?: string, limit = 100, offset = 0) =>
  api.get('/activities', { params: { plan_id: planId, limit, offset } })

export const getActivityStats = (planId?: string) =>
  api.get('/activities/stats', { params: { plan_id: planId } })

export const getActivity = (activityId: string) =>
  api.get(`/activities/${activityId}`)

export const listRoomActivities = (roomId: string, limit = 100, offset = 0) =>
  api.get(`/rooms/${roomId}/activities`, { params: { limit, offset } })

export const listVersionActivities = (planId: string, version: string, limit = 100, offset = 0) =>
  api.get(`/plans/${planId}/versions/${version}/activities`, { params: { limit, offset } })

// ─── Decisions ────────────────────────────────────────────────────────────────
export const listDecisions = (planId: string, version: string) =>
  api.get(`/plans/${planId}/versions/${version}/decisions`)

export const getDecision = (planId: string, version: string, decisionId: string) =>
  api.get(`/plans/${planId}/versions/${version}/decisions/${decisionId}`)

export const createDecision = (planId: string, version: string, data: {
  title: string
  decision_text: string
  description?: string
  rationale?: string
  alternatives_considered?: string[]
  agreed_by?: string[]
  disagreed_by?: string[]
  decided_by?: string
  room_id?: string
}) => api.post(`/plans/${planId}/versions/${version}/decisions`, data)

export const updateDecision = (planId: string, version: string, decisionId: string, data: Record<string, unknown>) =>
  api.patch(`/plans/${planId}/versions/${version}/decisions/${decisionId}`, data)

// ─── Edicts ──────────────────────────────────────────────────────────────────
export const listEdicts = (planId: string, version: string) =>
  api.get(`/plans/${planId}/versions/${version}/edicts`)

export const getEdict = (planId: string, version: string, edictId: string) =>
  api.get(`/plans/${planId}/versions/${version}/edicts/${edictId}`)

export const createEdict = (planId: string, version: string, data: {
  title: string
  content: string
  decision_id?: string
  issued_by: string
  effective_from?: string
  recipients?: number[]
  status?: string
}) => api.post(`/plans/${planId}/versions/${version}/edicts`, data)

export const updateEdict = (planId: string, version: string, edictId: string, data: Record<string, unknown>) =>
  api.patch(`/plans/${planId}/versions/${version}/edicts/${edictId}`, data)

export const deleteEdict = (planId: string, version: string, edictId: string) =>
  api.delete(`/plans/${planId}/versions/${version}/edicts/${edictId}`)

export const acknowledgeEdict = (planId: string, version: string, edictId: string, data: {
  acknowledged_by: string
  level: number
  comment?: string
}) => api.post(`/plans/${planId}/versions/${version}/edicts/${edictId}/acknowledgments`, data)

export const listEdictAcknowledgments = (planId: string, version: string, edictId: string) =>
  api.get(`/plans/${planId}/versions/${version}/edicts/${edictId}/acknowledgments`)

export const deleteEdictAcknowledgment = (planId: string, version: string, edictId: string, ackId: string) =>
  api.delete(`/plans/${planId}/versions/${version}/edicts/${edictId}/acknowledgments/${ackId}`)

// ─── Tasks ────────────────────────────────────────────────────────────────────
export const listTasks = (planId: string, version: string) =>
  api.get(`/plans/${planId}/versions/${version}/tasks`)

export const createTask = (planId: string, version: string, data: {
  title: string
  description?: string
  priority?: 'low' | 'medium' | 'high' | 'critical'
  assigned_to?: string
  estimated_hours?: number
  depends_on?: string[]
}) => api.post(`/plans/${planId}/versions/${version}/tasks`, data)

export const getTask = (planId: string, version: string, taskId: string) =>
  api.get(`/plans/${planId}/versions/${version}/tasks/${taskId}`)

export const updateTask = (planId: string, version: string, taskId: string, data: Record<string, unknown>) =>
  api.patch(`/plans/${planId}/versions/${version}/tasks/${taskId}`, data)

export const updateTaskProgress = (planId: string, version: string, taskId: string, data: { progress: number; status?: string }) =>
  api.patch(`/plans/${planId}/versions/${version}/tasks/${taskId}/progress`, data)

export const getTaskMetrics = (planId: string, version: string) =>
  api.get(`/plans/${planId}/versions/${version}/tasks/metrics`)

// ─── Sub-Tasks ─────────────────────────────────────────────────────────────────
export const listSubTasks = (planId: string, version: string, taskId: string) =>
  api.get(`/plans/${planId}/versions/${version}/tasks/${taskId}/sub-tasks`)

export const createSubTask = (planId: string, version: string, taskId: string, data: { title: string; description?: string }) =>
  api.post(`/plans/${planId}/versions/${version}/tasks/${taskId}/sub-tasks`, data)

export const updateSubTask = (planId: string, version: string, taskId: string, subTaskId: string, data: Record<string, unknown>) =>
  api.patch(`/plans/${planId}/versions/${version}/tasks/${taskId}/sub-tasks/${subTaskId}`, data)

// ─── Task Comments ──────────────────────────────────────────────────────────────
export const listTaskComments = (planId: string, version: string, taskId: string) =>
  api.get(`/plans/${planId}/versions/${version}/tasks/${taskId}/comments`)

export const createTaskComment = (planId: string, version: string, taskId: string, data: { author_name: string; content: string; author_id?: string; author_level?: number }) =>
  api.post(`/plans/${planId}/versions/${version}/tasks/${taskId}/comments`, data)

// ─── Task Checkpoints ──────────────────────────────────────────────────────────
export const listTaskCheckpoints = (planId: string, version: string, taskId: string) =>
  api.get(`/plans/${planId}/versions/${version}/tasks/${taskId}/checkpoints`)

export const createTaskCheckpoint = (planId: string, version: string, taskId: string, data: { name: string; status?: string }) =>
  api.post(`/plans/${planId}/versions/${version}/tasks/${taskId}/checkpoints`, data)

// ─── Risks ─────────────────────────────────────────────────────────────────────
export const listRisks = (planId: string, version: string) =>
  api.get(`/plans/${planId}/versions/${version}/risks`)

export const getRisk = (planId: string, version: string, riskId: string) =>
  api.get(`/plans/${planId}/versions/${version}/risks/${riskId}`)

export const createRisk = (planId: string, version: string, data: {
  title: string
  description?: string
  probability?: string
  impact?: string
  mitigation?: string
  contingency?: string
  status?: string
}) => api.post(`/plans/${planId}/versions/${version}/risks`, data)

export const updateRisk = (planId: string, version: string, riskId: string, data: Record<string, unknown>) =>
  api.patch(`/plans/${planId}/versions/${version}/risks/${riskId}`, data)

export const deleteRisk = (planId: string, version: string, riskId: string) =>
  api.delete(`/plans/${planId}/versions/${version}/risks/${riskId}`)

// ─── Constraints ───────────────────────────────────────────────────────────────
export const listConstraints = (planId: string) =>
  api.get(`/plans/${planId}/constraints`)

export const createConstraint = (planId: string, data: { type: string; value: string; unit?: string; description?: string }) =>
  api.post(`/plans/${planId}/constraints`, data)

export const updateConstraint = (planId: string, constraintId: string, data: Record<string, unknown>) =>
  api.patch(`/plans/${planId}/constraints/${constraintId}`, data)

export const deleteConstraint = (planId: string, constraintId: string) =>
  api.delete(`/plans/${planId}/constraints/${constraintId}`)

// ─── Stakeholders ──────────────────────────────────────────────────────────────
export const listStakeholders = (planId: string) =>
  api.get(`/plans/${planId}/stakeholders`)

export const createStakeholder = (planId: string, data: {
  name: string
  level?: number
  interest?: string
  influence?: string
  description?: string
}) => api.post(`/plans/${planId}/stakeholders`, data)

export const updateStakeholder = (planId: string, stakeholderId: string, data: Record<string, unknown>) =>
  api.patch(`/plans/${planId}/stakeholders/${stakeholderId}`, data)

export const deleteStakeholder = (planId: string, stakeholderId: string) =>
  api.delete(`/plans/${planId}/stakeholders/${stakeholderId}`)

// ─── Analytics ─────────────────────────────────────────────────────────────────
export const getPlanAnalytics = (planId: string) =>
  api.get(`/plans/${planId}/analytics`)

// ─── Requirements ──────────────────────────────────────────────────────────────
export const listRequirements = (planId: string) =>
  api.get(`/plans/${planId}/requirements`)

export const getRequirementsStats = (planId: string) =>
  api.get(`/plans/${planId}/requirements/stats`)

export const createRequirement = (planId: string, data: {
  description: string
  priority?: string
  category?: string
  status?: string
  notes?: string
}) => api.post(`/plans/${planId}/requirements`, data)

export const updateRequirement = (planId: string, reqId: string, data: Record<string, unknown>) =>
  api.patch(`/plans/${planId}/requirements/${reqId}`, data)

export const deleteRequirement = (planId: string, reqId: string) =>
  api.delete(`/plans/${planId}/requirements/${reqId}`)

// ─── Room History & Context ────────────────────────────────────────────────────
export const getRoomHistory = (roomId: string, limit = 100) =>
  api.get(`/rooms/${roomId}/history`, { params: { limit } })

export const getRoomContext = (roomId: string, level?: number) =>
  api.get(`/rooms/${roomId}/context`, { params: { level } })

export const searchRoomMessages = (roomId: string, query: string, limit = 50) =>
  api.get(`/rooms/${roomId}/messages/search`, { params: { q: query, limit } })

// ─── Escalations ───────────────────────────────────────────────────────────────
export const getRoomEscalations = (roomId: string) =>
  api.get(`/rooms/${roomId}/escalations`)

export const getPlanEscalations = (planId: string) =>
  api.get(`/plans/${planId}/escalations`)

export const getEscalation = (escalationId: string) =>
  api.get(`/escalations/${escalationId}`)

export const updateEscalation = (escalationId: string, data: { action: string; actor_id?: string; actor_name?: string; comment?: string }) =>
  api.patch(`/escalations/${escalationId}`, data)

export const escalateRoom = (roomId: string, data: {
  from_level: number
  to_level: number
  mode?: string
  escalation_path?: number[]
  content?: Record<string, unknown>
  notes?: string
}) => api.post(`/rooms/${roomId}/escalate`, data)

export const getEscalationPath = (roomId: string, fromLevel: number, mode: string) =>
  api.get(`/rooms/${roomId}/escalation-path`, { params: { from_level: fromLevel, mode } })

// ─── Room Hierarchy ─────────────────────────────────────────────────────────────
export const getRoomHierarchy = (roomId: string) =>
  api.get(`/rooms/${roomId}/hierarchy`)

export const linkRoom = (roomId: string, data: { parent_room_id?: string; child_rooms?: string[]; related_rooms?: string[] }) =>
  api.post(`/rooms/${roomId}/link`, data)

export const concludeRoom = (roomId: string, data: { summary?: string; conclusion?: string }) =>
  api.post(`/rooms/${roomId}/conclude`, data)

// ─── Plan Export ────────────────────────────────────────────────────────────────
export const exportPlanMarkdown = (planId: string) =>
  api.get(`/plans/${planId}/export`)

export const exportVersionMarkdown = (planId: string, version: string) =>
  api.get(`/plans/${planId}/versions/${version}/export`)

// ─── Problem Handling ─────────────────────────────────────────────────────────
export const getProblems = (planId: string) =>
  api.get(`/plans/${planId}/problems`)

export const getProblem = (issueId: string) =>
  api.get(`/problems/${issueId}`)

export const analyzeProblem = (issueId: string, data: {
  root_cause: string
  root_cause_confidence?: number
  impact_scope?: string
  affected_tasks?: string[]
  progress_impact?: string
  severity_reassessment?: string
  solution_options?: Array<{ description: string; pros: string[]; cons: string[] }>
  recommended_option?: number
  requires_discussion?: boolean
  discussion_needed_aspects?: string[]
}) => api.post(`/problems/${issueId}/analysis`, data)

export const discussProblem = (issueId: string, data: {
  participants?: Array<{ id: string; name: string; level: number }>
  discussion_focus?: Array<{ aspect: string; notes: string }>
  proposed_solutions?: Array<{ solution: string; proposed_by: string }>
  votes?: Record<string, string>
}) => api.post(`/problems/${issueId}/discussion`, data)

export const updatePlan = (planId: string, data: {
  new_version: string
  parent_version: string
  update_type?: string
  description?: string
  changes?: Record<string, unknown>
  task_updates?: Array<{ task_id: string; status: string }>
  new_tasks?: Array<{ title: string; description?: string; owner_id?: string }>
  cancelled_tasks?: string[]
}) => api.post(`/plans/${planId}/plan-update`, data)

export const resumeExecution = (planId: string, data: {
  new_version: string
  resuming_from_task?: number
  checkpoint?: string
  resume_instructions?: Record<string, unknown>
}) => api.post(`/plans/${planId}/resuming`, data)

// ─── Version Management ────────────────────────────────────────────────────────
export const createVersion = (planId: string, data: {
  type: 'fix' | 'enhancement' | 'major'
  description?: string
  tasks?: unknown[]
  decisions?: string[]
}) => api.post(`/plans/${planId}/versions`, data)

export const getVersionPlanJson = (planId: string, version: string) =>
  api.get(`/plans/${planId}/versions/${version}/plan.json`)

export const getPlanJson = (planId: string) =>
  api.get(`/plans/${planId}/plan.json`)

export const getVersionIndex = (planId: string, version: string) =>
  api.get(`/plans/${planId}/versions/${version}/INDEX.md`)

// ─── Snapshots ─────────────────────────────────────────────────────────────────
export const listSnapshots = (planId: string, version: string) =>
  api.get(`/plans/${planId}/versions/${version}/snapshots`)

export const getSnapshot = (planId: string, version: string, snapshotId: string) =>
  api.get(`/plans/${planId}/versions/${version}/snapshots/${snapshotId}`)

// ─── Debate ────────────────────────────────────────────────────────────────────
export const getDebateState = (roomId: string) =>
  api.get(`/rooms/${roomId}/debate/state`)

export const createDebatePoint = (roomId: string, data: { content: string; point_type?: string }) =>
  api.post(`/rooms/${roomId}/debate/points`, data)

export const submitDebatePosition = (roomId: string, data: {
  point_id: string
  position: 'support' | 'oppose' | 'neutral'
  reasoning?: string
  agent_id?: string
}) => api.post(`/rooms/${roomId}/debate/position`, data)

export const submitDebateExchange = (roomId: string, data: {
  exchange_type: 'challenge' | 'response' | 'evidence' | 'update_position' | 'consensus_building'
  from_agent: string
  target_agent?: string
  content: string
}) => api.post(`/rooms/${roomId}/debate/exchange`, data)

export const advanceDebateRound = (roomId: string) =>
  api.post(`/rooms/${roomId}/debate/round`)

// ─── Notifications ─────────────────────────────────────────────────────────────
export type NotificationType =
  | 'task_assigned'
  | 'task_completed'
  | 'task_blocked'
  | 'problem_reported'
  | 'problem_resolved'
  | 'approval_requested'
  | 'approval_completed'
  | 'edict_published'
  | 'escalation_received'

export interface Notification {
  notification_id: string
  plan_id?: string
  version?: string
  room_id?: string
  task_id?: string
  recipient_id: string
  recipient_level?: number
  type: NotificationType
  title: string
  message?: string
  read: boolean
  created_at: string
  read_at?: string
}

export const createNotification = (data: {
  plan_id?: string
  version?: string
  room_id?: string
  task_id?: string
  recipient_id: string
  recipient_level?: number
  type: NotificationType
  title: string
  message?: string
}) => api.post('/notifications', data)

export const listNotifications = (params?: {
  recipient_id?: string
  plan_id?: string
  room_id?: string
  type?: NotificationType
  read?: boolean
  limit?: number
  offset?: number
}) => api.get('/notifications', { params })

export const getNotification = (notificationId: string) =>
  api.get(`/notifications/${notificationId}`)

export const markNotificationRead = (notificationId: string) =>
  api.patch(`/notifications/${notificationId}/read`)

export const markAllNotificationsRead = (recipientId: string) =>
  api.patch('/notifications/read-all', null, { params: { recipient_id: recipientId } })

export const getUnreadNotificationCount = (recipientId: string) =>
  api.get('/notifications/unread-count', { params: { recipient_id: recipientId } })

export const deleteNotification = (notificationId: string) =>
  api.delete(`/notifications/${notificationId}`)

// ─── Task Dependencies ──────────────────────────────────────────────────────────
export const getTaskDependencyGraph = (planId: string, version: string) =>
  api.get(`/plans/${planId}/versions/${version}/tasks/dependency-graph`)

export const getBlockedTasks = (planId: string, version: string) =>
  api.get(`/plans/${planId}/versions/${version}/tasks/blocked`)

export const validateTaskDependencies = (planId: string, version: string, data: {
  dependencies: string[]
}) => api.post(`/plans/${planId}/versions/${version}/tasks/validate-dependencies`, data)

// ─── Room Templates ─────────────────────────────────────────────────────────────
export const createRoomTemplate = (data: {
  name: string;
  description?: string;
  purpose?: string;
  mode?: string;
  default_phase?: string;
  settings?: Record<string, any>;
  is_shared?: boolean;
}) => api.post('/room-templates', data)

export const listRoomTemplates = (params?: { purpose?: string; is_shared?: boolean }) =>
  api.get('/room-templates', { params })

export const getRoomTemplate = (templateId: string) =>
  api.get(`/room-templates/${templateId}`)

export const updateRoomTemplate = (templateId: string, data: Partial<{
  name: string;
  description: string;
  purpose: string;
  mode: string;
  default_phase: string;
  settings: Record<string, any>;
  is_shared: boolean;
}>) => api.patch(`/room-templates/${templateId}`, data)

export const deleteRoomTemplate = (templateId: string) =>
  api.delete(`/room-templates/${templateId}`)

export const createRoomFromTemplate = (planId: string, templateId: string, data?: { topic?: string; version?: string }) =>
  api.post(`/plans/${planId}/rooms/from-template/${templateId}`, data)

// Step 68: Plan Template API
export const createPlanTemplate = (data: {
  name: string;
  description?: string;
  plan_content?: Record<string, any>;
  tags?: string[];
  is_shared?: boolean;
}) => api.post('/plan-templates', data)

export const listPlanTemplates = (params?: { tag?: string; is_shared?: boolean; created_by?: string; search?: string }) =>
  api.get('/plan-templates', { params })

export const getPlanTemplate = (templateId: string) =>
  api.get(`/plan-templates/${templateId}`)

export const updatePlanTemplate = (templateId: string, data: Partial<{
  name: string;
  description: string;
  plan_content: Record<string, any>;
  tags: string[];
  is_shared: boolean;
}>) => api.patch(`/plan-templates/${templateId}`, data)

export const deletePlanTemplate = (templateId: string) =>
  api.delete(`/plan-templates/${templateId}`)

export const createPlanFromTemplate = (templateId: string, data?: { title?: string; topic?: string }) =>
  api.post(`/plan-templates/${templateId}/create-plan`, data)

// Step 65: Task Time Tracking API
export const createTimeEntry = (planId: string, version: string, taskId: string, data: {
  user_name?: string;
  hours: number;
  description?: string;
  notes?: string;
}) => api.post(`/plans/${planId}/versions/${version}/tasks/${taskId}/time-entries`, data)

export const listTimeEntries = (planId: string, version: string, taskId: string) =>
  api.get(`/plans/${planId}/versions/${version}/tasks/${taskId}/time-entries`)

export const getTimeSummary = (planId: string, version: string, taskId: string) =>
  api.get(`/plans/${planId}/versions/${version}/tasks/${taskId}/time-summary`)

export const deleteTimeEntry = (entryId: string) =>
  api.delete(`/time-entries/${entryId}`)
