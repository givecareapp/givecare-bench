import process from 'node:process'

import {
  GiveCareOrchestrator,
  buildGiveCareTurnInput,
  createGiveCarePiPackage,
  getModel,
} from '../../../../../give-care-mono/packages/pi-orchestrator/src/index.ts'
import type { GiveCarePolicyRuntime } from '../../../../../give-care-mono/packages/pi-orchestrator/src/givecare/extensions.ts'
import type {
  DiagnosticEventInput,
  FilingProfile,
  GiveCareRuntime,
} from '../../../../../give-care-mono/packages/pi-orchestrator/src/givecare/runtime.ts'

type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

type BridgeCommand = 'healthcheck' | 'run_turn'

interface BridgeMemory {
  key: string
  value: string
  confidence?: number
}

interface BridgeRecentMessage {
  direction: 'inbound' | 'outbound'
  text: string
}

interface BridgeConversationState {
  caregiverId: string
  conversationId: string
  inboundMessageId: string
  currentLoop: string
  currentStage?: string
  riskLevel: RiskLevel
  memory: BridgeMemory[]
  recentMessages?: BridgeRecentMessage[]
  incomingText: string
  skillDiscovery?: string
  pendingPromptType?: string
  pendingPromptInstrument?: string
  assessmentOverdue?: boolean
  benefitsScreeningDue?: boolean
  sdoh30Due?: boolean
  flaggedZoneCount?: number
  openAssessment?: {
    instrumentId: string
    assessmentRunId: string
    responsesAnswered: number
  } | null
  cadence?: { hasSdoh6: boolean; hasSdoh30: boolean; flaggedZoneCount: number }
  skillDiscoveryText?: string
  zipCode?: string
  latitude?: number
  longitude?: number
  bootstrapNeededFacts?: string[]
  bootstrapCollectedFacts?: string[]
  scoreSnapshot?: {
    score: number
    band: string
    bandLabel: string
    confidence: string
    zones: Record<string, number>
    topPressure: { zone: string; label: string; score: number } | null
    trend: { delta7d?: number; delta30d?: number; direction: string }
  } | null
}

interface BridgeFixtures {
  resources?: Array<{ title: string; description: string; url?: string; phone?: string }>
  benefitScreenings?: Array<{
    programId: string
    title: string
    result: string
    applicationUrl?: string
    missingFacts?: string[]
  }>
  benefitSummary?: { eligible: number; maybe: number; notEligible: number }
  nextBenefitQuestion?: string | null
  nearbyResourcesSummary?: string
  filingProfile?: FilingProfile | null
}

interface BridgeInput {
  command: BridgeCommand
  modelName?: string
  apiKey?: string
  temperature?: number
  preferredTemplateId?: string
  preferredThemeId?: string
  mission?: string
  vision?: string
  uxGoals?: string[]
  businessGoals?: string[]
  maxRecentMessages?: number
  now?: number
  conversation?: BridgeConversationState
  fixtures?: BridgeFixtures
}

interface MemoryEntry {
  caregiverId: string
  key: string
  value: string
  confidence: number
}

interface FollowupEntry {
  caregiverId: string
  conversationId: string
  minutes: number
  reason: string
  templateId?: string
  requestKey: string
}

interface CriticalEventEntry {
  caregiverId: string
  conversationId: string
  reason: string
  severity?: string
  details: string
}

interface AlertEntry {
  caregiverId: string
  conversationId: string
  severity: string
  eventType: string
  message: string
  source: string
}

