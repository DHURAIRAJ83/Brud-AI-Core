"""Pure metadata for every action the Admin Assistant may propose.

This is the strict allowlist referenced by rule 9/29: an action_type not
present here cannot be proposed or executed, full stop. The *executor*
(the callable that actually performs the mutation through an existing,
already-secured admin service) stays in
`backend/services/admin_assistant_service.py::ACTION_EXECUTORS` -- this
module only carries the pure description: risk level, target shape,
required payload fields, and bilingual confirmation copy. The LLM is
never the source of truth for any of this; it only narrates from it.

Per this phase's own documented, proportionate scope decision (see
`docs/admin_assistant/phase8_floating_context_aware_admin_assistant_plan.md`
section 7), not every example action name mentioned in the task is
wired to a real executor yet. Three are, spanning three risk tiers:
`dataset_record_review` (low), `dataset_source_update` (moderate), and
`governance_target_approval_override` (high) -- the last one proves the
full propose -> preview -> confirm-with-stale-check -> execute -> verify
-> audit pattern end-to-end against a real, consequential Phase 6
service. `critical` is a defined tier with no action registered against
it yet -- flagged as future work rather than wired at lower quality
under time pressure.
"""

from __future__ import annotations

from dataclasses import dataclass

RISK_LEVELS = ("low", "moderate", "high", "critical")

# Defense in depth, mirrored from admin_assistant_service.py: even if a
# future entry below or a future executor is mis-registered, an
# action_type containing one of these substrings is always refused.
# The Admin Assistant must never start or resume model training.
BLOCKED_ACTION_SUBSTRINGS = ("train", "pretrain")


@dataclass(frozen=True)
class ActionDefinition:
    action_type: str
    target_type: str
    risk_level: str
    mode: str
    permission: str  # documents intent only -- see plan.md 1.4; enforcement is "any authenticated admin"
    requires_reason: bool
    reversible: bool
    payload_fields: tuple[str, ...]
    summary: dict[str, str]
    confirmation_text: dict[str, str]


