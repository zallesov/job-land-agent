/**
* This file was @generated using pocketbase-typegen
*/

import type PocketBase from 'pocketbase'
import type { RecordService } from 'pocketbase'

export const Collections = {
	Authorigins: "_authOrigins",
	Externalauths: "_externalAuths",
	Mfas: "_mfas",
	Otps: "_otps",
	Superusers: "_superusers",
	AgentCommands: "agent_commands",
	Companies: "companies",
	CompanyResearch: "company_research",
	Events: "events",
	Interviews: "interviews",
	JobAssessments: "job_assessments",
	Jobs: "jobs",
	PipelineRuns: "pipeline_runs",
} as const
export type Collections = typeof Collections[keyof typeof Collections]

// Alias types for improved usability
export type IsoDateString = string
export type IsoAutoDateString = string & { readonly autodate: unique symbol }
export type RecordIdString = string
export type FileNameString = string & { readonly filename: unique symbol }
export type HTMLString = string

type ExpandType<T> = unknown extends T
	? T extends unknown
		? { expand?: unknown }
		: { expand: T }
	: { expand: T }

// System fields
export type BaseSystemFields<T = unknown> = {
	id: RecordIdString
	collectionId: string
	collectionName: Collections
} & ExpandType<T>

export type AuthSystemFields<T = unknown> = {
	email: string
	emailVisibility: boolean
	username: string
	verified: boolean
} & BaseSystemFields<T>

// Record types for each collection

export type AuthoriginsRecord = {
	collectionRef: string
	created: IsoAutoDateString
	fingerprint: string
	id: string
	recordRef: string
	updated: IsoAutoDateString
}

export type ExternalauthsRecord = {
	collectionRef: string
	created: IsoAutoDateString
	id: string
	provider: string
	providerId: string
	recordRef: string
	updated: IsoAutoDateString
}

export type MfasRecord = {
	collectionRef: string
	created: IsoAutoDateString
	id: string
	method: string
	recordRef: string
	updated: IsoAutoDateString
}

export type OtpsRecord = {
	collectionRef: string
	created: IsoAutoDateString
	id: string
	password: string
	recordRef: string
	sentTo?: string
	updated: IsoAutoDateString
}

export type SuperusersRecord = {
	created: IsoAutoDateString
	email: string
	emailVisibility?: boolean
	id: string
	password: string
	tokenKey: string
	updated: IsoAutoDateString
	verified?: boolean
}

export type AgentCommandsRecord<Tpayload_json = unknown, Tresult_json = unknown> = {
	command_type?: string
	created_at?: string
	created_by?: string
	error?: string
	finished_at?: string
	id: string
	payload_json?: null | Tpayload_json
	result_json?: null | Tresult_json
	started_at?: string
	status?: string
}

export type CompaniesRecord = {
	created_at?: string
	crunchbase_url?: string
	display_name?: string
	domain?: string
	glassdoor_url?: string
	id: string
	linkedin_url?: string
	normalized_name?: string
	updated_at?: string
	website_url?: string
}

export type CompanyResearchRecord<Traw_research_json = unknown, Tsource_urls_json = unknown> = {
	company_id?: RecordIdString
	created_at?: string
	employee_count?: string
	founded_year?: number
	funding_stage?: string
	funding_summary?: string
	glassdoor_summary?: string
	headcount_trend?: string
	hiring_entity_type?: string
	hq_location?: string
	id: string
	legitimacy_check?: string
	raw_research_json?: null | Traw_research_json
	research_notes?: string
	research_status?: string
	researched_at?: string
	risk_news?: string
	source_urls_json?: null | Tsource_urls_json
	trustworthiness_score?: number
	updated_at?: string
}

export type EventsRecord<Tevent_json = unknown> = {
	actor?: string
	created_at?: string
	entity_id?: string
	entity_type?: string
	event_json?: null | Tevent_json
	event_type?: string
	id: string
}