class BenchmarkRuntime implements GiveCareRuntime {
  memories: MemoryEntry[] = []
  followups: FollowupEntry[] = []
  criticalEvents: CriticalEventEntry[] = []
  alerts: AlertEntry[] = []
  diagnostics: DiagnosticEventInput[] = []
  assessmentRuns: Array<{
    runId: string
    caregiverId: string
    instrument: string
    responses: Array<{ questionId: string; value: number }>
    status: 'started' | 'completed' | 'abandoned'
  }> = []
  eligibilityFacts: Array<{
    caregiverId: string
    key: string
    value: string
    confidence: number
    source?: string
  }> = []
  bootstrapPatches: Array<{ caregiverId: string; zipCode?: string }> = []
  resourceOffers: Array<{ category: string }> = []
  resourceLookups: Array<{ category: string; state?: string }> = []
  nearbyQueries: Array<{ zone: string; zipCode?: string }> = []
  screeningsRun: Array<{ caregiverId: string }> = []
  filingProfile: FilingProfile | null = null
  private readonly fixtures: BridgeFixtures
  private runIdCounter = 0

  constructor(fixtures: BridgeFixtures = {}) {
    this.fixtures = fixtures
    this.filingProfile = fixtures.filingProfile ?? null
  }

  async upsertMemory(args: {
    caregiverId: string
    inboundMessageId: string
    key: string
    value: string
    confidence: number
  }): Promise<unknown> {
    const idx = this.memories.findIndex(
      m => m.caregiverId === args.caregiverId && m.key === args.key
    )
    const entry = {
      caregiverId: args.caregiverId,
      key: args.key,
      value: args.value,
      confidence: args.confidence,
    }
    if (idx >= 0) {
      this.memories[idx] = entry
    } else {
      this.memories.push(entry)
    }
    return { ok: true }
  }

  async enqueueFollowup(args: {
    caregiverId: string
    conversationId: string
    minutes: number
    reason: string
    templateId?: string
    requestKey: string
    cancelPendingSameTemplate: boolean
  }): Promise<unknown> {
    this.followups.push({
      caregiverId: args.caregiverId,
      conversationId: args.conversationId,
      minutes: args.minutes,
      reason: args.reason,
      templateId: args.templateId,
      requestKey: args.requestKey,
    })
    return { ok: true }
  }

  async startAssessmentRun(args: {
    caregiverId: string
    conversationId: string
    instrument: string
  }): Promise<{ runId: string }> {
    const runId = `bench-run-${++this.runIdCounter}`
    this.assessmentRuns.push({
      runId,
      caregiverId: args.caregiverId,
      instrument: args.instrument,
      responses: [],
      status: 'started',
    })
    return { runId }
  }

  async submitAssessmentRun(args: {
    runId: string
    responses: Array<{ questionId: string; value: number }>
  }): Promise<unknown> {
    const run = this.assessmentRuns.find(r => r.runId === args.runId)
    if (run) {
      run.responses = args.responses
      run.status = 'completed'
    }
    return { ok: true }
  }

  async getSdoh30QuestionPlan(args: {
    flaggedZones: string[]
    maxQuestionsPerZone?: number
    maxQuestions?: number
  }): Promise<{
    flaggedZones: string[]
    questionIds: string[]
    questions: Array<{ id: string; prompt: string; zone: string; min: number; max: number }>
    questionCount: number
    maxQuestions: number
  }> {
    const maxQuestions = args.maxQuestions ?? 10
    return {
      flaggedZones: args.flaggedZones,
      questionIds: ['q1', 'q2'],
      questions: [
        {
          id: 'q1',
          prompt: 'How often do you feel overwhelmed?',
          zone: args.flaggedZones[0] ?? 'P1',
          min: 0,
          max: 4,
        },
        {
          id: 'q2',
          prompt: 'How supported do you feel day to day?',
          zone: args.flaggedZones[0] ?? 'P1',
          min: 0,
          max: 4,
        },
      ],
      questionCount: 2,
      maxQuestions,
    }
  }

  async abandonAssessmentRun(args: { runId: string }): Promise<unknown> {
    const run = this.assessmentRuns.find(r => r.runId === args.runId)
    if (run) run.status = 'abandoned'
    return { ok: true }
  }

  async upsertEligibilityFact(args: {
    caregiverId: string
    key: string
    value: string
    confidence: number
    source?: string
  }): Promise<unknown> {
    const idx = this.eligibilityFacts.findIndex(
      f => f.caregiverId === args.caregiverId && f.key === args.key
    )
    const entry = {
      caregiverId: args.caregiverId,
      key: args.key,
      value: args.value,
      confidence: args.confidence,
      source: args.source,
    }
    if (idx >= 0) {
      this.eligibilityFacts[idx] = entry
    } else {
      this.eligibilityFacts.push(entry)
    }
    return { ok: true }
  }