ACTION_DEFINITIONS: tuple[ActionDefinition, ...] = (
    ActionDefinition(
        action_type="dataset_record_review",
        target_type="dataset_record",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("decision", "comments"),
        summary={
            "en": "Approve, reject, or request changes on a pending dataset record review.",
            "ta": "நிலுவையில் உள்ள ஒரு dataset record review-ஐ approve, reject, அல்லது request changes செய்யவும்.",
        },
        confirmation_text={
            "en": "This will record a {decision} decision on dataset record {target_public_id}.",
            "ta": "இது dataset record {target_public_id}-க்கு {decision} முடிவை பதிவு செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="dataset_source_update",
        target_type="dataset_source",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("name", "source_type", "url", "license", "notes"),
        summary={
            "en": "Update a dataset source's registered metadata (name, type, URL, licence, notes).",
            "ta": "ஒரு dataset source-இன் பதிவு செய்யப்பட்ட metadata-வை (name, type, URL, licence, notes) update செய்யவும்.",
        },
        confirmation_text={
            "en": "This will overwrite the registered metadata for dataset source {target_public_id}.",
            "ta": "இது dataset source {target_public_id}-இன் பதிவு செய்யப்பட்ட metadata-வை மேலெழுதும்.",
        },
    ),
    ActionDefinition(
        action_type="governance_target_approval_override",
        target_type="governance_entity",
        risk_level="high",
        mode="governance",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=("entity_type", "entity_public_id", "target_use", "decision", "reason"),
        summary={
            "en": "Record an explicit human override of a target-use governance decision (allowed/blocked/needs_review) for one entity and one target use.",
            "ta": "ஒரு entity-க்கும் ஒரு target use-க்கும் ஒரு target-use governance முடிவை (allowed/blocked/needs_review) வெளிப்படையாக மனித override செய்யவும்.",
        },
        confirmation_text={
            "en": "This will override the {target_use} governance decision for {entity_type} {entity_public_id} to '{decision}'. This changes what downstream pipelines may treat this record as eligible for.",
            "ta": "இது {entity_type} {entity_public_id}-இன் {target_use} governance முடிவை '{decision}' ஆக override செய்யும். இது downstream pipelines இந்த record-ஐ எதற்கு eligible எனக் கருதும் என்பதை மாற்றும்.",
        },
    ),
    # -- Phase 9: External Data Provider Registry -------------------------
    # Registering, verifying, or enabling a provider never grants a dataset
    # licence, RAG use, training use, or commercial use -- these actions
    # only ever mutate `external_data_providers` and its child tables,
    # never `data_sources` or any governance/lineage table.
    ActionDefinition(
        action_type="register_external_data_provider",
        target_type="external_data_provider_registration",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("provider_code", "name", "provider_type", "access_mode", "description"),
        summary={
            "en": "Register a new external data provider, starting draft/unverified/disabled.",
            "ta": "ஒரு புதிய external data provider-ஐ பதிவு செய்யவும், draft/unverified/disabled ஆகவே தொடங்கும்.",
        },
        confirmation_text={
            "en": "This will register a new external data provider '{name}' ({provider_code}). It will start disabled and unverified -- no dataset access is granted by this alone.",
            "ta": "இது '{name}' ({provider_code}) எனும் புதிய external data provider-ஐ பதிவு செய்யும். இது disabled மற்றும் unverified ஆகவே தொடங்கும் -- இதனால் மட்டும் எந்த dataset அணுகலும் வழங்கப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="verify_external_data_provider",
        target_type="external_data_provider",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Evaluate a provider's domain/documentation evidence and, only if a domain is already independently verified, upgrade trust_status to domain_verified.",
            "ta": "ஒரு provider-இன் domain/documentation ஆதாரத்தை மதிப்பிடவும் -- ஒரு domain ஏற்கனவே தனித்தனியாக verify செய்யப்பட்டிருந்தால் மட்டுமே trust_status domain_verified ஆக உயர்த்தப்படும்.",
        },
        confirmation_text={
            "en": "This will re-evaluate verification evidence for provider {target_public_id} and may upgrade its trust status.",
            "ta": "இது provider {target_public_id}-இன் verification ஆதாரத்தை மீண்டும் மதிப்பிடும், அதன் trust status உயரக்கூடும்.",
        },
    ),
    ActionDefinition(
        action_type="test_external_data_provider_connection",
        target_type="external_data_provider",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("use_credential",),
        summary={
            "en": "Run a bounded, read-only reachability check against a provider's registered domain -- no search, no download.",
            "ta": "ஒரு provider-இன் பதிவு செய்யப்பட்ட domain-க்கு எதிராக ஒரு bounded, read-only reachability check இயக்கவும் -- search அல்லது download கிடையாது.",
        },
        confirmation_text={
            "en": "This will send one bounded, read-only request to provider {target_public_id}'s registered domain.",
            "ta": "இது provider {target_public_id}-இன் பதிவு செய்யப்பட்ட domain-க்கு ஒரு bounded, read-only request அனுப்பும்.",
        },
    ),
    ActionDefinition(
        action_type="enable_external_data_provider",
        target_type="external_data_provider",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Enable a provider for read-only discovery. Never grants dataset licence, RAG, training, or commercial approval.",
            "ta": "read-only discovery-க்காக ஒரு provider-ஐ enable செய்யவும். dataset licence, RAG, training, அல்லது commercial approval-ஐ ஒருபோதும் வழங்காது.",
        },
        confirmation_text={
            "en": "This will enable provider {target_public_id} for read-only discovery.",
            "ta": "இது provider {target_public_id}-ஐ read-only discovery-க்காக enable செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="disable_external_data_provider",
        target_type="external_data_provider",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Disable a provider -- it can no longer be used for discovery.",
            "ta": "ஒரு provider-ஐ disable செய்யவும் -- இனி discovery-க்கு பயன்படுத்த முடியாது.",
        },
        confirmation_text={
            "en": "This will disable provider {target_public_id}.",
            "ta": "இது provider {target_public_id}-ஐ disable செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="configure_provider_credential_reference",
        target_type="external_data_provider",
        risk_level="high",
        mode="data",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=("credential_type", "reference_key", "reason"),
        summary={
            "en": "Configure a credential *reference* (an environment variable name) for a provider -- never a secret value itself.",
            "ta": "ஒரு provider-க்கு ஒரு credential *reference*-ஐ (ஒரு environment variable பெயர்) கட்டமைக்கவும் -- ஒருபோதும் ஒரு secret value அல்ல.",
        },
        confirmation_text={
            "en": "This will configure a {credential_type} credential reference for provider {target_public_id}. No secret value is stored by this action.",
            "ta": "இது provider {target_public_id}-க்கு ஒரு {credential_type} credential reference-ஐ கட்டமைக்கும். இந்த செயலால் எந்த secret value-உம் சேமிக்கப்படாது.",
        },
    ),
    # -- Phase 10: Live Dataset Discovery, Normalization & Comparison -----
    # Running a search or excluding a candidate only ever mutates
    # `external_dataset_search_sessions`/`external_dataset_candidates` and
    # their child tables -- never `data_sources` or any governance/lineage
    # table. A candidate stays a research artifact; nothing here grants a
    # dataset licence, RAG use, training use, evaluation use, or
    # commercial use by itself.
    ActionDefinition(
        action_type="run_dataset_search",
        target_type="external_dataset_search_session",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Search every currently enabled/searchable external provider for datasets matching this session's requirement, then normalize, deduplicate, and score the results.",
            "ta": "இந்த session-இன் தேவைக்கு பொருந்தும் datasets-க்காக தற்போது enabled/searchable ஆன ஒவ்வொரு external provider-ஐயும் தேடி, results-ஐ normalize, deduplicate, score செய்யவும்.",
        },
        confirmation_text={
            "en": "This will run a bounded external search for session {target_public_id} and create/update candidates in this session only -- no dataset is downloaded, imported, or approved.",
            "ta": "இது session {target_public_id}-க்காக ஒரு bounded external search இயக்கும், இந்த session-இல் மட்டும் candidates-ஐ உருவாக்கும்/புதுப்பிக்கும் -- எந்த dataset-உம் download, import, அல்லது approve செய்யப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="exclude_dataset_candidate",
        target_type="external_dataset_candidate",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Exclude a discovered candidate from the comparison view. The candidate row is never deleted and can be restored at any time.",
            "ta": "ஒரு கண்டுபிடிக்கப்பட்ட candidate-ஐ ஒப்பீட்டு காட்சியிலிருந்து விலக்கவும். Candidate row ஒருபோதும் நீக்கப்படாது, எப்போது வேண்டுமானாலும் மீட்டமைக்கலாம்.",
        },
        confirmation_text={
            "en": "This will exclude candidate {target_public_id} from its session's comparison view. It can be restored later.",
            "ta": "இது candidate {target_public_id}-ஐ அதன் session-இன் ஒப்பீட்டு காட்சியிலிருந்து விலக்கும். பின்னர் மீட்டமைக்கலாம்.",
        },
    ),
    # -- Phase 11: Licence Evidence, Terms Snapshot & Dataset Verification --
    # None of these 9 actions ever download a dataset payload file, import
    # records, activate RAG, create a training dataset version, or release a
    # model -- they only ever mutate `external_dataset_verification_*`
    # tables. `review_dataset_permission` and `finalize_dataset_verification
    # _report`/`record_dataset_withdrawal_notice` are the only "high" risk
    # entries here: the first grants/denies an actual rights decision (an
    # admin-only status), the second/third lock or block a case's future
    # eligibility. The Assistant may recommend a review outcome but this
    # action still requires the human Admin's own explicit confirmation --
    # the assistant itself never auto-approves.
    ActionDefinition(
        action_type="create_dataset_verification_case",
        target_type="external_dataset_candidate",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("verification_scope",),
        summary={
            "en": "Start a new licence/rights verification case for one Phase 10 dataset candidate.",
            "ta": "ஒரு Phase 10 dataset candidate-க்கு புதிய licence/rights verification case ஒன்றைத் தொடங்கவும்.",
        },
        confirmation_text={
            "en": "This will create a new verification case for candidate {target_public_id}. No file is downloaded and no permission is granted by this alone.",
            "ta": "இது candidate {target_public_id}-க்கு புதிய verification case ஒன்றை உருவாக்கும். இதனால் மட்டும் எந்த file-உம் download செய்யப்படாது, எந்த permission-உம் வழங்கப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="collect_dataset_licence_evidence",
        target_type="external_dataset_verification_case",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=("evidence_type", "source_url", "provider_public_id", "authority_level"),
        summary={
            "en": "Fetch one piece of licence/terms evidence for a verification case from an allowlisted domain and store a bounded, checksummed snapshot.",
            "ta": "ஒரு verification case-க்கான licence/terms evidence-ஐ அனுமதிக்கப்பட்ட domain-இலிருந்து பெற்று, bounded, checksummed snapshot ஒன்றை சேமிக்கவும்.",
        },
        confirmation_text={
            "en": "This will fetch evidence from the given URL for case {target_public_id} and store it as a new, checksummed evidence snapshot. No dataset file is downloaded.",
            "ta": "இது case {target_public_id}-க்காக கொடுக்கப்பட்ட URL-இலிருந்து evidence-ஐ பெற்று, checksummed evidence snapshot ஆக சேமிக்கும். எந்த dataset file-உம் download செய்யப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="add_manual_dataset_evidence",
        target_type="external_dataset_verification_case",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=("evidence_type", "content_text", "source_url", "authority_level", "ocr_derived"),
        summary={
            "en": "Record Admin-supplied evidence text directly (e.g. pasted licence text) as a manual, checksummed evidence snapshot.",
            "ta": "Admin நேரடியாக அளிக்கும் evidence text-ஐ (எ.கா. paste செய்யப்பட்ட licence text) manual, checksummed evidence snapshot ஆக பதிவு செய்யவும்.",
        },
        confirmation_text={
            "en": "This will add the text you provide as manual evidence on case {target_public_id}.",
            "ta": "இது நீங்கள் அளிக்கும் text-ஐ case {target_public_id}-இல் manual evidence ஆக சேர்க்கும்.",
        },
    ),
    ActionDefinition(
        action_type="assess_dataset_permissions",
        target_type="external_dataset_verification_case",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Run the automated, read-only permission assessment over already-collected evidence for all 16 permission dimensions. Never sets an approved/prohibited status -- only a human review can.",
            "ta": "ஏற்கனவே சேகரிக்கப்பட்ட evidence-இன் மீது, 16 permission dimensions-க்கும் automated, read-only assessment-ஐ இயக்கவும். approved/prohibited status-ஐ ஒருபோதும் தானாக அமைக்காது -- மனித review மட்டுமே அதை செய்ய முடியும்.",
        },
        confirmation_text={
            "en": "This will re-run the automated permission assessment for case {target_public_id} over its currently-collected evidence.",
            "ta": "இது case {target_public_id}-க்காக, தற்போது சேகரிக்கப்பட்ட evidence-இன் மீது automated permission assessment-ஐ மீண்டும் இயக்கும்.",
        },
    ),
    ActionDefinition(
        action_type="review_dataset_permission",
        target_type="external_dataset_verification_case",
        risk_level="high",
        mode="data",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=("permission_type", "status", "reason", "conditions"),
        summary={
            "en": "Record an explicit human Admin decision (approved/approved_with_conditions/not_approved/prohibited) for one permission dimension on a verification case.",
            "ta": "ஒரு verification case-இன் ஒரு permission dimension-க்கு, வெளிப்படையான மனித Admin முடிவை (approved/approved_with_conditions/not_approved/prohibited) பதிவு செய்யவும்.",
        },
        confirmation_text={
            "en": "This will record your decision '{status}' for permission '{permission_type}' on case {target_public_id}. This directly changes what this dataset may be used for -- it is never automatic.",
            "ta": "இது case {target_public_id}-இன் '{permission_type}' permission-க்கு உங்கள் '{status}' முடிவை பதிவு செய்யும். இது இந்த dataset எதற்குப் பயன்படுத்தப்படலாம் என்பதை நேரடியாக மாற்றும் -- இது ஒருபோதும் தானாக நடக்காது.",
        },
    ),
    ActionDefinition(
        action_type="resolve_dataset_verification_conflict",
        target_type="external_dataset_verification_case",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=True,
        reversible=False,
        payload_fields=("conflict_public_id", "resolution_status", "resolution_reason"),
        summary={
            "en": "Record a human resolution for one detected evidence conflict on a verification case, with a required written reason.",
            "ta": "ஒரு verification case-இல் கண்டறியப்பட்ட evidence conflict ஒன்றுக்கு, கட்டாய எழுதப்பட்ட காரணத்துடன் மனித தீர்வை பதிவு செய்யவும்.",
        },
        confirmation_text={
            "en": "This will resolve conflict {conflict_public_id} on case {target_public_id} as '{resolution_status}'. This does not silently choose one evidence source over another -- your reason is recorded permanently.",
            "ta": "இது case {target_public_id}-இல் உள்ள conflict {conflict_public_id}-ஐ '{resolution_status}' என தீர்க்கும். இது ஒரு evidence source-ஐ மற்றொன்றின் மேல் மௌனமாக தேர்ந்தெடுக்காது -- உங்கள் காரணம் நிரந்தரமாக பதிவு செய்யப்படும்.",
        },
    ),
    ActionDefinition(
        action_type="finalize_dataset_verification_report",
        target_type="external_dataset_verification_case",
        risk_level="high",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=(),
        summary={
            "en": "Generate the immutable final verification report and lock the case. Refuses if an unresolved blocking conflict exists or if reviewed evidence has since changed.",
            "ta": "மாற்ற முடியாத final verification report-ஐ உருவாக்கி case-ஐ lock செய்யவும். தீர்க்கப்படாத blocking conflict இருந்தால் அல்லது review செய்யப்பட்ட evidence மாறியிருந்தால் இது நிராகரிக்கப்படும்.",
        },
        confirmation_text={
            "en": "This will permanently finalize and lock case {target_public_id}. No further evidence, identity, or permission changes will be possible on this case afterward (only lazy reverification).",
            "ta": "இது case {target_public_id}-ஐ நிரந்தரமாக finalize செய்து lock செய்யும். இதற்குப் பிறகு இந்த case-இல் மேலும் evidence, identity, அல்லது permission மாற்றங்கள் சாத்தியமில்லை (lazy reverification மட்டும் தவிர).",
        },
    ),
    ActionDefinition(
        action_type="reverify_dataset_evidence",
        target_type="external_dataset_verification_case",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=(),
        summary={
            "en": "Explicitly re-check every network-sourced evidence snapshot's checksum. If any source changed, marks the case 'source_changed' and demotes prior admin approvals back to needs_legal_review.",
            "ta": "network மூலம் பெறப்பட்ட ஒவ்வொரு evidence snapshot-இன் checksum-ஐயும் வெளிப்படையாக மீண்டும் சரிபார்க்கவும். ஏதேனும் source மாறியிருந்தால், case-ஐ 'source_changed' எனக் குறித்து, முந்தைய admin approvals-ஐ needs_legal_review-க்கு தாழ்த்தும்.",
        },
        confirmation_text={
            "en": "This will re-fetch and re-checksum case {target_public_id}'s network-sourced evidence right now. Works even on an already-finalized case, since licence/terms can change after approval.",
            "ta": "இது case {target_public_id}-இன் network மூலம் பெறப்பட்ட evidence-ஐ இப்போது மீண்டும் fetch செய்து checksum செய்யும். ஏற்கனவே finalize செய்யப்பட்ட case-இலும் இது வேலை செய்யும், ஏனெனில் approval-க்குப் பிறகும் licence/terms மாறலாம்.",
        },
    ),
    ActionDefinition(
        action_type="record_dataset_withdrawal_notice",
        target_type="external_dataset_verification_case",
        risk_level="high",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=("notice_type", "source_url", "notice_text", "effective_at"),
        summary={
            "en": "Record a notice that a provider or rights holder requested removal or changed terms. Blocks future sample import/RAG/training/commercial use until re-reviewed -- never deletes or quarantines anything itself.",
            "ta": "ஒரு provider அல்லது rights holder அகற்றலைக் கோரியது அல்லது terms-ஐ மாற்றியது என்ற notice-ஐ பதிவு செய்யவும். மீண்டும் review செய்யும் வரை future sample import/RAG/training/commercial use-ஐ தடுக்கும் -- இது தானாக எதையும் delete அல்லது quarantine செய்யாது.",
        },
        confirmation_text={
            "en": "This will record a '{notice_type}' withdrawal notice on case {target_public_id} and mark it needing full re-review before any future use.",
            "ta": "இது case {target_public_id}-இல் '{notice_type}' withdrawal notice-ஐ பதிவு செய்து, எதிர்கால use-க்கு முன் முழுமையான re-review தேவை என குறிக்கும்.",
        },
    ),
    # Step 23: the *actual* Source & Rights Registry Phase 2 built is
    # `data_sources`/`source_rights` (via `/api/admin/data-sources`) --
    # distinct from the older, simpler `dataset_sources` table the
    # pre-existing `dataset_source_update` action above targets. This
    # action is the one genuinely new Assistant-pipeline action Phase 11
    # adds: it only ever *proposes* a `source_rights` declaration for an
    # *existing* `data_sources` row a finalized verification case's own
    # report supports -- never creates a new `data_sources` row (Step 23:
    # "no duplicate source should be created"), and never itself writes
    # anything until an Admin reviews and executes it through this exact
    # same governed pipeline.
    ActionDefinition(
        action_type="link_dataset_verification_rights",
        target_type="dataset_source_rights",
        risk_level="high",
        mode="data",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=(
            "rights_status", "license_name", "license_identifier", "attribution_required",
            "share_alike_required", "modification_allowed", "commercial_use_allowed",
            "rag_use_allowed", "training_use_allowed", "evaluation_use_allowed",
            "redistribution_allowed",
        ),
        summary={
            "en": "Declare Source & Rights Registry usage rights for an existing data source, derived from one finalized dataset verification case's own Admin-reviewed permissions.",
            "ta": "ஒரு finalize செய்யப்பட்ட dataset verification case-இன் Admin-reviewed permissions-இலிருந்து பெறப்பட்ட, ஏற்கனவே உள்ள ஒரு data source-க்கான Source & Rights Registry usage rights-ஐ அறிவிக்கவும்.",
        },
        confirmation_text={
            "en": "This will declare/update the Source & Rights Registry rights record for data source {target_public_id}, based on verification case findings. This directly changes what this source may be used for -- it is never automatic.",
            "ta": "இது verification case கண்டறிதல்களின் அடிப்படையில், data source {target_public_id}-க்கான Source & Rights Registry rights record-ஐ அறிவிக்கும்/புதுப்பிக்கும். இது இந்த source எதற்குப் பயன்படுத்தப்படலாம் என்பதை நேரடியாக மாற்றும் -- இது ஒருபோதும் தானாக நடக்காது.",
        },
    ),
    # -- Phase 12: Approved Sample Import, Quarantine, File Safety, PII & Quality ---------
    # Every action here operates on a bounded sample from an already-*finalized*
    # Phase 11 verification case. None of them ever downloads a full dataset,
    # activates RAG, creates a training dataset version, or approves training --
    # there is no such action_type registered anywhere in this block.
    ActionDefinition(
        action_type="create_sample_import",
        target_type="external_dataset_verification_case",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(
            "purpose", "selection_method", "selection_seed", "source_split", "source_file",
            "row_start", "row_end", "requested_count", "expected_modality", "dataset_version",
            "revision",
        ),
        summary={
            "en": "Propose a new bounded sample-import request against one finalized dataset verification case. Never downloads anything by itself.",
            "ta": "ஒரு finalize செய்யப்பட்ட dataset verification case-க்கு எதிராக, ஒரு bounded sample-import கோரிக்கையை முன்மொழியவும். இது தானாக எதையும் download செய்யாது.",
        },
        confirmation_text={
            "en": "This will open a new bounded sample-import proposal for verification case {target_public_id}. No file is downloaded and no permission is granted by this alone.",
            "ta": "இது verification case {target_public_id}-க்கு ஒரு புதிய bounded sample-import proposal-ஐத் திறக்கும். இதனால் மட்டும் எந்த file-உம் download செய்யப்படாது, எந்த permission-உம் வழங்கப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="request_sample_import_approval",
        target_type="external_dataset_sample_import",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(
            "purpose", "requested_record_limit", "requested_byte_limit", "allowed_file_ids",
            "allowed_file_patterns", "allowed_formats", "expected_languages", "expected_tasks",
        ),
        summary={
            "en": "Request a separate, explicitly bound approval (record/byte limits, allowed files/formats) for one draft sample import.",
            "ta": "ஒரு draft sample import-க்கு, தனியான, தெளிவாக bound செய்யப்பட்ட approval (record/byte limits, allowed files/formats) ஒன்றைக் கோரவும்.",
        },
        confirmation_text={
            "en": "This will request an approval for sample import {target_public_id}, bound to the record/byte limits and file scope you specify. An Admin must still separately approve it before any download can start.",
            "ta": "இது sample import {target_public_id}-க்கு, நீங்கள் குறிப்பிடும் record/byte limits மற்றும் file scope-உடன் bound செய்யப்பட்ட approval ஒன்றைக் கோரும். எந்த download தொடங்குவதற்கு முன்பும், ஒரு Admin தனியாக approve செய்ய வேண்டும்.",
        },
    ),
    ActionDefinition(
        action_type="approve_sample_import",
        target_type="external_dataset_sample_import",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=(
            "approved_record_limit", "approved_byte_limit", "expires_at", "approval_reason",
            "conditions",
        ),
        summary={
            "en": "Approve a pending sample-import request within explicit record/byte limits and an expiry date. This is a separate decision from dataset verification itself.",
            "ta": "தெளிவான record/byte limits மற்றும் ஒரு expiry date-உக்குள், நிலுவையில் உள்ள ஒரு sample-import கோரிக்கையை approve செய்யவும். இது dataset verification-இலிருந்து தனியான ஒரு முடிவு.",
        },
        confirmation_text={
            "en": "This will approve sample import {target_public_id} for download, bound to the limits you specify. If the underlying verification case changes afterward, this approval becomes stale and download will be rejected.",
            "ta": "இது sample import {target_public_id}-ஐ, நீங்கள் குறிப்பிடும் limits-உடன் bound செய்யப்பட்டதாக download-க்கு approve செய்யும். பின்னர் அடிப்படை verification case மாறினால், இந்த approval stale ஆகிவிடும், download நிராகரிக்கப்படும்.",
        },
    ),
    ActionDefinition(
        action_type="download_approved_sample",
        target_type="external_dataset_sample_import",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=("source_url", "allowed_domains", "original_filename"),
        summary={
            "en": "Download exactly one approved file into isolated quarantine storage, bounded by the approval's own byte limit. Never a full dataset, never outside quarantine.",
            "ta": "approval-இன் சொந்த byte limit-உக்குள் bound செய்யப்பட்ட, துல்லியமாக ஒரு approved file-ஐ, தனிமைப்படுத்தப்பட்ட quarantine storage-க்குள் download செய்யவும். ஒருபோதும் முழு dataset-ஐ அல்ல, quarantine-க்கு வெளியேயும் அல்ல.",
        },
        confirmation_text={
            "en": "This will download one file from {source_url} into quarantine for sample import {target_public_id}, up to the approved byte limit only. It will never enter RAG or training.",
            "ta": "இது sample import {target_public_id}-க்காக, {source_url}-இலிருந்து ஒரு file-ஐ, approved byte limit வரை மட்டும் quarantine-க்குள் download செய்யும். இது ஒருபோதும் RAG அல்லது training-க்குள் நுழையாது.",
        },
    ),
    ActionDefinition(
        action_type="validate_sample_files",
        target_type="external_dataset_sample_import",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Validate every quarantined file's filename, MIME type, and magic-byte signature -- never trusting a file extension alone.",
            "ta": "quarantine செய்யப்பட்ட ஒவ்வொரு file-இன் filename, MIME type, மற்றும் magic-byte signature-ஐயும் validate செய்யவும் -- ஒருபோதும் file extension ஒன்றை மட்டும் நம்பாது.",
        },
        confirmation_text={
            "en": "This will validate every quarantined file in sample import {target_public_id} and mark unsafe/unsupported files accordingly.",
            "ta": "இது sample import {target_public_id}-இல் உள்ள ஒவ்வொரு quarantine செய்யப்பட்ட file-ஐயும் validate செய்து, unsafe/unsupported files-ஐ அதற்கேற்ப குறிக்கும்.",
        },
    ),
    ActionDefinition(
        action_type="extract_sample_archive",
        target_type="external_dataset_sample_import",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Safely extract validated zip/tar/tar.gz archives member-by-member, rejecting path traversal, symlinks, hard links, device files, and archive bombs.",
            "ta": "validate செய்யப்பட்ட zip/tar/tar.gz archives-ஐ member-by-member பாதுகாப்பாக extract செய்யவும், path traversal, symlinks, hard links, device files, மற்றும் archive bombs-ஐ நிராகரிக்கவும்.",
        },
        confirmation_text={
            "en": "This will safely extract any archive files in sample import {target_public_id} inside quarantine, member-by-member.",
            "ta": "இது sample import {target_public_id}-இல் உள்ள எந்த archive files-ஐயும் quarantine-க்குள், member-by-member பாதுகாப்பாக extract செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="scan_sample",
        target_type="external_dataset_sample_import",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Run the deterministic malware/executable-content scanner over every validated file. Never claims full malware detection.",
            "ta": "validate செய்யப்பட்ட ஒவ்வொரு file-இன் மீதும், deterministic malware/executable-content scanner-ஐ இயக்கவும். இது ஒருபோதும் முழு malware detection-ஐ கூறாது.",
        },
        confirmation_text={
            "en": "This will run the deterministic safety scanner over every validated file in sample import {target_public_id}.",
            "ta": "இது sample import {target_public_id}-இல் உள்ள validate செய்யப்பட்ட ஒவ்வொரு file-இன் மீதும், deterministic safety scanner-ஐ இயக்கும்.",
        },
    ),
    ActionDefinition(
        action_type="parse_sample",
        target_type="external_dataset_sample_import",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Safely parse every scanned, non-archive file into bounded quarantine-only records (TXT/Markdown/CSV/JSON/JSONL/PDF).",
            "ta": "scan செய்யப்பட்ட, archive அல்லாத ஒவ்வொரு file-ஐயும், bounded quarantine-only records ஆக (TXT/Markdown/CSV/JSON/JSONL/PDF) பாதுகாப்பாக parse செய்யவும்.",
        },
        confirmation_text={
            "en": "This will parse every scanned file in sample import {target_public_id} into quarantine-only records. Original files are never modified.",
            "ta": "இது sample import {target_public_id}-இல் உள்ள scan செய்யப்பட்ட ஒவ்வொரு file-ஐயும் quarantine-only records ஆக parse செய்யும். Original files ஒருபோதும் மாற்றப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="run_sample_quality_checks",
        target_type="external_dataset_sample_import",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Run language, quality, PII, and safety checks over every parsed record, creating review issues -- never auto-deleting or auto-correcting anything.",
            "ta": "parse செய்யப்பட்ட ஒவ்வொரு record-இன் மீதும், language, quality, PII, மற்றும் safety checks-ஐ இயக்கி, review issues-ஐ உருவாக்கவும் -- ஒருபோதும் தானாக delete அல்லது correct செய்யாது.",
        },
        confirmation_text={
            "en": "This will run language/quality/PII/safety checks over every record in sample import {target_public_id} and create review issues for anything found.",
            "ta": "இது sample import {target_public_id}-இல் உள்ள ஒவ்வொரு record-இன் மீதும் language/quality/PII/safety checks-ஐ இயக்கி, கண்டறியப்பட்டவற்றுக்கு review issues உருவாக்கும்.",
        },
    ),
    ActionDefinition(
        action_type="run_sample_duplicate_checks",
        target_type="external_dataset_sample_import",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Detect exact and near-duplicate records within this sample, creating review groups -- never auto-merging or auto-deleting.",
            "ta": "இந்த sample-இனுள் exact மற்றும் near-duplicate records-ஐ கண்டறிந்து, review groups-ஐ உருவாக்கவும் -- ஒருபோதும் தானாக merge அல்லது delete செய்யாது.",
        },
        confirmation_text={
            "en": "This will run duplicate detection over every record in sample import {target_public_id} and group matches for review.",
            "ta": "இது sample import {target_public_id}-இல் உள்ள ஒவ்வொரு record-இன் மீதும் duplicate detection-ஐ இயக்கி, பொருந்தும் matches-ஐ review-க்காக group செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="run_sample_contamination_checks",
        target_type="external_dataset_sample_import",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Check every record against existing validation/test/evaluation-fixture checksum sets for contamination.",
            "ta": "இந்த ஒவ்வொரு record-ஐயும், ஏற்கனவே உள்ள validation/test/evaluation-fixture checksum sets-உடன் ஒப்பிட்டு contamination-ஐ சரிபார்க்கவும்.",
        },
        confirmation_text={
            "en": "This will check every record in sample import {target_public_id} against existing evaluation/test checksum sets for contamination.",
            "ta": "இது sample import {target_public_id}-இல் உள்ள ஒவ்வொரு record-ஐயும், ஏற்கனவே உள்ள evaluation/test checksum sets-உடன் ஒப்பிட்டு contamination-க்காக சரிபார்க்கும்.",
        },
    ),
    ActionDefinition(
        action_type="review_sample_issue",
        target_type="external_dataset_sample_import",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=("issue_public_id", "decision", "derived_content_text", "conditions"),
        summary={
            "en": "Record an Admin's decision (accept/exclude/redact derived copy/reject) on one file, record, or finding issue. Never modifies the immutable original.",
            "ta": "ஒரு file, record, அல்லது finding issue மீதான Admin-இன் முடிவை (accept/exclude/redact derived copy/reject) பதிவு செய்யவும். Immutable original-ஐ ஒருபோதும் மாற்றாது.",
        },
        confirmation_text={
            "en": "This will record your review decision for one issue in sample import {target_public_id}. The original quarantined file/record is never altered.",
            "ta": "இது sample import {target_public_id}-இல் உள்ள ஒரு issue-க்கான உங்கள் review முடிவை பதிவு செய்யும். Original quarantine செய்யப்பட்ட file/record ஒருபோதும் மாற்றப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="finalize_sample_validation_report",
        target_type="external_dataset_sample_import",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=(),
        summary={
            "en": "Finalize the immutable sample-validation report and determine RAG-sandbox eligibility (never production RAG or training approval). Refused while any blocking issue remains unreviewed.",
            "ta": "immutable sample-validation report-ஐ finalize செய்து, RAG-sandbox eligibility-ஐ தீர்மானிக்கவும் (ஒருபோதும் production RAG அல்லது training approval அல்ல). ஏதேனும் blocking issue review செய்யப்படாமல் இருந்தால் இது நிராகரிக்கப்படும்.",
        },
        confirmation_text={
            "en": "This will permanently finalize and lock sample import {target_public_id}'s validation report. This does not activate RAG, create a training dataset version, or approve training.",
            "ta": "இது sample import {target_public_id}-இன் validation report-ஐ நிரந்தரமாக finalize செய்து lock செய்யும். இது RAG-ஐ செயல்படுத்தாது, training dataset version உருவாக்காது, அல்லது training-ஐ approve செய்யாது.",
        },
    ),
    ActionDefinition(
        action_type="request_sample_deletion",
        target_type="external_dataset_sample_import",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=("reason",),
        summary={
            "en": "Request deletion of a quarantined sample's payload files, showing lineage impact before any file is removed.",
            "ta": "எந்த file-உம் அகற்றப்படுவதற்கு முன், lineage impact-ஐக் காட்டி, quarantine செய்யப்பட்ட ஒரு sample-இன் payload files-ஐ delete செய்ய கோரவும்.",
        },
        confirmation_text={
            "en": "This will request deletion of the quarantined payload for sample import {target_public_id}. Manifests, checksums, reports, and audit history are always retained.",
            "ta": "இது sample import {target_public_id}-இன் quarantine செய்யப்பட்ட payload-ஐ delete செய்ய கோரும். Manifests, checksums, reports, மற்றும் audit history எப்போதும் தக்கவைக்கப்படும்.",
        },
    ),
    ActionDefinition(
        action_type="execute_sample_deletion",
        target_type="external_dataset_sample_import",
        risk_level="high",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=(),
        summary={
            "en": "Permanently remove a quarantined sample's payload files after a prior deletion request. Irreversible; manifests/checksums/reports/audit are retained.",
            "ta": "முன்னதாக கோரப்பட்ட ஒரு deletion request-க்குப் பிறகு, quarantine செய்யப்பட்ட ஒரு sample-இன் payload files-ஐ நிரந்தரமாக அகற்றவும். Irreversible; manifests/checksums/reports/audit தக்கவைக்கப்படும்.",
        },
        confirmation_text={
            "en": "This will permanently delete the quarantined payload files for sample import {target_public_id}. This cannot be undone -- only the payload is removed; all history is retained.",
            "ta": "இது sample import {target_public_id}-இன் quarantine செய்யப்பட்ட payload files-ஐ நிரந்தரமாக delete செய்யும். இதை மீட்டெடுக்க முடியாது -- payload மட்டுமே அகற்றப்படும்; எல்லா history-உம் தக்கவைக்கப்படும்.",
        },
    ),
    # -- Phase 13: Isolated RAG Sandbox, Retrieval Evaluation, Grounded Answer Testing -----
    # Every action here operates on one Phase 13 RAG sandbox experiment, itself
    # bound to a *finalized, rag_sandbox_eligible* Phase 12 sample import. None of
    # them ever activates production RAG, creates a production index, creates a
    # training dataset version, starts training, or approves a model release --
    # there is no such action_type registered anywhere in this block.
    ActionDefinition(
        action_type="create_rag_sandbox_experiment",
        target_type="external_dataset_sample_import",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(
            "purpose", "experiment_code", "maximum_records", "maximum_total_characters",
            "maximum_total_tokens", "expires_at",
        ),
        summary={
            "en": "Propose a new bounded RAG sandbox experiment against one finalized, rag_sandbox_eligible Phase 12 sample import. Never builds anything by itself.",
            "ta": "finalize செய்யப்பட்ட, rag_sandbox_eligible ஆன ஒரு Phase 12 sample import-க்கு எதிராக, ஒரு bounded RAG sandbox experiment-ஐ முன்மொழியவும். இது தானாக எதையும் build செய்யாது.",
        },
        confirmation_text={
            "en": "This will open a new draft RAG sandbox experiment for sample import {target_public_id}. No record is promoted and no index is built by this alone.",
            "ta": "இது sample import {target_public_id}-க்கு ஒரு புதிய draft RAG sandbox experiment-ஐத் திறக்கும். இதனால் மட்டும் எந்த record-உம் promote செய்யப்படாது, எந்த index-உம் build செய்யப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="request_rag_sandbox_approval",
        target_type="rag_sandbox_experiment",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(
            "purpose", "maximum_records", "maximum_total_characters", "maximum_total_tokens",
            "chunking_configuration", "retrieval_configuration", "embedding_assignment_key",
            "generation_assignment_key", "query_set_public_id", "expires_at", "conditions",
        ),
        summary={
            "en": "Request a separate, explicitly bound approval (accepted-record set, bounds, model assignments) for one draft sandbox experiment.",
            "ta": "ஒரு draft sandbox experiment-க்கு, தனியான, தெளிவாக bound செய்யப்பட்ட approval (accepted-record set, bounds, model assignments) ஒன்றைக் கோரவும்.",
        },
        confirmation_text={
            "en": "This will request an approval for sandbox experiment {target_public_id}, bound to the current accepted-record set and the limits you specify. An Admin must still separately approve it before any record is promoted.",
            "ta": "இது sandbox experiment {target_public_id}-க்கு, தற்போதைய accepted-record set மற்றும் நீங்கள் குறிப்பிடும் limits-உடன் bound செய்யப்பட்ட approval ஒன்றைக் கோரும். எந்த record promote செய்யப்படுவதற்கு முன்பும், ஒரு Admin தனியாக approve செய்ய வேண்டும்.",
        },
    ),
    ActionDefinition(
        action_type="approve_rag_sandbox_experiment",
        target_type="rag_sandbox_experiment",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=("expires_at",),
        summary={
            "en": "Approve a pending sandbox-experiment approval, binding it to the current Phase 12 accepted-record set and an expiry date.",
            "ta": "நிலுவையில் உள்ள ஒரு sandbox-experiment approval-ஐ, தற்போதைய Phase 12 accepted-record set மற்றும் ஒரு expiry date-உடன் bind செய்து approve செய்யவும்.",
        },
        confirmation_text={
            "en": "This will approve sandbox experiment {target_public_id} for corpus preparation. If the underlying Phase 12 sample report or accepted-record set changes afterward, this approval becomes stale.",
            "ta": "இது sandbox experiment {target_public_id}-ஐ corpus preparation-க்கு approve செய்யும். பின்னர் அடிப்படை Phase 12 sample report அல்லது accepted-record set மாறினால், இந்த approval stale ஆகிவிடும்.",
        },
    ),
    ActionDefinition(
        action_type="prepare_rag_sandbox_corpus",
        target_type="rag_sandbox_experiment",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=(),
        summary={
            "en": "Promote every accepted, promotion-eligible Phase 12 record into a brand-new, isolated sandbox knowledge space -- never production-visible.",
            "ta": "accept செய்யப்பட்ட, promotion-eligible ஆன ஒவ்வொரு Phase 12 record-ஐயும், புத்தம்-புதிய, தனிமைப்படுத்தப்பட்ட sandbox knowledge space ஒன்றுக்குள் promote செய்யவும் -- இது ஒருபோதும் production-இல் தெரியாது.",
        },
        confirmation_text={
            "en": "This will promote approved records for sandbox experiment {target_public_id} into an isolated sandbox corpus. This corpus is structurally separate from production RAG.",
            "ta": "இது sandbox experiment {target_public_id}-க்கான approved records-ஐ, ஒரு தனிமைப்படுத்தப்பட்ட sandbox corpus-க்குள் promote செய்யும். இந்த corpus production RAG-இலிருந்து structural-ஆக தனியாக உள்ளது.",
        },
    ),
    ActionDefinition(
        action_type="build_rag_sandbox_index",
        target_type="rag_sandbox_experiment",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(
            "index_kind", "chunking_config", "embedding_model_public_id", "top_k",
            "minimum_score",
        ),
        summary={
            "en": "Build a BM25, vector, or hybrid index over the sandbox corpus, using existing chunking/embedding/indexing services only.",
            "ta": "ஏற்கனவே உள்ள chunking/embedding/indexing services-ஐ மட்டும் பயன்படுத்தி, sandbox corpus-இன் மீது ஒரு BM25, vector, அல்லது hybrid index-ஐ build செய்யவும்.",
        },
        confirmation_text={
            "en": "This will build a {index_kind} index for sandbox experiment {target_public_id}, scoped entirely to its isolated sandbox space.",
            "ta": "இது sandbox experiment {target_public_id}-க்காக, முழுவதுமாக அதன் தனிமைப்படுத்தப்பட்ட sandbox space-க்குள் மட்டும் scope செய்யப்பட்ட ஒரு {index_kind} index-ஐ build செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="create_rag_sandbox_query_set",
        target_type="rag_sandbox_experiment",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("name",),
        summary={
            "en": "Create a new, initially-draft query set for one sandbox experiment.",
            "ta": "ஒரு sandbox experiment-க்கு, ஆரம்பத்தில் draft ஆக இருக்கும் ஒரு புதிய query set-ஐ உருவாக்கவும்.",
        },
        confirmation_text={
            "en": "This will create a new draft query set for sandbox experiment {target_public_id}.",
            "ta": "இது sandbox experiment {target_public_id}-க்கு ஒரு புதிய draft query set-ஐ உருவாக்கும்.",
        },
    ),
    ActionDefinition(
        action_type="finalize_rag_sandbox_query_set",
        target_type="rag_sandbox_experiment",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=("query_set_public_id",),
        summary={
            "en": "Finalize a query set, making it immutable. Refuses if any assistant-suggested query remains unreviewed.",
            "ta": "ஒரு query set-ஐ finalize செய்து, அதை immutable ஆக்கவும். assistant பரிந்துரைத்த எந்த query-உம் review செய்யப்படாமல் இருந்தால், இது மறுக்கப்படும்.",
        },
        confirmation_text={
            "en": "This will finalize query set {query_set_public_id} for sandbox experiment {target_public_id}. No further queries may be added afterward.",
            "ta": "இது sandbox experiment {target_public_id}-க்கான query set {query_set_public_id}-ஐ finalize செய்யும். பின்னர் மேலும் எந்த query-உம் சேர்க்க முடியாது.",
        },
    ),
    ActionDefinition(
        action_type="run_rag_sandbox_retrieval",
        target_type="rag_sandbox_experiment",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("index_public_id", "query_set_public_id"),
        summary={
            "en": "Run every query in a finalized query set against one sandbox index, using the existing retrieval service only.",
            "ta": "ஏற்கனவே உள்ள retrieval service-ஐ மட்டும் பயன்படுத்தி, ஒரு finalize செய்யப்பட்ட query set-இல் உள்ள ஒவ்வொரு query-உம் ஒரு sandbox index-இற்கு எதிராக இயக்கவும்.",
        },
        confirmation_text={
            "en": "This will run retrieval for every query in query set {query_set_public_id} against index {index_public_id}, for sandbox experiment {target_public_id}.",
            "ta": "இது sandbox experiment {target_public_id}-க்காக, query set {query_set_public_id}-இல் உள்ள ஒவ்வொரு query-உம் index {index_public_id}-இற்கு எதிராக retrieval இயக்கும்.",
        },
    ),
    ActionDefinition(
        action_type="run_rag_sandbox_generation",
        target_type="rag_sandbox_experiment",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("retrieval_run_public_id", "generation_assignment_public_id"),
        summary={
            "en": "Generate a grounded, sandbox-labeled answer for every query in a retrieval run, using the existing grounded-generation service only.",
            "ta": "ஏற்கனவே உள்ள grounded-generation service-ஐ மட்டும் பயன்படுத்தி, ஒரு retrieval run-இல் உள்ள ஒவ்வொரு query-க்கும் ஒரு grounded, sandbox-labeled answer-ஐ உருவாக்கவும்.",
        },
        confirmation_text={
            "en": "This will generate sandbox-labeled grounded answers for retrieval run {retrieval_run_public_id} in experiment {target_public_id}. Output is always marked as sandbox evaluation output, never production guidance.",
            "ta": "இது experiment {target_public_id}-இல், retrieval run {retrieval_run_public_id}-க்கு sandbox-labeled grounded answers-ஐ உருவாக்கும். Output எப்போதும் sandbox evaluation output என்று குறிக்கப்படும், production guidance ஆக அல்ல.",
        },
    ),
    ActionDefinition(
        action_type="run_rag_sandbox_evaluation",
        target_type="rag_sandbox_experiment",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("answer_run_public_id",),
        summary={
            "en": "Run deterministic unsupported-claim, insufficient-evidence, conflict, injection, language, and quality evaluation for one answer run.",
            "ta": "ஒரு answer run-க்கு, deterministic unsupported-claim, insufficient-evidence, conflict, injection, language, மற்றும் quality evaluation-ஐ இயக்கவும்.",
        },
        confirmation_text={
            "en": "This will run automated evaluation for answer run {answer_run_public_id} in experiment {target_public_id}. Human review is still required before acceptance.",
            "ta": "இது experiment {target_public_id}-இல், answer run {answer_run_public_id}-க்கு automated evaluation இயக்கும். acceptance-க்கு முன் இன்னும் human review தேவை.",
        },
    ),
    ActionDefinition(
        action_type="review_rag_sandbox_query",
        target_type="rag_sandbox_experiment",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(
            "query_public_id", "answer_run_public_id", "retrieval_relevant", "answer_grounded",
            "citations_correct", "language_appropriate", "refusal_correct", "conflict_handled",
            "injection_resisted", "decision", "notes",
        ),
        summary={
            "en": "Record a human review decision for one query's retrieval/answer/citation/language/refusal/conflict/injection outcome. Append-only and attributed.",
            "ta": "ஒரு query-இன் retrieval/answer/citation/language/refusal/conflict/injection முடிவுக்கான ஒரு human review முடிவை பதிவு செய்யவும். Append-only மற்றும் attributed ஆனது.",
        },
        confirmation_text={
            "en": "This will record your review decision for query {query_public_id} in experiment {target_public_id}.",
            "ta": "இது experiment {target_public_id}-இல், query {query_public_id}-க்கான உங்கள் review முடிவை பதிவு செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="finalize_rag_sandbox_report",
        target_type="rag_sandbox_experiment",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=(),
        summary={
            "en": "Generate the immutable sandbox experiment report -- refuses while any tested query has no human review yet.",
            "ta": "immutable ஆன sandbox experiment report-ஐ உருவாக்கவும் -- test செய்யப்பட்ட எந்த query-உம் இன்னும் human review இல்லாமல் இருந்தால், இது மறுக்கப்படும்.",
        },
        confirmation_text={
            "en": "This will finalize a new, immutable report for sandbox experiment {target_public_id}. It never activates production RAG and never approves training.",
            "ta": "இது sandbox experiment {target_public_id}-க்கு ஒரு புதிய, immutable report-ஐ finalize செய்யும். இது ஒருபோதும் production RAG-ஐ activate செய்யாது, training-ஐயும் approve செய்யாது.",
        },
    ),
    ActionDefinition(
        action_type="accept_rag_sandbox",
        target_type="rag_sandbox_experiment",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=True,
        reversible=False,
        payload_fields=("decision", "reason", "report_public_id", "conditions"),
        summary={
            "en": "Record a separate Admin acceptance decision (accepted / accepted_with_conditions / rejected / needs_more_testing) for the latest finalized report. Never activates production RAG or approves training.",
            "ta": "சமீபத்திய finalize செய்யப்பட்ட report-க்கு, ஒரு தனியான Admin acceptance முடிவை (accepted / accepted_with_conditions / rejected / needs_more_testing) பதிவு செய்யவும். இது ஒருபோதும் production RAG-ஐ activate செய்யாது, training-ஐயும் approve செய்யாது.",
        },
        confirmation_text={
            "en": "This will record acceptance decision '{decision}' for sandbox experiment {target_public_id}'s report {report_public_id}. Stale if the report has since changed.",
            "ta": "இது sandbox experiment {target_public_id}-இன் report {report_public_id}-க்கு, '{decision}' என்ற acceptance முடிவை பதிவு செய்யும். report பின்னர் மாறியிருந்தால், இது stale ஆகும்.",
        },
    ),
    ActionDefinition(
        action_type="reject_rag_sandbox",
        target_type="rag_sandbox_experiment",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=True,
        reversible=False,
        payload_fields=("reason", "report_public_id", "conditions"),
        summary={
            "en": "Record an Admin rejection decision for the latest finalized sandbox report.",
            "ta": "சமீபத்திய finalize செய்யப்பட்ட sandbox report-க்கு, ஒரு Admin rejection முடிவை பதிவு செய்யவும்.",
        },
        confirmation_text={
            "en": "This will record a rejection for sandbox experiment {target_public_id}'s report {report_public_id}.",
            "ta": "இது sandbox experiment {target_public_id}-இன் report {report_public_id}-க்கு ஒரு rejection-ஐ பதிவு செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="request_rag_sandbox_deletion",
        target_type="rag_sandbox_experiment",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=("reason",),
        summary={
            "en": "Request deletion of a sandbox experiment's corpus/index payload, showing impact before anything is removed. Reports and audit are always retained.",
            "ta": "எதுவும் அகற்றப்படுவதற்கு முன், impact-ஐக் காட்டி, ஒரு sandbox experiment-இன் corpus/index payload-ஐ delete செய்ய கோரவும். Reports மற்றும் audit எப்போதும் தக்கவைக்கப்படும்.",
        },
        confirmation_text={
            "en": "This will request deletion of the sandbox corpus/indexes for experiment {target_public_id}. Manifests, reports, acceptances, and audit history are always retained.",
            "ta": "இது experiment {target_public_id}-இன் sandbox corpus/indexes-ஐ delete செய்ய கோரும். Manifests, reports, acceptances, மற்றும் audit history எப்போதும் தக்கவைக்கப்படும்.",
        },
    ),
    ActionDefinition(
        action_type="execute_rag_sandbox_deletion",
        target_type="rag_sandbox_experiment",
        risk_level="high",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=(),
        summary={
            "en": "Permanently archive a sandbox experiment's isolated knowledge space and mark its corpus/indexes deleted, after a prior confirmed deletion request. Reports/acceptances/audit are retained.",
            "ta": "முன்னதாக confirm செய்யப்பட்ட ஒரு deletion request-க்குப் பிறகு, ஒரு sandbox experiment-இன் தனிமைப்படுத்தப்பட்ட knowledge space-ஐ நிரந்தரமாக archive செய்து, அதன் corpus/indexes-ஐ deleted என்று குறிக்கவும். Reports/acceptances/audit தக்கவைக்கப்படும்.",
        },
        confirmation_text={
            "en": "This will permanently archive the isolated sandbox space for experiment {target_public_id} and mark its corpus/indexes deleted. This cannot be undone -- reports, acceptances, and audit history are retained.",
            "ta": "இது experiment {target_public_id}-இன் தனிமைப்படுத்தப்பட்ட sandbox space-ஐ நிரந்தரமாக archive செய்து, அதன் corpus/indexes-ஐ deleted என்று குறிக்கும். இதை மீட்டெடுக்க முடியாது -- reports, acceptances, மற்றும் audit history தக்கவைக்கப்படும்.",
        },
    ),
    # -- Phase 14: Training Dataset Promotion, Incremental Language Training,
    # Checkpoint Evaluation & Admin Approval -----------------------------------------
    # Deliberately scoped to the pre-approval data-curation stages only
    # (suitability assessment -> candidate transformation/review -> replay
    # plan -> dataset promotion *request* + submission). None of these
    # action_types contain "train"/"pretrain" -- BLOCKED_ACTION_SUBSTRINGS
    # would refuse them anyway -- but the scoping itself is deliberate: the
    # assistant stops at "submit this dataset promotion for Admin approval".
    # It can never approve or materialize a promotion, create/approve a
    # training run request, start/resume a run, evaluate or accept a
    # checkpoint, or register a model candidate -- every one of those
    # remains a direct, non-assistant-mediated Admin action in the
    # Incremental Training dashboard/API.
    ActionDefinition(
        action_type="assess_language_sample_suitability",
        target_type="rag_sandbox_experiment",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Open a new training-suitability assessment for one accepted Phase 13 RAG sandbox report. Never itself makes any record training-eligible.",
            "ta": "accept செய்யப்பட்ட ஒரு Phase 13 RAG sandbox report-க்கு, ஒரு புதிய training-suitability assessment-ஐத் திறக்கவும். இது தானாக எந்த record-உம் training-eligible ஆக்காது.",
        },
        confirmation_text={
            "en": "This will open a new suitability assessment for RAG sandbox experiment {target_public_id}. No record is classified or approved by this alone.",
            "ta": "இது RAG sandbox experiment {target_public_id}-க்கு ஒரு புதிய suitability assessment-ஐத் திறக்கும். இதனால் மட்டும் எந்த record-உம் classify அல்லது approve செய்யப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="run_language_sample_suitability_check",
        target_type="training_data_assessment",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Run the deterministic 19-dimension suitability check and language-vs-factual classification for every record in an assessment.",
            "ta": "ஒரு assessment-இல் உள்ள ஒவ்வொரு record-க்கும், deterministic ஆன 19-dimension suitability check மற்றும் language-vs-factual classification-ஐ இயக்கவும்.",
        },
        confirmation_text={
            "en": "This will classify every record in assessment {target_public_id} and assign each a suitability status and reason. This does not select or approve any record.",
            "ta": "இது assessment {target_public_id}-இல் உள்ள ஒவ்வொரு record-ஐயும் classify செய்து, ஒவ்வொன்றுக்கும் ஒரு suitability status மற்றும் reason-ஐ assign செய்யும். இது எந்த record-ஐயும் select அல்லது approve செய்யாது.",
        },
    ),
    ActionDefinition(
        action_type="acknowledge_language_sample_assessment",
        target_type="training_data_assessment",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Record a lightweight Admin acknowledgement that an assessment's classified results have been reviewed.",
            "ta": "ஒரு assessment-இன் classify செய்யப்பட்ட முடிவுகள் review செய்யப்பட்டதாக, ஒரு லேசான Admin acknowledgement-ஐ பதிவு செய்யவும்.",
        },
        confirmation_text={
            "en": "This will record that assessment {target_public_id}'s results have been reviewed. It does not approve any dataset promotion.",
            "ta": "இது assessment {target_public_id}-இன் முடிவுகள் review செய்யப்பட்டதாக பதிவு செய்யும். இது எந்த dataset promotion-ஐயும் approve செய்யாது.",
        },
    ),
    ActionDefinition(
        action_type="transform_language_sample_candidate",
        target_type="training_data_assessment_item",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(
            "transformation_type", "prompt_text", "assistant_text", "language", "task",
            "source_checksum", "source_sample_record_public_id",
            "source_rag_sandbox_record_public_id", "transformation_version",
        ),
        summary={
            "en": "Propose a governed transformation of one suitable assessment item into a training-example candidate, preserving lineage to its source record. Requires separate human review before it can be promoted.",
            "ta": "suitable ஆன ஒரு assessment item-ஐ, அதன் source record-க்கான lineage-ஐப் பாதுகாத்து, ஒரு training-example candidate-ஆக governed transformation செய்ய முன்மொழியவும். Promote செய்யப்படுவதற்கு முன், தனியான human review தேவை.",
        },
        confirmation_text={
            "en": "This will create a new, pending-review training-example candidate from assessment item {target_public_id}. The original source record is never modified.",
            "ta": "இது assessment item {target_public_id}-இலிருந்து, pending-review நிலையில் ஒரு புதிய training-example candidate-ஐ உருவாக்கும். மூல source record ஒருபோதும் மாற்றப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="review_language_sample_candidate",
        target_type="training_example_candidate",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=("decision", "reason", "revised_prompt_text", "revised_assistant_text",
                         "conditions"),
        summary={
            "en": "Approve, reject, or request revision on a pending training-example candidate.",
            "ta": "நிலுவையில் உள்ள ஒரு training-example candidate-ஐ approve, reject, அல்லது revision கோரவும்.",
        },
        confirmation_text={
            "en": "This will record a {decision} decision on training-example candidate {target_public_id}. Only approved candidates are eligible for a dataset promotion request.",
            "ta": "இது training-example candidate {target_public_id}-க்கு {decision} முடிவை பதிவு செய்யும். approve செய்யப்பட்ட candidates மட்டுமே ஒரு dataset promotion request-க்கு eligible ஆகும்.",
        },
    ),
    ActionDefinition(
        action_type="create_replay_data_plan",
        target_type="training_data_assessment",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("new_record_count", "new_data_ratio", "selection_seed"),
        summary={
            "en": "Create a deterministic, seeded replay-data plan mixing existing approved records alongside new candidates to reduce catastrophic-forgetting risk.",
            "ta": "catastrophic-forgetting risk-ஐ குறைக்க, ஏற்கனவே approve செய்யப்பட்ட records-ஐ புதிய candidates-உடன் கலந்து, ஒரு deterministic, seeded replay-data plan-ஐ உருவாக்கவும்.",
        },
        confirmation_text={
            "en": "This will create a replay-data plan for assessment {target_public_id}. The replay ratio is a recommendation -- it does not itself select records for promotion.",
            "ta": "இது assessment {target_public_id}-க்கு ஒரு replay-data plan-ஐ உருவாக்கும். replay ratio ஒரு recommendation மட்டுமே -- இது தானாக promotion-க்கு records-ஐ select செய்யாது.",
        },
    ),
    ActionDefinition(
        action_type="create_dataset_promotion_request",
        target_type="training_data_assessment",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("candidate_public_ids", "replay_plan_public_id"),
        summary={
            "en": "Propose a dataset promotion request for a set of approved training-example candidates, re-running the contamination/leakage recheck. A confirmed overlap always blocks this.",
            "ta": "approve செய்யப்பட்ட training-example candidates தொகுப்பு ஒன்றுக்கு, contamination/leakage recheck-ஐ மீண்டும் இயக்கி, ஒரு dataset promotion request-ஐ முன்மொழியவும். confirmed overlap எப்போதும் இதை தடுக்கும்.",
        },
        confirmation_text={
            "en": "This will create a draft dataset promotion request for assessment {target_public_id} with the selected candidates. It still requires separate submission and a separate Admin approval before any dataset version is built.",
            "ta": "இது assessment {target_public_id}-க்கு, தேர்ந்தெடுக்கப்பட்ட candidates-உடன், ஒரு draft dataset promotion request-ஐ உருவாக்கும். எந்த dataset version-உம் build ஆவதற்கு முன், தனியான submission மற்றும் தனியான Admin approval இன்னும் தேவை.",
        },
    ),
    ActionDefinition(
        action_type="submit_dataset_promotion_request",
        target_type="training_dataset_promotion_request",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Submit a draft dataset promotion request for separate Admin approval. Does not approve or materialize it.",
            "ta": "தனியான Admin approval-க்காக, ஒரு draft dataset promotion request-ஐ சமர்ப்பிக்கவும். இது அதை approve அல்லது materialize செய்யாது.",
        },
        confirmation_text={
            "en": "This will move dataset promotion request {target_public_id} to awaiting-approval. A human Admin must still separately approve and materialize it -- this action can never do either.",
            "ta": "இது dataset promotion request {target_public_id}-ஐ awaiting-approval நிலைக்கு நகர்த்தும். ஒரு human Admin இன்னும் தனியாக அதை approve மற்றும் materialize செய்ய வேண்டும் -- இந்த action ஒருபோதும் அவற்றைச் செய்யாது.",
        },
    ),
    # -- Phase 15: Final Text/NLP Integration, Production RAG Proposal,
    # Model Release Governance, Secure Deployment Readiness & Full
    # Regression Verification ------------------------------------------------
    # Deliberately scoped to proposal/submission and read-verify-only
    # safety checks. There is no executor here for approving a promotion
    # or release, building or validating a RAG candidate, starting a
    # canary, activating anything, rolling anything back, or submitting
    # the final production-acceptance decision -- every one of those
    # remains a direct, non-assistant-mediated Admin action in the
    # Production Readiness dashboard/API.
    ActionDefinition(
        action_type="create_production_rag_promotion_request",
        target_type="rag_sandbox_experiment",
        risk_level="moderate",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(
            "knowledge_space_public_id", "selected_record_ids", "chunking_configuration",
            "embedding_assignment_key", "retrieval_configuration", "generation_assignment_key",
            "citation_policy_version", "grounding_policy_version", "injection_policy_version",
            "commercial_use_context", "resource_preview",
        ),
        summary={
            "en": "Propose a production RAG promotion request from an accepted Phase 13 RAG sandbox report. Never itself builds, validates, or activates production RAG.",
            "ta": "accept செய்யப்பட்ட ஒரு Phase 13 RAG sandbox report-இலிருந்து, ஒரு production RAG promotion request-ஐ முன்மொழியவும். இது தானாக production RAG-ஐ build, validate, அல்லது activate செய்யாது.",
        },
        confirmation_text={
            "en": "This will create a draft production RAG promotion request for RAG sandbox experiment {target_public_id}. It still requires separate submission, a separate Admin approval, a separate candidate build/validation, and a separate activation before any production RAG serves traffic.",
            "ta": "இது RAG sandbox experiment {target_public_id}-க்கு ஒரு draft production RAG promotion request-ஐ உருவாக்கும். எந்த production RAG-உம் traffic-க்கு service செய்வதற்கு முன், தனியான submission, தனியான Admin approval, தனியான candidate build/validation, மற்றும் தனியான activation இன்னும் தேவை.",
        },
    ),
    ActionDefinition(
        action_type="submit_production_rag_promotion_request",
        target_type="production_rag_promotion_request",
        risk_level="moderate",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Submit a draft production RAG promotion request for separate Admin approval. Does not approve, build, or activate it.",
            "ta": "தனியான Admin approval-க்காக, ஒரு draft production RAG promotion request-ஐ சமர்ப்பிக்கவும். இது அதை approve, build, அல்லது activate செய்யாது.",
        },
        confirmation_text={
            "en": "This will move production RAG promotion request {target_public_id} to awaiting-review. A human Admin must still separately approve it, build and validate a candidate, and activate it -- this action can never do any of those.",
            "ta": "இது production RAG promotion request {target_public_id}-ஐ awaiting-review நிலைக்கு நகர்த்தும். ஒரு human Admin இன்னும் தனியாக அதை approve செய்து, ஒரு candidate-ஐ build/validate செய்து, activate செய்ய வேண்டும் -- இந்த action இவற்றில் எதையும் ஒருபோதும் செய்யாது.",
        },
    ),
    ActionDefinition(
        action_type="create_production_model_release_request",
        target_type="incremental_training_checkpoint",
        risk_level="moderate",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(
            "model_release_family_public_id", "dataset_version_public_id", "label", "notes",
            "release_type", "target_assignment_keys", "canary_requested",
            "canary_percentage_or_scope",
        ),
        summary={
            "en": "Propose a production model release request from an accepted Phase 14 checkpoint. Never itself validates, approves, or activates a model release.",
            "ta": "accept செய்யப்பட்ட ஒரு Phase 14 checkpoint-இலிருந்து, ஒரு production model release request-ஐ முன்மொழியவும். இது தானாக ஒரு model release-ஐ validate, approve, அல்லது activate செய்யாது.",
        },
        confirmation_text={
            "en": "This will create a draft production model release request for checkpoint {target_public_id}. It still requires separate validation, a separate Admin approval, and a separate activation before this model can serve any traffic.",
            "ta": "இது checkpoint {target_public_id}-க்கு ஒரு draft production model release request-ஐ உருவாக்கும். இந்த model எந்த traffic-க்கும் service செய்வதற்கு முன், தனியான validation, தனியான Admin approval, மற்றும் தனியான activation இன்னும் தேவை.",
        },
    ),
    ActionDefinition(
        action_type="submit_production_model_release_request",
        target_type="production_model_release_request",
        risk_level="moderate",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Submit a draft production model release request for separate Admin approval. Does not validate, approve, or activate it.",
            "ta": "தனியான Admin approval-க்காக, ஒரு draft production model release request-ஐ சமர்ப்பிக்கவும். இது அதை validate, approve, அல்லது activate செய்யாது.",
        },
        confirmation_text={
            "en": "This will move production model release request {target_public_id} to awaiting-review. A human Admin must still separately validate, approve, and activate it -- this action can never do any of those.",
            "ta": "இது production model release request {target_public_id}-ஐ awaiting-review நிலைக்கு நகர்த்தும். ஒரு human Admin இன்னும் தனியாக அதை validate, approve, மற்றும் activate செய்ய வேண்டும் -- இந்த action இவற்றில் எதையும் ஒருபோதும் செய்யாது.",
        },
    ),
    ActionDefinition(
        action_type="check_production_release_candidate_artifact_security",
        target_type="model_release_candidate",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Run an independent artifact-security re-verification (confinement, unexpected executables, checksum integrity) over every artifact already collected for a model release candidate. Read-only against the artifacts themselves; only writes an audit-trail check row.",
            "ta": "ஒரு model release candidate-க்காக ஏற்கனவே சேகரிக்கப்பட்ட ஒவ்வொரு artifact-க்கும், ஒரு independent artifact-security re-verification-ஐ (confinement, unexpected executables, checksum integrity) இயக்கவும். artifacts-மீது read-only; ஒரு audit-trail check row-ஐ மட்டுமே எழுதும்.",
        },
        confirmation_text={
            "en": "This will independently re-verify every collected artifact for model release candidate {target_public_id} and record the result. It does not change the candidate's status or approve anything.",
            "ta": "இது model release candidate {target_public_id}-க்கு சேகரிக்கப்பட்ட ஒவ்வொரு artifact-ஐயும் சுயாதீனமாக மீண்டும் verify செய்து, முடிவை பதிவு செய்யும். இது candidate-இன் status-ஐ மாற்றாது அல்லது எதையும் approve செய்யாது.",
        },
    ),
    ActionDefinition(
        action_type="run_production_api_abuse_readiness_check",
        target_type="production_readiness_system",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Run the read-only API-abuse/model-extraction readiness assessment (bounded request fields, CSRF configuration, canary thresholds, no forbidden download endpoints) and record the result.",
            "ta": "read-only ஆன API-abuse/model-extraction readiness assessment-ஐ (bounded request fields, CSRF configuration, canary thresholds, forbidden download endpoints இல்லாதது) இயக்கி, முடிவை பதிவு செய்யவும்.",
        },
        confirmation_text={
            "en": "This will run the API-abuse readiness assessment against the current codebase and configuration and record the result. It changes nothing about running services.",
            "ta": "இது தற்போதைய codebase மற்றும் configuration-க்கு எதிராக API-abuse readiness assessment-ஐ இயக்கி, முடிவை பதிவு செய்யும். இயங்கும் services பற்றி எதையும் இது மாற்றாது.",
        },
    ),
    ActionDefinition(
        action_type="run_production_secret_redaction_check",
        target_type="production_readiness_system",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Run a functional self-check confirming the existing secret-redaction mechanism still redacts password/token/secret-shaped fields, and record the result.",
            "ta": "ஏற்கனவே உள்ள secret-redaction mechanism இன்னும் password/token/secret வடிவ fields-ஐ redact செய்கிறதா என்பதை உறுதிசெய்ய ஒரு functional self-check-ஐ இயக்கி, முடிவை பதிவு செய்யவும்.",
        },
        confirmation_text={
            "en": "This will run a functional redaction self-check and record the result. It does not scan or change any live data.",
            "ta": "இது ஒரு functional redaction self-check-ஐ இயக்கி, முடிவை பதிவு செய்யும். இது எந்த live data-ஐயும் scan அல்லது மாற்றாது.",
        },
    ),
    ActionDefinition(
        action_type="compile_production_readiness_report",
        target_type="production_readiness_system",
        risk_level="moderate",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Compile a new, versioned, immutable Text/NLP production readiness report from the current deployment-readiness and regression state. Never itself accepts or rejects production readiness.",
            "ta": "தற்போதைய deployment-readiness மற்றும் regression நிலையிலிருந்து, ஒரு புதிய, versioned, immutable ஆன Text/NLP production readiness report-ஐ தொகுக்கவும். இது தானாக production readiness-ஐ accept அல்லது reject செய்யாது.",
        },
        confirmation_text={
            "en": "This will compile and append a new production readiness report version reflecting current state. A human Admin must still separately submit the final production-acceptance review -- this action can never do that.",
            "ta": "இது தற்போதைய நிலையை பிரதிபலிக்கும் ஒரு புதிய production readiness report version-ஐ தொகுத்து append செய்யும். ஒரு human Admin இன்னும் தனியாக இறுதி production-acceptance review-ஐ சமர்ப்பிக்க வேண்டும் -- இந்த action அதை ஒருபோதும் செய்யாது.",
        },
    ),
    ActionDefinition(
        action_type="run_production_backup_readiness_check",
        target_type="production_readiness_system",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Check whether a recent database backup exists and (if configured) how old it is. Read-only against the backup directory; only writes an audit-trail check row.",
            "ta": "ஒரு recent database backup உள்ளதா, (configure செய்யப்பட்டிருந்தால்) அது எவ்வளவு பழையது என்பதை check செய்யவும். backup directory-மீது read-only; ஒரு audit-trail check row-ஐ மட்டுமே எழுதும்.",
        },
        confirmation_text={
            "en": "This will check the latest backup's presence/age and record the result. It never creates, deletes, or modifies any backup file.",
            "ta": "இது latest backup-இன் presence/age-ஐ check செய்து முடிவை பதிவு செய்யும். இது எந்த backup fileஐயும் ஒருபோதும் create, delete, அல்லது modify செய்யாது.",
        },
    ),
    ActionDefinition(
        action_type="run_production_restore_readiness_check",
        target_type="production_readiness_system",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Run an isolated restore drill: copy the latest backup into a temporary directory, verify it there (integrity check, schema version), and delete the temporary copy. Never touches the live database.",
            "ta": "ஒரு isolated restore drill-ஐ இயக்கவும்: latest backup-ஐ ஒரு temporary directory-க்கு copy செய்து, அங்கே verify செய்து (integrity check, schema version), temporary copy-ஐ delete செய்யவும். live database-ஐ ஒருபோதும் தொடாது.",
        },
        confirmation_text={
            "en": "This will copy the latest backup into an isolated temporary directory, verify it, delete the copy, and record the result. It never touches the live database.",
            "ta": "இது latest backup-ஐ ஒரு isolated temporary directory-க்கு copy செய்து, verify செய்து, copy-ஐ delete செய்து, முடிவை பதிவு செய்யும். இது live database-ஐ ஒருபோதும் தொடாது.",
        },
    ),
    ActionDefinition(
        action_type="assess_production_backup_encryption",
        target_type="production_readiness_system",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Honestly assess whether the latest backup is encrypted at rest (checks for an encrypted sidecar file and whether an encryption key is present in the environment). Never guesses; reports not_encrypted/not_configured if evidence is missing.",
            "ta": "latest backup encrypted at rest-ஆ என்பதை நேர்மையாக assess செய்யவும் (ஒரு encrypted sidecar file உள்ளதா, environment-இல் ஒரு encryption key உள்ளதா என்பதை check செய்யும்). ஒருபோதும் guess செய்யாது; evidence இல்லையென்றால் not_encrypted/not_configured என்று report செய்யும்.",
        },
        confirmation_text={
            "en": "This will check the latest backup for an encrypted sidecar and a present encryption key, and record an honest result. It never encrypts, decrypts, or modifies any file.",
            "ta": "இது latest backup-க்கு ஒரு encrypted sidecar மற்றும் ஒரு present encryption key உள்ளதா என்பதை check செய்து, ஒரு நேர்மையான முடிவை பதிவு செய்யும். இது எந்த fileஐயும் ஒருபோதும் encrypt, decrypt, அல்லது modify செய்யாது.",
        },
    ),
    ActionDefinition(
        action_type="encrypt_production_backup",
        target_type="production_readiness_system",
        risk_level="moderate",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Encrypt the latest backup at rest with AES-256-GCM, using a key read only from the server's configured environment variable (never from this request). Produces a new encrypted sibling file; the original plaintext backup is left untouched. Fails closed (does nothing) if no key is configured.",
            "ta": "server-இன் configure செய்யப்பட்ட environment variable-இலிருந்து மட்டும் படிக்கப்படும் ஒரு key-ஐ பயன்படுத்தி (இந்த request-இலிருந்து ஒருபோதும் இல்லை), latest backup-ஐ AES-256-GCM மூலம் at rest encrypt செய்யவும். ஒரு புதிய encrypted sibling file-ஐ உருவாக்கும்; original plaintext backup தொடப்படாமல் இருக்கும். key configure செய்யப்படவில்லை என்றால் fail closed ஆகும் (எதுவும் செய்யாது).",
        },
        confirmation_text={
            "en": "This will create a new, encrypted copy of the latest backup next to the original (which is left unchanged), using the server-side encryption key -- never a key from this conversation. This does not delete or replace anything and can be undone by removing the new encrypted file.",
            "ta": "இது latest backup-இன் ஒரு புதிய, encrypted copy-ஐ original-க்கு அருகில் உருவாக்கும் (original மாறாமல் இருக்கும்), server-side encryption key-ஐ பயன்படுத்தி -- இந்த conversation-இலிருந்து ஒருபோதும் ஒரு key அல்ல. இது எதையும் delete அல்லது replace செய்யாது, புதிய encrypted file-ஐ நீக்குவதன் மூலம் undo செய்யலாம்.",
        },
    ),
    ActionDefinition(
        action_type="verify_production_encrypted_restore",
        target_type="production_readiness_system",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Run a fully isolated encrypted-restore drill: decrypt the latest encrypted backup into a temporary directory, verify it there, and delete the temporary copy (including the decrypted plaintext). Never touches the live database or the real backup files.",
            "ta": "ஒரு முழுமையாக isolated ஆன encrypted-restore drill-ஐ இயக்கவும்: latest encrypted backup-ஐ ஒரு temporary directory-க்கு decrypt செய்து, அங்கே verify செய்து, temporary copy-ஐ (decrypted plaintext உட்பட) delete செய்யவும். live database அல்லது real backup files-ஐ ஒருபோதும் தொடாது.",
        },
        confirmation_text={
            "en": "This will decrypt the latest encrypted backup into an isolated temporary directory, verify it, delete the decrypted copy, and record the result. It never touches the live database or any real backup file.",
            "ta": "இது latest encrypted backup-ஐ ஒரு isolated temporary directory-க்கு decrypt செய்து, verify செய்து, decrypted copy-ஐ delete செய்து, முடிவை பதிவு செய்யும். இது live database அல்லது எந்த real backup fileஐயும் ஒருபோதும் தொடாது.",
        },
    ),
    # -- Phase 19 knowledge-gap registry: 4 fully wired (low/moderate risk), matching this
    # phase's own established precedent (Section 1's docstring) that not every proposal action
    # needs an executor at launch. The remaining 4 are pure metadata only (see plan doc section 2).
    ActionDefinition(
        action_type="create_knowledge_gap_research_note",
        target_type="knowledge_gap_case",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=("note_type", "note_text", "source_reference"),
        summary={
            "en": "Add an append-only research note to a knowledge-gap case (PII/secret-scanned before saving).",
            "ta": "ஒரு knowledge-gap case-க்கு append-only research note ஒன்றைச் சேர்க்கவும் (சேமிக்கும் முன் PII/secret scan செய்யப்படும்).",
        },
        confirmation_text={
            "en": "This will permanently add this research note to case {target_public_id}. Notes cannot be edited or deleted afterward.",
            "ta": "இது இந்த research note-ஐ case {target_public_id}-க்கு நிரந்தரமாகச் சேர்க்கும். பின்னர் notes-ஐ edit அல்லது delete செய்ய முடியாது.",
        },
    ),
    ActionDefinition(
        action_type="propose_gap_priority_update",
        target_type="knowledge_gap_case",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Recompute a knowledge-gap case's priority score/band from its current frequency, recency, and reason codes.",
            "ta": "ஒரு knowledge-gap case-இன் priority score/band-ஐ அதன் தற்போதைய frequency, recency, மற்றும் reason codes-இலிருந்து மீண்டும் கணக்கிடவும்.",
        },
        confirmation_text={
            "en": "This will recalculate and store a new priority score/band for case {target_public_id}. It never marks the case resolved or approved for anything.",
            "ta": "இது case {target_public_id}-க்கு புதிய priority score/band-ஐ கணக்கிட்டு சேமிக்கும். இது case-ஐ resolved அல்லது எதற்கும் approved என குறிக்காது.",
        },
    ),
    ActionDefinition(
        action_type="propose_duplicate_gap_merge",
        target_type="knowledge_gap_case",
        risk_level="moderate",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=("case_public_ids", "canonical_question", "primary_language"),
        summary={
            "en": "Merge two or more knowledge-gap cases into one cluster after a conservative duplicate-detection preview.",
            "ta": "conservative duplicate-detection preview-க்குப் பிறகு இரண்டு அல்லது அதற்கு மேற்பட்ட knowledge-gap cases-ஐ ஒரு cluster-ஆக merge செய்யவும்.",
        },
        confirmation_text={
            "en": "This will merge the listed cases into one cluster. Original case rows and their occurrence history are always retained -- nothing is deleted.",
            "ta": "இது பட்டியலிடப்பட்ட cases-ஐ ஒரு cluster-ஆக merge செய்யும். அசல் case rows மற்றும் அவற்றின் occurrence history எப்போதும் தக்கவைக்கப்படும் -- எதுவும் delete செய்யப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="generate_daily_knowledge_gap_report",
        target_type="knowledge_gap_report_system",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Generate today's deterministic knowledge-gap daily report from already-registered cases.",
            "ta": "ஏற்கனவே பதிவுசெய்யப்பட்ட cases-இலிருந்து இன்றைய deterministic knowledge-gap daily report-ஐ உருவாக்கவும்.",
        },
        confirmation_text={
            "en": "This will generate and store today's knowledge-gap daily report. It reads existing registry data only -- no web search, no model call.",
            "ta": "இது இன்றைய knowledge-gap daily report-ஐ உருவாக்கி சேமிக்கும். இது existing registry data-ஐ மட்டுமே படிக்கும் -- web search இல்லை, model call இல்லை.",
        },
    ),
    ActionDefinition(
        action_type="propose_knowledge_gap_classification",
        target_type="knowledge_gap_case",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("comment",),
        summary={
            "en": "Record a 'reclassify' review decision on a knowledge-gap case, moving it back to the classification stage for human re-examination. Does not itself change the stored event type/reason codes -- an Admin re-examines and corrects those through the case's own classify/review endpoints afterward.",
            "ta": "ஒரு knowledge-gap case-இல் 'reclassify' review decision-ஐ பதிவு செய்து, அதை மீண்டும் classification stage-க்கு human re-examination-க்காக நகர்த்தவும். இது சேமிக்கப்பட்ட event type/reason codes-ஐ தானாக மாற்றாது -- ஒரு Admin பின்னர் case-இன் classify/review endpoints வழியாக அவற்றை மறு-பரிசீலனை செய்து சரிசெய்வார்.",
        },
        confirmation_text={
            "en": "This will record a reclassify decision on case {target_public_id} and move it back to the classification stage.",
            "ta": "இது case {target_public_id}-இல் ஒரு reclassify decision-ஐ பதிவு செய்து, அதை மீண்டும் classification stage-க்கு நகர்த்தும்.",
        },
    ),
    ActionDefinition(
        action_type="propose_gap_resolution",
        target_type="knowledge_gap_case",
        risk_level="moderate",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=("resolution_type", "notes"),
        summary={
            "en": "Record a resolution type for a knowledge-gap case. Descriptive only -- it never performs the described action itself (never creates a RAG source, never starts training, never activates a release).",
            "ta": "ஒரு knowledge-gap case-க்கான resolution type-ஐ பதிவு செய்யவும். Descriptive மட்டுமே -- இது விவரிக்கப்பட்ட செயலை தானாக செய்யாது (RAG source உருவாக்காது, training தொடங்காது, release activate செய்யாது).",
        },
        confirmation_text={
            "en": "This will record a {resolution_type} resolution on case {target_public_id} and move it to a terminal-ish status. It never performs the described action by itself.",
            "ta": "இது case {target_public_id}-இல் ஒரு {resolution_type} resolution-ஐ பதிவு செய்து, அதை ஒரு terminal-ஒத்த status-க்கு நகர்த்தும். இது விவரிக்கப்பட்ட செயலை தானாக செய்யாது.",
        },
    ),
    ActionDefinition(
        action_type="propose_rag_research_handoff",
        target_type="knowledge_gap_case",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Recompute and store a knowledge-gap case's RAG-research/training-assessment eligibility flags. Advisory only -- never creates a RAG source, RAG trial, training dataset, or training run.",
            "ta": "ஒரு knowledge-gap case-இன் RAG-research/training-assessment eligibility flags-ஐ மீண்டும் கணக்கிட்டு சேமிக்கவும். Advisory மட்டுமே -- RAG source, RAG trial, training dataset, அல்லது training run ஒருபோதும் உருவாக்காது.",
        },
        confirmation_text={
            "en": "This will recompute case {target_public_id}'s RAG-research and training-assessment eligibility flags from its current classification. It never creates a RAG source, RAG trial, training dataset, or training run.",
            "ta": "இது case {target_public_id}-இன் RAG-research மற்றும் training-assessment eligibility flags-ஐ அதன் தற்போதைய classification-இலிருந்து மீண்டும் கணக்கிடும். இது RAG source, RAG trial, training dataset, அல்லது training run ஒருபோதும் உருவாக்காது.",
        },
    ),
    # Named "capability_assessment", not "training_assessment_handoff" as
    # Phase 19's own spec literally lists it -- the latter string
    # contains "train", which the existing, more fundamental
    # `BLOCKED_ACTION_SUBSTRINGS` defense-in-depth filter (this action
    # never starts training, it only flags a case as advisory-eligible)
    # refuses outright regardless of what executor is or isn't wired.
    # Renaming avoids a name collision with that safety filter rather
    # than weakening it. See `eligible_for_training_assessment` (the
    # underlying case field this proposes a value for) for the concept
    # itself, which is unchanged. Shares the same executor as
    # `propose_rag_research_handoff` -- both recompute the one
    # `KnowledgeGapHandoffAssessmentService.assess()` result, which
    # always produces both flags together.
    ActionDefinition(
        action_type="propose_capability_assessment_handoff",
        target_type="knowledge_gap_case",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Recompute and store a knowledge-gap case's training-assessment/RAG-research eligibility flags. Advisory only -- never creates a training dataset, training run, RAG source, or RAG trial.",
            "ta": "ஒரு knowledge-gap case-இன் training-assessment/RAG-research eligibility flags-ஐ மீண்டும் கணக்கிட்டு சேமிக்கவும். Advisory மட்டுமே -- training dataset, training run, RAG source, அல்லது RAG trial ஒருபோதும் உருவாக்காது.",
        },
        confirmation_text={
            "en": "This will recompute case {target_public_id}'s training-assessment and RAG-research eligibility flags from its current classification. It never creates a training dataset, training run, RAG source, or RAG trial.",
            "ta": "இது case {target_public_id}-இன் training-assessment மற்றும் RAG-research eligibility flags-ஐ அதன் தற்போதைய classification-இலிருந்து மீண்டும் கணக்கிடும். இது training dataset, training run, RAG source, அல்லது RAG trial ஒருபோதும் உருவாக்காது.",
        },
    ),
    # Phase 20 Step 32 -- five low-risk proposal actions, all "record a
    # flagged issue for human review" only. None of them mutate the
    # checksum-versioned trusted_web_policy.json file, enable a paid
    # search provider, toggle a tool's public/admin-enabled flag, or
    # enable external MCP -- Admin Assistant may flag/propose, never
    # silently apply a policy or permission change itself (full
    # tool-permission governance remains Phase 22).
    ActionDefinition(
        action_type="propose_trusted_web_policy_issue",
        target_type="trusted_web_policy_system",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=("comment",),
        summary={
            "en": "Flag a possible issue with the Trusted Web source-trust policy for human review. Never edits the policy file itself.",
            "ta": "Trusted Web source-trust policy-இல் ஒரு சாத்தியமான issue-ஐ human review-க்காக flag செய்யவும். Policy file-ஐ ஒருபோதும் edit செய்யாது.",
        },
        confirmation_text={
            "en": "This will record a policy-issue flag for Admin review. It never modifies config/trusted_web_policy.json.",
            "ta": "இது Admin review-க்காக ஒரு policy-issue flag-ஐ பதிவு செய்யும். இது config/trusted_web_policy.json-ஐ ஒருபோதும் மாற்றாது.",
        },
    ),
    ActionDefinition(
        action_type="propose_source_block",
        target_type="trusted_web_policy_system",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=("domain", "comment"),
        summary={
            "en": "Propose blocking a domain from the Trusted Web source-trust policy for human review. Never edits the policy file itself.",
            "ta": "Trusted Web source-trust policy-இலிருந்து ஒரு domain-ஐ block செய்ய human review-க்காக propose செய்யவும். Policy file-ஐ ஒருபோதும் edit செய்யாது.",
        },
        confirmation_text={
            "en": "This will record a source-block proposal for Admin review. It never modifies config/trusted_web_policy.json -- an Admin must apply the change through the governed policy-reload mechanism.",
            "ta": "இது Admin review-க்காக ஒரு source-block proposal-ஐ பதிவு செய்யும். இது config/trusted_web_policy.json-ஐ ஒருபோதும் மாற்றாது -- ஒரு Admin governed policy-reload மூலம் மாற்றத்தை apply செய்ய வேண்டும்.",
        },
    ),
    ActionDefinition(
        action_type="propose_source_allowlist_review",
        target_type="trusted_web_policy_system",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=("domain", "comment"),
        summary={
            "en": "Propose reviewing a domain for addition to (or trust-level change on) the Trusted Web allowlist. Never edits the policy file itself.",
            "ta": "Trusted Web allowlist-இல் ஒரு domain-ஐ சேர்க்க (அல்லது trust-level மாற்ற) review செய்ய propose செய்யவும். Policy file-ஐ ஒருபோதும் edit செய்யாது.",
        },
        confirmation_text={
            "en": "This will record an allowlist-review proposal for Admin review. It never modifies config/trusted_web_policy.json.",
            "ta": "இது Admin review-க்காக ஒரு allowlist-review proposal-ஐ பதிவு செய்யும். இது config/trusted_web_policy.json-ஐ ஒருபோதும் மாற்றாது.",
        },
    ),
    ActionDefinition(
        action_type="propose_tool_enablement_review",
        target_type="deterministic_tool_registry_system",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=("tool_name", "comment"),
        summary={
            "en": "Propose reviewing whether a deterministic tool's public/admin enablement should change. Never toggles the tool's enabled state itself.",
            "ta": "ஒரு deterministic tool-இன் public/admin enablement மாற வேண்டுமா என்பதை review செய்ய propose செய்யவும். Tool-இன் enabled state-ஐ ஒருபோதும் toggle செய்யாது.",
        },
        confirmation_text={
            "en": "This will record a tool-enablement review request for Admin review, audited only. It never changes any tool's public_enabled/admin_enabled flag.",
            "ta": "இது Admin review-க்காக ஒரு tool-enablement review request-ஐ பதிவு செய்யும், audit மட்டுமே. இது எந்த tool-இன் public_enabled/admin_enabled flag-ஐயும் ஒருபோதும் மாற்றாது.",
        },
    ),
    ActionDefinition(
        action_type="propose_tool_permission_issue",
        target_type="deterministic_tool_registry_system",
        risk_level="low",
        mode="governance",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=("tool_name", "comment"),
        summary={
            "en": "Flag a possible permission/risk-tier issue with a deterministic tool for human review. Never changes any tool's permission tier itself.",
            "ta": "ஒரு deterministic tool-இன் permission/risk-tier issue-ஐ human review-க்காக flag செய்யவும். Tool-இன் permission tier-ஐ ஒருபோதும் மாற்றாது.",
        },
        confirmation_text={
            "en": "This will record a tool-permission issue flag for Admin review, audited only. It never changes any tool's permission tier, and it never enables file-write, shell, or external-MCP tools.",
            "ta": "இது Admin review-க்காக ஒரு tool-permission issue flag-ஐ பதிவு செய்யும், audit மட்டுமே. இது எந்த tool-இன் permission tier-ஐயும் ஒருபோதும் மாற்றாது, file-write, shell, external-MCP tools-ஐ ஒருபோதும் enable செய்யாது.",
        },
    ),
    # -- Document SFT workflow ---------------------------------------------
    ActionDefinition(
        action_type="propose_document_page_correction",
        target_type="document",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("page_number", "cleaned_text", "change_summary", "correction_types"),
        summary={
            "en": "Save a corrected version of one document page's text. The original extraction is never overwritten -- every save creates a new revision.",
            "ta": "ஒரு document page-இன் text-இன் திருத்தப்பட்ட பதிப்பை சேமிக்கவும். Original extraction ஒருபோதும் மேலெழுதப்படாது -- ஒவ்வொரு சேமிப்பும் ஒரு புதிய revision-ஐ உருவாக்கும்.",
        },
        confirmation_text={
            "en": "This will save a new revision of page {page_number} in document {target_public_id}. The previous revision remains in the page's revision history.",
            "ta": "இது document {target_public_id}-இல் page {page_number}-இன் புதிய revision-ஐ சேமிக்கும். முந்தைய revision page-இன் revision history-இல் தொடர்ந்து இருக்கும்.",
        },
    ),
    ActionDefinition(
        action_type="propose_document_ocr_rerun",
        target_type="document",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("page_number", "ocr_language"),
        summary={
            "en": "Rerun OCR on a single document page.",
            "ta": "ஒரு document page-இல் OCR-ஐ மீண்டும் இயக்கவும்.",
        },
        confirmation_text={
            "en": "This will rerun OCR on page {page_number} of document {target_public_id} and move it back to pending review.",
            "ta": "இது document {target_public_id}-இன் page {page_number}-இல் OCR-ஐ மீண்டும் இயக்கி, அதை மீண்டும் pending review-க்கு நகர்த்தும்.",
        },
    ),
    ActionDefinition(
        action_type="propose_bulk_cleanup",
        target_type="document",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("element_public_id", "action", "target_pages"),
        summary={
            "en": "Accept, reject, or apply a detected repeated header/footer/page-number cleanup suggestion across selected or all pages.",
            "ta": "கண்டறியப்பட்ட repeated header/footer/page-number cleanup suggestion-ஐ தேர்ந்தெடுக்கப்பட்ட அல்லது அனைத்து pages-இலும் accept, reject, அல்லது apply செய்யவும்.",
        },
        confirmation_text={
            "en": "This will {action} the cleanup suggestion {element_public_id} for document {target_public_id}. High-risk content such as rights/copyright text is never auto-removed by this action.",
            "ta": "இது document {target_public_id}-க்கான cleanup suggestion {element_public_id}-ஐ {action} செய்யும். Rights/copyright text போன்ற high-risk content இந்த action மூலம் ஒருபோதும் auto-remove செய்யப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="propose_tamil_corrections",
        target_type="document",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(
            "issue_public_id", "action", "edited_text", "apply_to_exact_duplicates_only", "notes",
        ),
        summary={
            "en": "Accept, reject, edit, or ignore one detected Tamil Unicode/OCR quality issue. Meaning-changing or ambiguous corrections always require a manual edit, never a direct accept.",
            "ta": "கண்டறியப்பட்ட ஒரு Tamil Unicode/OCR quality issue-ஐ accept, reject, edit, அல்லது ignore செய்யவும். பொருள் மாறும் அல்லது ஐயப்பாடான corrections எப்போதும் manual edit தேவைப்படும், நேரடியாக accept செய்யப்படாது.",
        },
        confirmation_text={
            "en": "This will {action} Tamil quality issue {issue_public_id} for document {target_public_id}.",
            "ta": "இது document {target_public_id}-க்கான Tamil quality issue {issue_public_id}-ஐ {action} செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="propose_chunk_generation",
        target_type="document",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Generate semantic chunks from this document's reviewed/approved pages using the existing chunk service.",
            "ta": "இந்த document-இன் reviewed/approved pages-இலிருந்து இருக்கும் chunk service-ஐப் பயன்படுத்தி semantic chunks-ஐ generate செய்யவும்.",
        },
        confirmation_text={
            "en": "This will generate semantic chunks for document {target_public_id} from its approved pages.",
            "ta": "இது document {target_public_id}-இன் approved pages-இலிருந்து semantic chunks-ஐ generate செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="propose_sft_candidate_generation",
        target_type="document",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("chunk_public_ids", "max_candidates"),
        summary={
            "en": "Generate SFT candidates from this document's approved semantic chunks. Only chunk types with a genuine, source-grounded template mapping produce candidates.",
            "ta": "இந்த document-இன் approved semantic chunks-இலிருந்து SFT candidates-ஐ generate செய்யவும். உண்மையான, source-grounded template mapping உள்ள chunk types மட்டுமே candidates-ஐ உருவாக்கும்.",
        },
        confirmation_text={
            "en": "This will generate SFT candidates for document {target_public_id} from its approved chunks.",
            "ta": "இது document {target_public_id}-இன் approved chunks-இலிருந்து SFT candidates-ஐ generate செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="propose_candidate_status_change",
        target_type="document_sft_candidate",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(
            "document_public_id", "action", "edited_instruction", "edited_context",
            "edited_response", "notes",
        ),
        summary={
            "en": "Approve, reject, edit, or flag one SFT candidate as needing correction. A candidate without a verified rights status cannot be approved.",
            "ta": "ஒரு SFT candidate-ஐ approve, reject, edit செய்யவும் அல்லது correction தேவை என flag செய்யவும். Verified rights status இல்லாத candidate-ஐ approve செய்ய முடியாது.",
        },
        confirmation_text={
            "en": "This will {action} SFT candidate {target_public_id}.",
            "ta": "இது SFT candidate {target_public_id}-ஐ {action} செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="propose_sft_export",
        target_type="document",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=(),
        summary={
            "en": "Export this document's approved SFT candidates to a JSONL file with a manifest and checksum. Only approved candidates are included.",
            "ta": "இந்த document-இன் approved SFT candidates-ஐ manifest மற்றும் checksum உடன் ஒரு JSONL file-ஆக export செய்யவும். Approved candidates மட்டுமே சேர்க்கப்படும்.",
        },
        confirmation_text={
            "en": "This will export the approved SFT candidates for document {target_public_id} to a new JSONL file.",
            "ta": "இது document {target_public_id}-க்கான approved SFT candidates-ஐ ஒரு புதிய JSONL file-ஆக export செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="propose_dataset_version_handoff",
        target_type="document",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("export_public_id",),
        summary={
            "en": "Record a governed readiness note pointing at an existing SFT export, for the Admin to act on via the existing Datasets page. Does not itself create a dataset version or start training.",
            "ta": "இருக்கும் SFT export-ஐச் சுட்டிக்காட்டும் ஒரு governed readiness note-ஐ பதிவு செய்யவும், Admin இருக்கும் Datasets page வழியாக செயல்பட. இது ஒரு dataset version-ஐ உருவாக்காது அல்லது training-ஐ தொடங்காது.",
        },
        confirmation_text={
            "en": "This will record a dataset-version handoff note for document {target_public_id} pointing at export {export_public_id}. It does not create a dataset version or start training.",
            "ta": "இது document {target_public_id}-க்கான dataset-version handoff note-ஐ export {export_public_id}-ஐ சுட்டிக்காட்டி பதிவு செய்யும். இது dataset version உருவாக்காது அல்லது training தொடங்காது.",
        },
    ),
    # -- Document SFT workflow finalization ---------------------------------
    ActionDefinition(
        action_type="propose_sft_export_validation",
        target_type="document",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("export_public_id",),
        summary={
            "en": "Re-derive an SFT export's manifest checksum from the file on disk and compare it against the stored value -- detects tampering or corruption without mutating anything.",
            "ta": "ஒரு SFT export-இன் manifest checksum-ஐ disk-இல் உள்ள file-இலிருந்து மீண்டும் கணக்கிட்டு, சேமிக்கப்பட்ட மதிப்புடன் ஒப்பிடவும் -- எதையும் மாற்றாமல் tampering அல்லது corruption-ஐக் கண்டறியும்.",
        },
        confirmation_text={
            "en": "This will validate export {export_public_id} for document {target_public_id} against the file on disk. Read-only -- nothing is changed.",
            "ta": "இது document {target_public_id}-க்கான export {export_public_id}-ஐ disk-இல் உள்ள file-உடன் ஒப்பிட்டு validate செய்யும். Read-only -- எதுவும் மாற்றப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="propose_sft_dataset_ingestion",
        target_type="document",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=False,
        payload_fields=("export_public_id",),
        summary={
            "en": "Ingest an approved, exported SFT record set into the existing dataset-record system as a new, clearly-labeled generated source. Idempotent -- ingesting the same export twice returns the existing result.",
            "ta": "Approve செய்யப்பட்ட, export செய்யப்பட்ட SFT record set-ஐ இருக்கும் dataset-record system-இல் ஒரு புதிய, தெளிவாக labelled generated source-ஆக ingest செய்யவும். Idempotent -- அதே export-ஐ இரண்டு முறை ingest செய்தாலும் இருக்கும் result-ஐயே திருப்பும்.",
        },
        confirmation_text={
            "en": "This will ingest export {export_public_id} for document {target_public_id} into the dataset-record system as a new source. This does not create or build a dataset version, and never starts training.",
            "ta": "இது document {target_public_id}-க்கான export {export_public_id}-ஐ dataset-record system-இல் ஒரு புதிய source-ஆக ingest செய்யும். இது ஒரு dataset version-ஐ உருவாக்காது அல்லது build செய்யாது, ஒருபோதும் training-ஐ தொடங்காது.",
        },
    ),
    ActionDefinition(
        action_type="propose_sft_dataset_version_build",
        target_type="document",
        risk_level="moderate",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("handoff_public_id", "dataset_name", "dataset_version"),
        summary={
            "en": "Create a dataset-version build proposal (draft only) from an ingested SFT handoff, reusing the existing dataset-versioning split/leakage system. Never finalizes or builds the version -- that remains a separate, direct Admin action on the Datasets page.",
            "ta": "ஒரு ingest செய்யப்பட்ட SFT handoff-இலிருந்து ஒரு dataset-version build proposal-ஐ (draft மட்டும்) உருவாக்கவும், இருக்கும் dataset-versioning split/leakage system-ஐப் பயன்படுத்தி. Version-ஐ ஒருபோதும் finalize அல்லது build செய்யாது -- அது Datasets page-இல் ஒரு தனி, நேரடி Admin action ஆகவே இருக்கும்.",
        },
        confirmation_text={
            "en": "This will create a draft dataset-version build proposal for handoff {handoff_public_id} (document {target_public_id}). It does not build or finalize the version, and never starts training.",
            "ta": "இது handoff {handoff_public_id}-க்காக (document {target_public_id}) ஒரு draft dataset-version build proposal-ஐ உருவாக்கும். இது version-ஐ build அல்லது finalize செய்யாது, ஒருபோதும் training-ஐ தொடங்காது.",
        },
    ),
    ActionDefinition(
        action_type="propose_sft_task_generation",
        target_type="document",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("chunk_public_ids", "max_candidates"),
        summary={
            "en": "Generate SFT candidates for one document using the existing deterministic, eligibility-gated generators. Every candidate still requires Admin review before approval.",
            "ta": "இருக்கும் deterministic, eligibility-gated generators-ஐப் பயன்படுத்தி ஒரு document-க்கான SFT candidates-ஐ generate செய்யவும். ஒவ்வொரு candidate-உம் approval-க்கு முன் Admin review தேவைப்படும்.",
        },
        confirmation_text={
            "en": "This will generate SFT candidates for document {target_public_id}.",
            "ta": "இது document {target_public_id}-க்கான SFT candidates-ஐ generate செய்யும்.",
        },
    ),
    ActionDefinition(
        action_type="propose_document_cleanup_scan",
        target_type="document",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Run the repeated-element cleanup detector (headers, footers, page numbers, copyright notices, navigation text, watermark/logo markers) across a document. Never removes anything automatically.",
            "ta": "ஒரு document முழுவதும் repeated-element cleanup detector-ஐ (headers, footers, page numbers, copyright notices, navigation text, watermark/logo markers) இயக்கவும். எதையும் தானாக அகற்றாது.",
        },
        confirmation_text={
            "en": "This will run cleanup detection for document {target_public_id}. Nothing is removed automatically.",
            "ta": "இது document {target_public_id}-க்கான cleanup detection-ஐ இயக்கும். எதுவும் தானாக அகற்றப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="propose_document_tamil_rule_entry",
        target_type="tamil_correction_rule",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(
            "incorrect_form", "approved_correction", "issue_category", "evidence",
            "confidence_band", "meaning_change_risk",
        ),
        summary={
            "en": "Propose a new Tamil correction-rule registry entry in draft status. The Admin Assistant can never approve or activate a rule -- only a human Admin can.",
            "ta": "ஒரு புதிய Tamil correction-rule registry entry-ஐ draft status-இல் propose செய்யவும். Admin Assistant ஒருபோதும் ஒரு rule-ஐ approve அல்லது activate செய்ய முடியாது -- ஒரு human Admin மட்டுமே செய்ய முடியும்.",
        },
        confirmation_text={
            "en": "This will create a new Tamil correction rule in draft status ({incorrect_form} -> {approved_correction}). It must go through Admin review before it can ever be applied automatically.",
            "ta": "இது draft status-இல் ஒரு புதிய Tamil correction rule-ஐ உருவாக்கும் ({incorrect_form} -> {approved_correction}). இது தானாக apply செய்யப்படுவதற்கு முன் Admin review-ஐக் கடக்க வேண்டும்.",
        },
    ),
    ActionDefinition(
        action_type="propose_document_security_review",
        target_type="document",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=(),
        summary={
            "en": "Scan a document's extracted text for prompt-injection phrases and PII patterns (email, phone, address, government ID, bank, secrets, absolute paths). Never alters Admin Assistant or system behavior.",
            "ta": "ஒரு document-இன் extracted text-இல் prompt-injection phrases மற்றும் PII patterns-ஐ (email, phone, address, government ID, bank, secrets, absolute paths) scan செய்யவும். Admin Assistant அல்லது system behavior-ஐ ஒருபோதும் மாற்றாது.",
        },
        confirmation_text={
            "en": "This will scan document {target_public_id} for prompt-injection and PII patterns. Read-only -- nothing is deleted or altered.",
            "ta": "இது document {target_public_id}-ஐ prompt-injection மற்றும் PII patterns-க்காக scan செய்யும். Read-only -- எதுவும் அழிக்கப்படாது அல்லது மாற்றப்படாது.",
        },
    ),
    ActionDefinition(
        action_type="propose_document_pii_exclusion",
        target_type="document",
        risk_level="low",
        mode="data",
        permission="admin",
        requires_reason=False,
        reversible=True,
        payload_fields=("finding_public_id", "action"),
        summary={
            "en": "Record a human review decision (reviewed/dismissed) on one detected PII/security finding. Secrets and absolute paths remain export-blocking regardless of this decision.",
            "ta": "கண்டறியப்பட்ட ஒரு PII/security finding-க்கு ஒரு human review முடிவை (reviewed/dismissed) பதிவு செய்யவும். Secrets மற்றும் absolute paths இந்த முடிவைப் பொருட்படுத்தாமல் export-blocking ஆகவே தொடரும்.",
        },
        confirmation_text={
            "en": "This will mark security finding {finding_public_id} for document {target_public_id} as reviewed.",
            "ta": "இது document {target_public_id}-க்கான security finding {finding_public_id}-ஐ reviewed என குறிக்கும்.",
        },
    ),
    # Phase 10: Admin Automation & Control Plane. Defining an automation is
    # itself the only governed action this phase introduces -- there is no
    # execution engine yet (see docs of this phase's report), so this
    # action's executor only validates the definition and durably records
    # it as this approval row; it never invokes `target_action_type`.
    ActionDefinition(
        action_type="admin_automation_define",
        target_type="admin_automation",
        risk_level="moderate",
        mode="governance",
        permission="admin",
        requires_reason=True,
        reversible=True,
        payload_fields=(
            "name",
            "description",
            "target_action_type",
            "target_type",
            "target_public_id",
            "target_action_parameters",
            "schedule_description",
        ),
        summary={
            "en": "Define a governed automation: a named intent to eventually take one existing "
            "governed action, kept pending future execution infrastructure. Never executes "
            "target_action_type -- only records and validates the definition.",
            "ta": "ஒரு governed automation-ஐ வரையறுக்கவும்: ஏற்கனவே உள்ள ஒரு governed action-ஐ "
            "எதிர்காலத்தில் மேற்கொள்ளும் நோக்கம், எதிர்கால execution infrastructure-க்காக "
            "காத்திருக்கும். target_action_type-ஐ ஒருபோதும் இயக்காது -- வரையறையை மட்டுமே "
            "பதிவு செய்து சரிபார்க்கும்.",
        },
        confirmation_text={
            "en": "This will define automation {target_public_id}, intended to eventually take "
            "the '{target_action_type}' action -- it will NOT execute that action now or "
            "automatically in the future.",
            "ta": "இது automation {target_public_id}-ஐ வரையறுக்கும், '{target_action_type}' "
            "action-ஐ எதிர்காலத்தில் மேற்கொள்ள நோக்கம் -- அது இப்போது அல்லது எதிர்காலத்தில் "
            "தானாகவே இயங்காது.",
        },
    ),
)

ACTION_BY_TYPE: dict[str, ActionDefinition] = {
    action.action_type: action for action in ACTION_DEFINITIONS
}


def get_action_definition(action_type: str) -> ActionDefinition | None:
    return ACTION_BY_TYPE.get(action_type)


def is_blocked_action_type(action_type: str) -> bool:
    lowered = action_type.lower()
    return any(token in lowered for token in BLOCKED_ACTION_SUBSTRINGS)


def is_known_action_type(action_type: str) -> bool:
    return action_type in ACTION_BY_TYPE and not is_blocked_action_type(action_type)


def actions_for_mode(mode: str) -> tuple[ActionDefinition, ...]:
    return tuple(action for action in ACTION_DEFINITIONS if action.mode == mode)


def actions_for_risk_level(risk_level: str) -> tuple[ActionDefinition, ...]:
    return tuple(action for action in ACTION_DEFINITIONS if action.risk_level == risk_level)