export type InterviewsRecord<Tcontacts_json = unknown, Temails_json = unknown, Tinterview_dates_json = unknown> = {
	comments?: string
	company_name?: string
	contact_via?: string
	contacts?: string
	contacts_json?: null | Tcontacts_json
	created_at?: string
	description?: string
	emails_json?: null | Temails_json
	id: string
	interview_dates_json?: null | Tinterview_dates_json
	interview_status?: string
	job_id?: string
	job_title?: string
	job_url?: string
	next_interview_date?: string
	status?: string
	telegram_handle?: string
	updated_at?: string
}

export type JobAssessmentsRecord<Traw_assessment_json = unknown, Tsource_urls_json = unknown> = {
	ai_native_assessment?: string
	apply_verdict?: string
	assessed_at?: string
	assessment_notes?: string
	assessment_status?: string
	created_at?: string
	ic_or_management?: string
	id: string
	job_id?: RecordIdString
	one_line_summary?: string
	raw_assessment_json?: null | Traw_assessment_json
	red_flag_scan?: string
	relevance_score?: number
	remote_eligibility?: string
	salary_assessment?: string
	seniority_fit?: string
	source_urls_json?: null | Tsource_urls_json
	tech_stack_fit?: string
	updated_at?: string
	visa_contract_structure?: string
}

export type JobsRecord<Tsource_payload_json = unknown> = {
	actual_hiring_company_id?: RecordIdString
	apply_url?: string
	comment?: string
	company_id?: RecordIdString
	country?: string
	created_at?: string
	current_interview_status?: string
	date_posted?: string
	dedup_key?: string
	deleted_at?: string
	description?: string
	first_seen?: string
	id: string
	last_seen?: string
	location?: string
	pipeline_status?: string
	posted_company_name?: string
	provider?: string
	provider_job_id?: string
	remote_scope?: string
	research_status?: string
	salary_range?: string
	source_payload_json?: null | Tsource_payload_json
	status?: string
	title?: string
	updated_at?: string
	url?: string
	user_status?: string
}

export type PipelineRunsRecord<Tsummary_json = unknown> = {
	error?: string
	finished_at?: string
	id: string
	run_type?: string
	started_at?: string
	status?: string
	summary_json?: null | Tsummary_json
}

// Response types include system fields and match responses from the PocketBase API
export type AuthoriginsResponse<Texpand = unknown> = Required<AuthoriginsRecord> & BaseSystemFields<Texpand>
export type ExternalauthsResponse<Texpand = unknown> = Required<ExternalauthsRecord> & BaseSystemFields<Texpand>
export type MfasResponse<Texpand = unknown> = Required<MfasRecord> & BaseSystemFields<Texpand>
export type OtpsResponse<Texpand = unknown> = Required<OtpsRecord> & BaseSystemFields<Texpand>
export type SuperusersResponse<Texpand = unknown> = Required<SuperusersRecord> & AuthSystemFields<Texpand>
export type AgentCommandsResponse<Tpayload_json = unknown, Tresult_json = unknown, Texpand = unknown> = Required<AgentCommandsRecord<Tpayload_json, Tresult_json>> & BaseSystemFields<Texpand>
export type CompaniesResponse<Texpand = unknown> = Required<CompaniesRecord> & BaseSystemFields<Texpand>
export type CompanyResearchResponse<Traw_research_json = unknown, Tsource_urls_json = unknown, Texpand = unknown> = Required<CompanyResearchRecord<Traw_research_json, Tsource_urls_json>> & BaseSystemFields<Texpand>
export type EventsResponse<Tevent_json = unknown, Texpand = unknown> = Required<EventsRecord<Tevent_json>> & BaseSystemFields<Texpand>
export type InterviewsResponse<Tcontacts_json = unknown, Temails_json = unknown, Tinterview_dates_json = unknown, Texpand = unknown> = Required<InterviewsRecord<Tcontacts_json, Temails_json, Tinterview_dates_json>> & BaseSystemFields<Texpand>
export type JobAssessmentsResponse<Traw_assessment_json = unknown, Tsource_urls_json = unknown, Texpand = unknown> = Required<JobAssessmentsRecord<Traw_assessment_json, Tsource_urls_json>> & BaseSystemFields<Texpand>
export type JobsResponse<Tsource_payload_json = unknown, Texpand = unknown> = Required<JobsRecord<Tsource_payload_json>> & BaseSystemFields<Texpand>
export type PipelineRunsResponse<Tsummary_json = unknown, Texpand = unknown> = Required<PipelineRunsRecord<Tsummary_json>> & BaseSystemFields<Texpand>