  async screenBenefits(args: { caregiverId: string; conversationId: string }): Promise<{
    screenings: Array<{
      programId: string
      title: string
      result: string
      applicationUrl?: string
      missingFacts?: string[]
    }>
    nextQuestion: string | null
    summary: { eligible: number; maybe: number; notEligible: number }
  }> {
    this.screeningsRun.push({ caregiverId: args.caregiverId })
    const screenings =
      this.fixtures.benefitScreenings ?? [
        {
          programId: 'snap',
          title: 'SNAP',
          result: 'eligible',
          applicationUrl: 'https://example.com/snap',
          missingFacts: [],
        },
        {
          programId: 'medicaid',
          title: 'Medicaid',
          result: 'maybe',
          missingFacts: ['monthly income'],
        },
      ]
    const summary =
      this.fixtures.benefitSummary ?? {
        eligible: screenings.filter(item => item.result === 'eligible').length,
        maybe: screenings.filter(item => item.result === 'maybe').length,
        notEligible: screenings.filter(item => item.result === 'not_eligible').length,
      }
    return {
      screenings,
      nextQuestion: this.fixtures.nextBenefitQuestion ?? null,
      summary,
    }
  }

  async offerResource(args: { category: string }): Promise<string[]> {
    this.resourceOffers.push({ category: args.category })
    return [`${args.category} support`, `${args.category} caregiver guide`]
  }

  async lookupResources(args: {
    category: string
    state?: string
    zipPrefix?: string
    language?: string
    limit?: number
  }): Promise<Array<{ title: string; description: string; url?: string; phone?: string }>> {
    this.resourceLookups.push({ category: args.category, state: args.state })
    const fallback = [
      {
        title: `${args.category} support line`,
        description: 'Deterministic benchmark fixture resource',
        url: 'https://example.com/resource',
        phone: '800-555-0100',
      },
    ]
    return this.fixtures.resources ?? fallback
  }

  async patchCaregiverBootstrap(args: {
    caregiverId: string
    zipCode?: string
    updatedAt: number
  }): Promise<unknown> {
    this.bootstrapPatches.push({ caregiverId: args.caregiverId, zipCode: args.zipCode })
    return { ok: true }
  }

  async queryNearbyResources(args: {
    zone: string
    zipCode?: string
    latitude?: number
    longitude?: number
    freeTextQuery?: string
  }): Promise<{ status: string; summary: string; resources: unknown[]; query?: string }> {
    this.nearbyQueries.push({ zone: args.zone, zipCode: args.zipCode })
    return {
      status: 'found',
      summary: this.fixtures.nearbyResourcesSummary ?? `Found nearby ${args.zone} support options.`,
      resources: this.fixtures.resources ?? [],
      query: args.freeTextQuery,
    }
  }

  async appendCriticalEvent(args: {
    caregiverId: string
    conversationId: string
    reason: string
    severity?: 'info' | 'warning' | 'critical'
    details: string
  }): Promise<unknown> {
    this.criticalEvents.push({
      caregiverId: args.caregiverId,
      conversationId: args.conversationId,
      reason: args.reason,
      severity: args.severity,
      details: args.details,
    })
    return { ok: true }
  }

  async sendCriticalAlert(args: {
    caregiverId: string
    conversationId: string
    severity: string
    eventType: string
    message: string
    reason?: string
    details?: string
    source: string
  }): Promise<unknown> {
    this.alerts.push({
      caregiverId: args.caregiverId,
      conversationId: args.conversationId,
      severity: args.severity,
      eventType: args.eventType,
      message: args.message,
      source: args.source,
    })
    return { ok: true }
  }

  async startFilingSession(_args: {
    caregiverId: string
    programId: string
    programTitle: string
    applicationUrl: string
    now: number
  }): Promise<{ status: 'streaming' | 'pre_filled' | 'fallback'; streamingUrl?: string; tinyfishRunId?: string }> {
    return {
      status: 'fallback',
      streamingUrl: undefined,
      tinyfishRunId: undefined,
    }
  }

  async getLatestBenefitApplication(_args: { caregiverId: string; programId: string }): Promise<{
    applicationId: string
    status: 'pending' | 'streaming' | 'pre_filled' | 'fallback'
    createdAt: number
  } | null> {
    return null
  }

  async getCaregiverProfile(_args: { caregiverId: string }): Promise<FilingProfile | null> {
    return this.filingProfile
  }

  async recordDiagnosticEvent(args: DiagnosticEventInput): Promise<unknown> {
    this.diagnostics.push(args)
    return { ok: true }
  }
}

function buildPolicyRuntime(runtime: BenchmarkRuntime, conversation: BridgeConversationState): GiveCarePolicyRuntime {
  return {
    upsertMemory: async args => {
      await runtime.upsertMemory({
        caregiverId: conversation.caregiverId,
        inboundMessageId: conversation.inboundMessageId,
        key: args.key,
        value: args.value,
        confidence: args.confidence,
      })
    },
    enqueueFollowup: async args => {
      await runtime.enqueueFollowup({
        caregiverId: conversation.caregiverId,
        conversationId: conversation.conversationId,
        minutes: args.minutes,
        reason: args.reason,
        templateId: undefined,
        requestKey: `bench_followup_${Date.now()}`,
        cancelPendingSameTemplate: true,
      })
    },
    clearPendingPrompt: async () => {},
    appendCriticalEvent: async args => {
      await runtime.appendCriticalEvent({
        caregiverId: conversation.caregiverId,
        conversationId: conversation.conversationId,
        reason: args.reason,
        severity: 'critical',
        details: args.details ?? '',
      })
    },
    sendCriticalAlert: async args => {
      await runtime.sendCriticalAlert({
        caregiverId: conversation.caregiverId,
        conversationId: conversation.conversationId,
        severity: args.severity,
        eventType: args.eventType,
        message: args.message,
        source: args.source ?? 'benchmark_policy',
      })
    },
    recordDiagnosticEvent: async args => {
      await runtime.recordDiagnosticEvent(args)
    },
  }
}

function resolveApiKey(input: BridgeInput): string | undefined {
  return (
    input.apiKey ??
    process.env.GIVECARE_PI_API_KEY ??
    process.env.GOOGLE_GENERATIVE_AI_API_KEY ??
    process.env.GOOGLE_API_KEY ??
    process.env.GEMINI_API_KEY
  )
}

async function readStdin(): Promise<string> {
  const chunks: Buffer[] = []
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk))
  }
  return Buffer.concat(chunks).toString('utf8')
}

function ok(data: Record<string, unknown>) {
  process.stdout.write(`${JSON.stringify({ ok: true, ...data })}\n`)
}

function fail(message: string, details?: unknown) {
  process.stdout.write(
    `${JSON.stringify({ ok: false, error: message, details: details ?? null })}\n`
  )
  process.exitCode = 1
}