// Types containing all Records and Responses, useful for creating typing helper functions

export type CollectionRecords = {
	_authOrigins: AuthoriginsRecord
	_externalAuths: ExternalauthsRecord
	_mfas: MfasRecord
	_otps: OtpsRecord
	_superusers: SuperusersRecord
	agent_commands: AgentCommandsRecord
	companies: CompaniesRecord
	company_research: CompanyResearchRecord
	events: EventsRecord
	interviews: InterviewsRecord
	job_assessments: JobAssessmentsRecord
	jobs: JobsRecord
	pipeline_runs: PipelineRunsRecord
}

export type CollectionResponses = {
	_authOrigins: AuthoriginsResponse
	_externalAuths: ExternalauthsResponse
	_mfas: MfasResponse
	_otps: OtpsResponse
	_superusers: SuperusersResponse
	agent_commands: AgentCommandsResponse
	companies: CompaniesResponse
	company_research: CompanyResearchResponse
	events: EventsResponse
	interviews: InterviewsResponse
	job_assessments: JobAssessmentsResponse
	jobs: JobsResponse
	pipeline_runs: PipelineRunsResponse
}

// Utility types for create/update operations

type ProcessCreateAndUpdateFields<T> = Omit<{
	// Omit AutoDate fields
	[K in keyof T as Extract<T[K], IsoAutoDateString> extends never ? K : never]: 
		// Convert FileNameString to File
		T[K] extends infer U ? 
			U extends (FileNameString | FileNameString[]) ? 
				U extends any[] ? File[] : File 
			: U
		: never
}, 'id'>

// Create type for Auth collections
export type CreateAuth<T> = {
	id?: RecordIdString
	email: string
	emailVisibility?: boolean
	password: string
	passwordConfirm: string
	verified?: boolean
} & ProcessCreateAndUpdateFields<T>

// Create type for Base collections
export type CreateBase<T> = {
	id?: RecordIdString
} & ProcessCreateAndUpdateFields<T>

// Update type for Auth collections
export type UpdateAuth<T> = Partial<
	Omit<ProcessCreateAndUpdateFields<T>, keyof AuthSystemFields>
> & {
	email?: string
	emailVisibility?: boolean
	oldPassword?: string
	password?: string
	passwordConfirm?: string
	verified?: boolean
}

// Update type for Base collections
export type UpdateBase<T> = Partial<
	Omit<ProcessCreateAndUpdateFields<T>, keyof BaseSystemFields>
>

// Get the correct create type for any collection
export type Create<T extends keyof CollectionResponses> =
	CollectionResponses[T] extends AuthSystemFields
		? CreateAuth<CollectionRecords[T]>
		: CreateBase<CollectionRecords[T]>

// Get the correct update type for any collection
export type Update<T extends keyof CollectionResponses> =
	CollectionResponses[T] extends AuthSystemFields
		? UpdateAuth<CollectionRecords[T]>
		: UpdateBase<CollectionRecords[T]>

// Type for usage with type asserted PocketBase instance
// https://github.com/pocketbase/js-sdk#specify-typescript-definitions

export type TypedPocketBase = {
	collection<T extends keyof CollectionResponses>(
		idOrName: T
	): RecordService<CollectionResponses[T]>
} & PocketBase