async function main() {
  const raw = await readStdin()
  const input = (raw ? JSON.parse(raw) : { command: 'healthcheck' }) as BridgeInput

  if (input.command === 'healthcheck') {
    ok({
      command: 'healthcheck',
      monoRoot: process.env.GIVECARE_MONO_ROOT,
      status: 'ready',
    })
    return
  }

  if (input.command !== 'run_turn' || !input.conversation) {
    fail('Invalid bridge input')
    return
  }

  const apiKey = resolveApiKey(input)
  if (!apiKey) {
    fail('Missing GiveCare orchestrator API key (GOOGLE_GENERATIVE_AI_API_KEY / GEMINI_API_KEY)')
    return
  }

  const modelName = input.modelName ?? 'gemini-3.1-flash-lite-preview'
  const model = getModel('google', modelName as any)
  const runtime = new BenchmarkRuntime(input.fixtures ?? {})
  const policyRuntime = buildPolicyRuntime(runtime, input.conversation)
  const piPackage = createGiveCarePiPackage({
    modelName,
    model,
    runtime,
    policyRuntime,
    temperature: input.temperature ?? 0.4,
    defaultTemplateId: input.preferredTemplateId,
    defaultThemeId: input.preferredThemeId,
    templatePolicy: {
      mission: input.mission,
      vision: input.vision,
      uxGoals: input.uxGoals,
      businessGoals: input.businessGoals,
      maxRecentMessages: input.maxRecentMessages,
    },
    apiKey,
  })

  piPackage.setSkillContext({
    caregiverId: input.conversation.caregiverId,
    conversationId: input.conversation.conversationId,
    inboundMessageId: input.conversation.inboundMessageId,
    zipCode: input.conversation.zipCode,
    latitude: input.conversation.latitude,
    longitude: input.conversation.longitude,
    riskLevel: input.conversation.riskLevel,
    now: input.now ?? Date.now(),
    scoreSnapshot: input.conversation.scoreSnapshot ?? null,
  })

  const orchestrator = new GiveCareOrchestrator(piPackage)
  const run = await orchestrator.runTurn(
    buildGiveCareTurnInput({
      caregiverId: input.conversation.caregiverId,
      conversationId: input.conversation.conversationId,
      inboundMessageId: input.conversation.inboundMessageId,
      currentLoop: input.conversation.currentLoop,
      currentStage: input.conversation.currentStage,
      riskLevel: input.conversation.riskLevel,
      memory: input.conversation.memory,
      recentMessages: input.conversation.recentMessages,
      skillDiscovery: input.conversation.skillDiscovery,
      pendingPromptType: input.conversation.pendingPromptType,
      pendingPromptInstrument: input.conversation.pendingPromptInstrument,
      assessmentOverdue: input.conversation.assessmentOverdue,
      benefitsScreeningDue: input.conversation.benefitsScreeningDue,
      sdoh30Due: input.conversation.sdoh30Due,
      flaggedZoneCount: input.conversation.flaggedZoneCount,
      openAssessment: input.conversation.openAssessment,
      cadence: input.conversation.cadence,
      skillDiscoveryText: input.conversation.skillDiscoveryText,
      zipCode: input.conversation.zipCode,
      latitude: input.conversation.latitude,
      longitude: input.conversation.longitude,
      incomingText: input.conversation.incomingText,
      preferredTemplateId: input.preferredTemplateId,
      preferredThemeId: input.preferredThemeId,
      bootstrapNeededFacts: input.conversation.bootstrapNeededFacts,
      bootstrapCollectedFacts: input.conversation.bootstrapCollectedFacts,
      scoreSnapshot: input.conversation.scoreSnapshot ?? null,
      metadata: {
        source: 'givecare_bench_orchestrator',
      },
    })
  )

  ok({
    command: 'run_turn',
    modelName,
    assistantText: run.assistantText,
    templateId: run.templateId,
    themeId: run.themeId,
    stopReason: run.stopReason,
    toolCalls: run.toolCalls,
    toolResults: run.toolResults,
    toolTimings: run.toolTimings,
    steps: run.steps,
    modelCalls: run.modelCalls,
    latencyMs: run.latencyMs,
    runtimeEffects: {
      memories: runtime.memories,
      followups: runtime.followups,
      criticalEvents: runtime.criticalEvents,
      alerts: runtime.alerts,
      diagnostics: runtime.diagnostics,
      assessmentRuns: runtime.assessmentRuns,
      eligibilityFacts: runtime.eligibilityFacts,
      bootstrapPatches: runtime.bootstrapPatches,
      resourceOffers: runtime.resourceOffers,
      resourceLookups: runtime.resourceLookups,
      nearbyQueries: runtime.nearbyQueries,
      screeningsRun: runtime.screeningsRun,
    },
  })
}

main().catch(err => {
  fail(err instanceof Error ? err.message : String(err))
})
