"""Structured registry of every reachable Admin Dashboard page.

Mirrors `apps/admin-dashboard/src/components/Sidebar.jsx::navTree` and
`App.jsx`'s `active === '...'` routing exactly -- one entry per real,
reachable page, built by reading each page's own component (its real
tabs/sections and the services it calls), never invented. A page whose
component is still `PlaceholderPage` (Chat Testing, Audit Logs,
Settings) is marked `implemented=False` and the assistant must say so
plainly rather than describe functionality that does not exist yet.

`registry_version` is stamped onto every context snapshot and feedback
row so a later registry change never silently reinterprets old data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

REGISTRY_VERSION = "v1"

# Mirrors admin_assistant_tool_invocations.mode / admin_assistant_feedback
# usage -- these are UI *filters* over one assistant, never separate bots.
ASSISTANT_MODES = ("guide", "data", "governance", "rag", "model", "system")


@dataclass(frozen=True)
class PageEntry:
    page_id: str
    nav_key: str
    group: str | None  # top-level nav group label this page nests under, if any
    implemented: bool
    mode: str
    title: dict[str, str]
    purpose: dict[str, str]
    tabs: tuple[str, ...] = ()
    related_page_ids: tuple[str, ...] = ()
    safety_note: dict[str, str] = field(default_factory=dict)


DASHBOARD_PAGES: tuple[PageEntry, ...] = (
    PageEntry(
        page_id="overview",
        nav_key="Overview",
        group=None,
        implemented=True,
        mode="guide",
        title={"en": "Overview", "ta": "கண்ணோட்டம்"},
        purpose={
            "en": "The landing page after login: product status (chatbot, admin dashboard, core model) and foundation record counts (dataset records, training jobs, registered models).",
            "ta": "Login ஆன பிறகு காணப்படும் முதல் பக்கம்: product status (chatbot, admin dashboard, core model) மற்றும் foundation record எண்ணிக்கைகள் (dataset records, training jobs, registered models).",
        },
        related_page_ids=("system", "data_overview"),
        safety_note={"en": "Read-only.", "ta": "படிக்க மட்டுமே."},
    ),
    PageEntry(
        page_id="system",
        nav_key="System",
        group=None,
        implemented=True,
        mode="system",
        title={"en": "System", "ta": "System"},
        purpose={
            "en": "Read-only control-plane status: database health/schema version/journal mode/backups, safe runtime configuration (environment, log level, audit), and recent audit events.",
            "ta": "Read-only control-plane status: database health/schema version/journal mode/backups, பாதுகாப்பான runtime configuration (environment, log level, audit), மற்றும் சமீபத்திய audit events.",
        },
        related_page_ids=("overview",),
        safety_note={
            "en": "Never displays file paths or secret values.",
            "ta": "கோப்பு பாதைகள் அல்லது secret values ஒருபோதும் காட்டப்படாது.",
        },
    ),
    PageEntry(
        page_id="data_overview",
        nav_key="Data Overview",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "Data Overview", "ta": "தரவு கண்ணோட்டம்"},
        purpose={
            "en": "A single read-only snapshot of every data-related area: sources, documents, dataset records, quality, duplicates, versions, corpus builds, RAG knowledge spaces, governed builds, and pretraining readiness.",
            "ta": "மூலங்கள், ஆவணங்கள், dataset records, தரம், நகல்கள், versions, corpus builds, RAG knowledge spaces, governed builds, pretraining readiness ஆகிய அனைத்தையும் ஒரே பார்வையில் காட்டும் read-only பக்கம்.",
        },
        related_page_ids=("datasets", "documents"),
        safety_note={
            "en": "Read-only: this page never creates, approves, or exports anything.",
            "ta": "இந்த பக்கம் படிக்க மட்டுமே -- இது எதையும் உருவாக்காது, approve செய்யாது, export செய்யாது.",
        },
    ),
    PageEntry(
        page_id="datasets",
        nav_key="Datasets",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "Datasets", "ta": "Datasets"},
        purpose={
            "en": "Manage dataset sources and records: create manual sources, add records, run the review queue, assess quality, inspect duplicate conflicts, import files, and build/export dataset versions.",
            "ta": "Dataset sources மற்றும் records-ஐ நிர்வகிக்கவும்: manual sources உருவாக்குதல், records சேர்த்தல், review queue, quality assessment, duplicate conflicts பார்வையிடல், கோப்புகளை import செய்தல், dataset versions உருவாக்கி export செய்தல்.",
        },
        tabs=("Sources", "Records", "Review Queue", "Quality", "Versions"),
        related_page_ids=("manual_data", "sources_rights", "documents", "data_overview"),
        safety_note={
            "en": "Imported/uploaded content always lands as a draft record -- nothing is auto-approved.",
            "ta": "Import/upload செய்யப்பட்ட உள்ளடக்கம் எப்போதும் draft record ஆகவே சேமிக்கப்படும் -- எதுவும் தானாக approve ஆகாது.",
        },
    ),
    PageEntry(
        page_id="manual_data",
        nav_key="Manual Data",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "Manual Data", "ta": "கைமுறை தரவு"},
        purpose={
            "en": "A governed staging area for hand-authored Tamil/English/Tanglish language data (spoken examples, conversations, Q&A, instructions, dictionary entries, translations, knowledge notes) -- always linked to a source declaration.",
            "ta": "கையால் எழுதப்பட்ட தமிழ்/ஆங்கிலம்/டேங்கிலீஷ் தரவுக்கான ஒரு regulated staging பகுதி (spoken examples, conversations, Q&A, instructions, dictionary entries, translations, knowledge notes) -- எப்போதும் ஒரு source declaration உடன் இணைக்கப்பட்டிருக்கும்.",
        },
        tabs=("Create Data", "Review Queue", "Verification Queue", "Approved"),
        related_page_ids=("sources_rights", "datasets", "data_overview"),
        safety_note={
            "en": "Every manual record starts as a draft; approval always records exactly which uses were granted.",
            "ta": "ஒவ்வொரு கைமுறை record-உம் draft ஆகவே தொடங்கும்; approval எப்போதும் எந்தெந்த uses அளிக்கப்பட்டன என்பதை பதிவு செய்யும்.",
        },
    ),
    PageEntry(
        page_id="sources_rights",
        nav_key="Sources & Rights",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "Sources & Rights", "ta": "மூலங்களும் உரிமைகளும்"},
        purpose={
            "en": "A governed registry of where data came from, who owns it, what licence/permission applies, and exactly which uses (RAG, training, evaluation, commercial, public export, redistribution) are allowed.",
            "ta": "தரவு எங்கிருந்து வந்தது, யாருக்கு உரிமை உண்டு, என்ன license/permission பொருந்தும், மற்றும் எந்தெந்த பயன்பாடுகள் (RAG, training, evaluation, commercial, public export, redistribution) அனுமதிக்கப்படுகின்றன என்பதை பதிவு செய்யும் அமைப்பு.",
        },
        tabs=("Sources", "Rights Review", "Usage Eligibility"),
        related_page_ids=("documents", "corpus_builder", "knowledge_rag"),
        safety_note={
            "en": "Unknown or pending-review rights fail closed for training, commercial use, and public export.",
            "ta": "தெரியாத அல்லது pending rights, training/commercial/public export-க்கு fail-closed ஆகும்.",
        },
    ),
    PageEntry(
        page_id="external_data_providers",
        nav_key="External Data Providers",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "External Data Providers", "ta": "வெளிப்புற தரவு வழங்குநர்கள்"},
        purpose={
            "en": "A governed registry of external organizations/websites Brud AI could potentially pull training/RAG data from -- access mode, authentication, connector capabilities, trust, and lifecycle. Registering, verifying, or enabling a provider here never grants a dataset licence, RAG use, training use, or commercial use by itself.",
            "ta": "Brud AI training/RAG தரவை எடுக்கக்கூடிய வெளிப்புற நிறுவனங்கள்/வலைத்தளங்களின் ஒரு regulated registry -- access mode, authentication, connector capabilities, trust, lifecycle. இங்கு ஒரு provider-ஐ பதிவு, verify, அல்லது enable செய்வது தானாகவே dataset licence, RAG use, training use, அல்லது commercial use-ஐ வழங்காது.",
        },
        tabs=("Overview", "Providers", "Add Provider", "Domains", "Capabilities", "Credentials", "Connection Tests", "History"),
        related_page_ids=("sources_rights", "data_overview", "dataset_discovery"),
        safety_note={
            "en": "Built-in providers always start draft/unverified/disabled. No credential value is ever stored, logged, or returned -- only a reference (an environment variable name). No dataset search or download happens here.",
            "ta": "Built-in providers எப்போதும் draft/unverified/disabled ஆகவே தொடங்கும். எந்த credential value-உம் ஒருபோதும் சேமிக்கப்படாது, log செய்யப்படாது, அல்லது திரும்பத் தரப்படாது -- ஒரு reference (environment variable பெயர்) மட்டுமே. இங்கு எந்த dataset search அல்லது download-உம் நடக்காது.",
        },
    ),
    PageEntry(
        page_id="dataset_discovery",
        nav_key="Dataset Discovery",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "Dataset Discovery", "ta": "தரவுத்தொகுப்பு கண்டுபிடிப்பு"},
        purpose={
            "en": "A governed research workspace: describe a dataset requirement, search enabled external providers, review normalized/deduplicated/scored candidates, compare 2-5 of them side by side, and save the research session. Never downloads a file, imports a dataset, or grants a licence/RAG/training/evaluation/commercial-use approval by itself -- every candidate stays a research artifact for the Sources & Rights Registry to formally approve later.",
            "ta": "ஒரு regulated ஆராய்ச்சி workspace: dataset தேவையை விவரிக்கவும், enabled external providers-ஐ தேடவும், normalize/deduplicate/score செய்யப்பட்ட candidates-ஐ பார்க்கவும், 2-5 candidates-ஐ ஒப்பிடவும், research session-ஐ சேமிக்கவும். இது தானாகவே எந்த file-ஐயும் download செய்யாது, dataset-ஐ import செய்யாது, அல்லது licence/RAG/training/evaluation/commercial-use approval-ஐ வழங்காது -- ஒவ்வொரு candidate-உம் Sources & Rights Registry பின்னர் முறையாக approve செய்ய வேண்டிய ஆராய்ச்சி artifact ஆகவே இருக்கும்.",
        },
        tabs=("Sessions", "Requirement", "Candidates", "Comparison", "History"),
        related_page_ids=(
            "external_data_providers", "sources_rights", "data_overview", "dataset_verification",
        ),
        safety_note={
            "en": "Only providers meeting Phase 9's enabled/lifecycle/capability rules are ever searched. A missing dataset card or unknown licence is always shown as a warning, never hidden. A single provider's failure never discards another provider's results.",
            "ta": "Phase 9-ன் enabled/lifecycle/capability விதிகளை பூர்த்தி செய்யும் providers மட்டுமே தேடப்படும். Missing dataset card அல்லது unknown licence எப்போதும் warning ஆகவே காட்டப்படும், மறைக்கப்படாது. ஒரு provider தோல்வியடைந்தாலும் மற்ற providers-ன் results இழக்கப்படாது.",
        },
    ),
    PageEntry(
        page_id="dataset_verification",
        nav_key="Dataset Verification",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "Dataset Verification", "ta": "தரவுத்தொகுப்பு சரிபார்ப்பு"},
        purpose={
            "en": "A governed workflow to verify a Phase 10 dataset candidate's identity, official source, dataset card, declared/verified licence, terms, privacy/consent, upstream sources, and independently-assessed RAG/training/evaluation/commercial-use permissions, producing an evidence-backed verification record. Never downloads a dataset payload file, imports records, activates RAG, creates a training dataset version, starts training, or releases a model -- and never grants a permission automatically. Only an explicit Admin review may set an approved/prohibited status.",
            "ta": "ஒரு Phase 10 dataset candidate-இன் identity, official source, dataset card, declared/verified licence, terms, privacy/consent, upstream sources, மற்றும் சுயேச்சையாக assess செய்யப்பட்ட RAG/training/evaluation/commercial-use permissions-ஐ சரிபார்க்கும் ஒரு regulated workflow, இது evidence-backed verification record ஒன்றை உருவாக்கும். இது ஒருபோதும் dataset payload file-ஐ download செய்யாது, records-ஐ import செய்யாது, RAG-ஐ activate செய்யாது, training dataset version உருவாக்காது, training தொடங்காது, அல்லது model release செய்யாது -- மேலும் ஒரு permission-ஐ ஒருபோதும் தானாக வழங்காது. ஒரு வெளிப்படையான Admin review மட்டுமே approved/prohibited status-ஐ அமைக்க முடியும்.",
        },
        tabs=(
            "Overview", "Verification Cases", "Evidence", "Identity", "Licence & Terms",
            "Permissions", "Upstream Sources", "Conflicts", "Review", "Final Report", "History",
        ),
        related_page_ids=(
            "dataset_discovery", "sources_rights", "quality_approval", "data_overview",
            "dataset_sample_import",
        ),
        safety_note={
            "en": "Evidence is only ever fetched from a registered provider domain or an admin-approved upstream domain, with SSRF/redirect/size/MIME protections. Training and commercial permission can never be automatically set to allowed -- only a human Admin review can. A finalized case is immutable except for lazy reverification, which demotes any prior approval whose evidence has since changed.",
            "ta": "Evidence ஒரு பதிவு செய்யப்பட்ட provider domain அல்லது admin-approved upstream domain-இலிருந்து மட்டுமே பெறப்படும், SSRF/redirect/size/MIME பாதுகாப்புகளுடன். Training மற்றும் commercial permission ஒருபோதும் தானாக allowed என அமைக்கப்படாது -- ஒரு மனித Admin review மட்டுமே அதை செய்ய முடியும். ஒரு finalize செய்யப்பட்ட case, lazy reverification தவிர மாற்ற முடியாதது, இது evidence மாறியிருக்கும் எந்த முந்தைய approval-ஐயும் தாழ்த்தும்.",
        },
    ),
    PageEntry(
        page_id="dataset_sample_import",
        nav_key="Sample Import & Quarantine",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "Sample Import & Quarantine", "ta": "மாதிரி இறக்குமதி & தனிமைப்படுத்தல்"},
        purpose={
            "en": "A governed workflow to safely download a small, bounded sample from a finalized Phase 11 verification case into isolated quarantine, validate file safety, scan for malware-like content, extract archives safely, parse supported formats, and check for PII, safety issues, quality problems, duplicates, and evaluation contamination -- producing an immutable sample-validation report and a RAG-sandbox eligibility signal. Never downloads a full dataset, activates RAG, creates a training dataset version, starts training, or releases a model, and never grants training approval.",
            "ta": "ஒரு finalize செய்யப்பட்ட Phase 11 verification case-இலிருந்து, ஒரு சிறிய, bounded sample-ஐ தனிமைப்படுத்தப்பட்ட quarantine-க்குள் பாதுகாப்பாக download செய்து, file safety-ஐ validate செய்து, malware-like content-ஐ scan செய்து, archives-ஐ பாதுகாப்பாக extract செய்து, supported formats-ஐ parse செய்து, PII, safety issues, quality problems, duplicates, மற்றும் evaluation contamination-ஐ சரிபார்க்கும் ஒரு regulated workflow, இது immutable sample-validation report மற்றும் RAG-sandbox eligibility signal ஒன்றை உருவாக்கும். இது ஒருபோதும் முழு dataset-ஐ download செய்யாது, RAG-ஐ activate செய்யாது, training dataset version உருவாக்காது, training தொடங்காது, அல்லது model release செய்யாது, மேலும் ஒருபோதும் training approval வழங்காது.",
        },
        tabs=(
            "Overview", "Sample Imports", "Approval", "Files", "Security Scan", "Parsed Records",
            "PII & Sensitive Data", "Quality", "Duplicates & Conflicts", "Contamination",
            "Human Review", "Final Report", "Deletion & History",
        ),
        related_page_ids=("dataset_verification", "data_overview", "rag_sandbox"),
        safety_note={
            "en": "Downloads are bounded by an explicit, separately-approved byte limit and only from an admin-allowlisted domain, with the same SSRF/redirect protections as dataset verification. No quarantined record ever enters RAG or training. Original quarantined files/records are never modified -- only redacted or corrected derived copies are created, always under human review.",
            "ta": "Downloads ஒரு வெளிப்படையான, தனியாக approve செய்யப்பட்ட byte limit-உக்குள், மற்றும் admin-allowlisted domain-இலிருந்து மட்டுமே, dataset verification-இன் அதே SSRF/redirect பாதுகாப்புகளுடன் bound செய்யப்படும். எந்த quarantine செய்யப்பட்ட record-உம் ஒருபோதும் RAG அல்லது training-க்குள் நுழையாது. Original quarantine செய்யப்பட்ட files/records ஒருபோதும் மாற்றப்படாது -- redacted அல்லது corrected derived copies மட்டுமே, எப்போதும் human review-இன் கீழ் உருவாக்கப்படும்.",
        },
    ),
    PageEntry(
        page_id="rag_sandbox",
        nav_key="RAG Sandbox",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "RAG Sandbox", "ta": "RAG Sandbox"},
        purpose={
            "en": "A governed, structurally-isolated sandbox to test a finalized Phase 12 sample-validation report's accepted records in a real retrieval and grounded-generation pipeline before any production RAG or training decision. Promotes only accepted records into a dedicated, never-production-visible knowledge space; builds BM25/vector/hybrid indexes; runs retrieval and grounded-answer tests including insufficient-evidence, conflicting-source, and prompt-injection cases; validates citations; requires human review; and produces an immutable report with advisory production-RAG-readiness and training-data-observation signals. Never activates production RAG, never creates a training dataset version, and never starts training.",
            "ta": "எந்த production RAG அல்லது training முடிவுக்கு முன்பும், finalize செய்யப்பட்ட ஒரு Phase 12 sample-validation report-இன் accepted records-ஐ, ஒரு உண்மையான retrieval மற்றும் grounded-generation pipeline-இல் test செய்ய, ஒரு regulated, structural-ஆக தனிமைப்படுத்தப்பட்ட sandbox. accept செய்யப்பட்ட records-ஐ மட்டும், ஒருபோதும் production-இல் தெரியாத ஒரு தனி knowledge space-க்குள் promote செய்து; BM25/vector/hybrid indexes-ஐ build செய்து; insufficient-evidence, conflicting-source, மற்றும் prompt-injection cases உட்பட retrieval மற்றும் grounded-answer tests-ஐ இயக்கி; citations-ஐ validate செய்து; human review-ஐ கட்டாயமாக்கி; advisory production-RAG-readiness மற்றும் training-data-observation signals-உடன் ஒரு immutable report-ஐ உருவாக்கும். இது ஒருபோதும் production RAG-ஐ activate செய்யாது, training dataset version உருவாக்காது, training தொடங்காது.",
        },
        tabs=(
            "Overview", "Experiments", "Approval", "Corpus", "Chunks", "Indexes", "Query Sets",
            "Retrieval Results", "Grounded Answers", "Citations", "Language Tests",
            "Conflict Tests", "Injection Tests", "Human Review", "Final Report", "Acceptance",
            "Deletion & History",
        ),
        related_page_ids=("dataset_sample_import", "knowledge_rag", "data_overview"),
        safety_note={
            "en": "Every sandbox experiment builds its own dedicated, never-production-visible knowledge space and index -- production RAG and public chat can never see sandbox data, and sandbox retrieval never falls back to production data. Only accepted, promotion-eligible Phase 12 records may be promoted; PII-blocked, rejected, and excluded records are always blocked. Acceptance of a sandbox report never activates production RAG and never approves training -- those remain separate, later decisions.",
            "ta": "ஒவ்வொரு sandbox experiment-உம், ஒருபோதும் production-இல் தெரியாத, தனிப்பட்ட ஒரு knowledge space மற்றும் index-ஐ உருவாக்கும் -- production RAG மற்றும் public chat ஒருபோதும் sandbox தரவை பார்க்க முடியாது, மேலும் sandbox retrieval ஒருபோதும் production தரவுக்கு fallback ஆகாது. accept செய்யப்பட்ட, promotion-eligible ஆன Phase 12 records மட்டுமே promote செய்யப்படலாம்; PII-blocked, rejected, மற்றும் excluded records எப்போதும் தடுக்கப்படும். ஒரு sandbox report-இன் acceptance ஒருபோதும் production RAG-ஐ activate செய்யாது, training-ஐயும் approve செய்யாது -- அவை தனியான, பிற்பட்ட முடிவுகளாகவே உள்ளன.",
        },
    ),
    PageEntry(
        page_id="incremental_training",
        nav_key="Incremental Training",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "Incremental Training", "ta": "Incremental Training"},
        purpose={
            "en": "A governed workflow to take an accepted Phase 13 RAG sandbox report, assess training suitability, transform and review approved candidates into training examples, promote them into an immutable dataset version, request and separately approve a bounded training run, execute it against the existing pretraining/instruction-tuning infrastructure, verify and evaluate every checkpoint, check for regression and catastrophic forgetting against a baseline, collect bounded human review, and record a separate, explicit Admin acceptance decision. An accepted checkpoint can only ever register as a staging model candidate through the existing model registry -- this page never activates a production model, never creates a release, and never lets RAG sandbox acceptance substitute for training approval.",
            "ta": "accept செய்யப்பட்ட ஒரு Phase 13 RAG sandbox report-ஐ எடுத்து, training suitability-ஐ assess செய்து, approve செய்யப்பட்ட candidates-ஐ training examples-ஆக transform செய்து review செய்து, அவற்றை ஒரு immutable dataset version-ஆக promote செய்து, ஒரு bounded training run-ஐ கோரி தனியாக approve செய்து, இருக்கும் pretraining/instruction-tuning infrastructure-க்கு எதிராக அதை இயக்கி, ஒவ்வொரு checkpoint-ஐயும் verify மற்றும் evaluate செய்து, ஒரு baseline-க்கு எதிராக regression மற்றும் catastrophic forgetting-ஐ சரிபார்த்து, bounded human review-ஐ சேகரித்து, தனியான, தெளிவான Admin acceptance முடிவை பதிவு செய்யும் ஒரு regulated workflow. accept செய்யப்பட்ட ஒரு checkpoint, இருக்கும் model registry வழியாக ஒரு staging model candidate-ஆக மட்டுமே register செய்யப்படும் -- இந்த page ஒருபோதும் ஒரு production model-ஐ activate செய்யாது, ஒரு release உருவாக்காது, மேலும் RAG sandbox acceptance-ஐ training approval-க்கு பதிலாக ஒருபோதும் பயன்படுத்தாது.",
        },
        tabs=(
            "Overview", "Assessments", "Candidates", "Dataset Promotion", "Training Runs",
            "Checkpoints", "Reports & Acceptance",
        ),
        related_page_ids=("rag_sandbox", "data_overview", "pretraining_readiness"),
        safety_note={
            "en": "Every governance gate is a separate, explicit Admin decision: RAG sandbox acceptance never implies training-data approval, training-data approval never implies a training-run approval, a training-run approval never implies checkpoint acceptance, and checkpoint acceptance never implies a production model release. A major_regression comparison result always blocks checkpoint acceptance and cannot be overridden from this page.",
            "ta": "ஒவ்வொரு governance gate-உம், ஒரு தனியான, தெளிவான Admin முடிவு: RAG sandbox acceptance ஒருபோதும் training-data approval-ஐ குறிக்காது, training-data approval ஒருபோதும் training-run approval-ஐ குறிக்காது, ஒரு training-run approval ஒருபோதும் checkpoint acceptance-ஐ குறிக்காது, மேலும் checkpoint acceptance ஒருபோதும் ஒரு production model release-ஐ குறிக்காது. ஒரு major_regression comparison result எப்போதும் checkpoint acceptance-ஐ தடுக்கும், இந்த page-இலிருந்து அதை override செய்ய முடியாது.",
        },
    ),
    PageEntry(
        page_id="documents",
        nav_key="Documents",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "Documents", "ta": "ஆவணங்கள்"},
        purpose={
            "en": "Upload PDFs, link a source/rights record, extract text (embedded or Tamil-English OCR), review pages side-by-side with the original scan, and hand off approved pages to segmentation.",
            "ta": "PDF பதிவேற்றி, ஒரு source/rights பதிவை இணைத்து, உரையைப் பிரித்தெடுத்து (embedded அல்லது தமிழ்-ஆங்கில OCR), பக்கங்களை மூல ஸ்கேனுடன் ஒப்பிட்டு சரிபார்த்து, approved பக்கங்களை segmentation-க்கு அனுப்பவும்.",
        },
        tabs=(
            "Overview", "Upload", "Processing", "Page Review", "Repeated Elements",
            "Tamil Quality", "Candidates", "SFT Candidates", "Export", "Security Review",
            "Media & Tables", "Tamil Corrections",
        ),
        related_page_ids=("chunk_studio", "datasets", "sources_rights", "document_wizard"),
        safety_note={
            "en": "Approving a page only records a human review decision on its text -- it never implies rights or training approval. SFT candidate approval requires a verified rights status and never starts training.",
            "ta": "ஒரு பக்கத்தை approve செய்வது அதன் உரையின் மீதான ஒரு human review முடிவை மட்டுமே பதிவு செய்யும் -- rights அல்லது training approval-ஐ குறிக்காது. SFT candidate approval-க்கு verified rights status தேவை, training-ஐ ஒருபோதும் தொடங்காது.",
        },
    ),
    PageEntry(
        page_id="document_wizard",
        nav_key="Document Wizard",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "Document Wizard", "ta": "Document Wizard"},
        purpose={
            "en": "Guided status across all fourteen Document SFT workflow steps (Upload through Training Readiness) for one selected document, computed from real current state. Most steps are read-only summaries that link back to the Documents page to act, but steps 10-13 (Validate Export, Dataset Handoff, Preview Split, Build Dataset Version) include their own explicit preview-then-confirm actions.",
            "ta": "ஒரு document-க்கான பதினான்கு Document SFT workflow steps-இன் (Upload முதல் Training Readiness வரை) வழிகாட்டப்பட்ட status, உண்மையான தற்போதைய நிலையிலிருந்து கணக்கிடப்படும். பெரும்பாலான steps read-only summaries, Documents page-க்கு இணைக்கின்றன, ஆனால் steps 10-13 (Validate Export, Dataset Handoff, Preview Split, Build Dataset Version) தங்களுடைய சொந்த preview-then-confirm actions கொண்டுள்ளன.",
        },
        tabs=(),
        related_page_ids=("documents", "chunk_studio", "datasets"),
        safety_note={
            "en": "Steps 1-9 and 14 are read-only. Steps 10-13 can validate an export, ingest approved records into the dataset system, and build a dataset version -- each requires an explicit preview and a separate confirm action, and none of them starts training.",
            "ta": "Steps 1-9 மற்றும் 14 read-only. Steps 10-13 export-ஐ validate செய்யலாம், approved records-ஐ dataset system-க்குள் ingest செய்யலாம், dataset version-ஐ build செய்யலாம் -- ஒவ்வொன்றுக்கும் தனித்தனி preview மற்றும் confirm action தேவை, எதுவும் training-ஐ தொடங்காது.",
        },
    ),
    PageEntry(
        page_id="chunk_studio",
        nav_key="Chunk & Record Studio",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "Chunk & Record Studio", "ta": "Chunk & Record Studio"},
        purpose={
            "en": "Turn approved PDF pages into typed semantic chunks, then build reviewed structured dataset candidates (dictionary, grammar, Q&A, translation, Tanglish, knowledge, RAG) from those chunks -- always preserving exact source lineage.",
            "ta": "Approve செய்யப்பட்ட PDF பக்கங்களை typed semantic chunks ஆக மாற்றி, பிறகு அவற்றிலிருந்து reviewed structured dataset candidates உருவாக்கவும் -- மூலப் lineage எப்போதும் சரியாக பாதுகாக்கப்படும்.",
        },
        tabs=("Documents", "Chunk Editor", "Structure", "Record Builder", "Conflicts", "Approved"),
        related_page_ids=("quality_approval", "datasets", "knowledge_rag"),
        safety_note={
            "en": "Approving a chunk never implies rights, training, or export approval by itself -- run a usage-eligibility check first.",
            "ta": "ஒரு chunk-ஐ approve செய்வது தானாகவே rights, training, அல்லது export approval-ஐ குறிக்காது -- முதலில் usage-eligibility check இயக்கவும்.",
        },
    ),
    PageEntry(
        page_id="quality_approval",
        nav_key="Quality & Approval",
        group="Data",
        implemented=True,
        mode="governance",
        title={"en": "Quality & Approval", "ta": "Quality & Approval"},
        purpose={
            "en": "One consolidated review queue across every governed entity: normalized quality issues, persisted duplicate/conflict groups, and a per-target-use approval decision -- never a single global 'approved' flag.",
            "ta": "Governed செய்யப்படும் ஒவ்வொரு entity-க்கும் ஒரே consolidated review queue: normalized quality issues, சேமிக்கப்பட்ட duplicate/conflict groups, மற்றும் ஒவ்வொரு target use-க்கும் தனித்தனி approval முடிவு.",
        },
        tabs=("Queue", "Review Detail", "Quality", "Duplicates", "Conflicts", "Approvals", "Export Readiness", "History"),
        related_page_ids=("builds_pipelines", "chunk_studio", "manual_data", "datasets"),
        safety_note={
            "en": "Never deletes, merges, or auto-approves anything -- every override requires a reason and is audited.",
            "ta": "எதையும் ஒருபோதும் delete, merge, அல்லது auto-approve செய்யாது -- ஒவ்வொரு override-உம் ஒரு காரணத்தை கோரும், audit செய்யப்படும்.",
        },
    ),
    PageEntry(
        page_id="builds_pipelines",
        nav_key="Builds & Pipelines",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "Builds & Pipelines", "ta": "Builds & Pipelines"},
        purpose={
            "en": "Turn approved, traceable Data Studio content into a governed, immutable dataset version for a specific target pipeline, then hand it off explicitly into RAG ingestion or tokenizer/pretraining/instruction-tuning workflows.",
            "ta": "Approve செய்யப்பட்ட, traceable Data Studio content-ஐ ஒரு குறிப்பிட்ட target pipeline-க்காக ஒரு governed, immutable dataset version ஆக மாற்றி, பிறகு RAG ingestion அல்லது tokenizer/pretraining/instruction-tuning workflows-க்கு வெளிப்படையாக handoff செய்யவும்.",
        },
        tabs=("Create Build", "Build Preview", "Blocked Records", "RAG Handoffs", "Tokenizer & Training", "Evaluation Builds", "Manifests", "Lineage"),
        related_page_ids=("datasets", "knowledge_rag", "pretraining_readiness"),
        safety_note={
            "en": "Nothing here is published, released, or trained automatically -- every build requires an explicit Confirm and Execute.",
            "ta": "இங்கு எதுவும் தானாக publish, release, அல்லது train செய்யப்படாது -- ஒவ்வொரு build-க்கும் ஒரு வெளிப்படையான Confirm மற்றும் Execute தேவை.",
        },
    ),
    PageEntry(
        page_id="corpus_builder",
        nav_key="Corpus Builder",
        group="Data",
        implemented=True,
        mode="data",
        title={"en": "Corpus Builder", "ta": "Corpus Builder"},
        purpose={
            "en": "Assemble a large Tamil/English/Tanglish corpus with proven origin, licence, quality, privacy, and contamination safety before any content becomes an immutable, exportable corpus version.",
            "ta": "origin, licence, quality, privacy, contamination பாதுகாப்பு நிரூபிக்கப்பட்ட பிறகே ஒரு பெரிய Tamil/English/Tanglish corpus-ஐ, immutable, exportable corpus version ஆக உருவாக்கவும்.",
        },
        tabs=("Policies", "Sources & Licences", "Snapshots & Extraction", "Normalization & Segmentation", "Quality & Safety", "Deduplication & Contamination", "Collections & Balance", "Builds & Partitions", "Versions/Export/Manifest"),
        related_page_ids=("pretraining_readiness",),
        safety_note={
            "en": "Finalizing a corpus export never starts model training automatically.",
            "ta": "Corpus export-ஐ finalize செய்வது தானாக model training-ஐ தொடங்காது.",
        },
    ),
    PageEntry(
        page_id="knowledge_rag",
        nav_key="Knowledge & RAG",
        group="Data",
        implemented=True,
        mode="rag",
        title={"en": "Knowledge & RAG", "ta": "Knowledge & RAG"},
        purpose={
            "en": "Ingest approved knowledge sources into chunked, indexed evidence, then test grounded retrieval and generation in a private admin lab.",
            "ta": "Approved knowledge sources-ஐ chunk செய்து, index செய்து, private admin lab-இல் grounded retrieval மற்றும் generation-ஐ சோதிக்கவும்.",
        },
        tabs=("Knowledge Spaces", "Sources", "Source Versions", "Chunking", "Chunk Quality", "Embedding Models/Runs", "Vector/Keyword Indexes", "Retrieval Lab", "RAG Chat Lab"),
        related_page_ids=("data_overview",),
        safety_note={
            "en": "The public chatbot is never connected here -- this remains an admin-only lab.",
            "ta": "பொது chatbot இங்கே ஒருபோதும் இணைக்கப்படவில்லை -- இது admin-மட்டும் lab ஆகவே இருக்கும்.",
        },
    ),
    PageEntry(
        page_id="pretraining_readiness",
        nav_key="Pretraining Readiness",
        group="Data",
        implemented=True,
        mode="model",
        title={"en": "Pretraining Readiness", "ta": "Pretraining Readiness"},
        purpose={
            "en": "Bridge an approved corpus release into a tokenizer-training corpus and a frozen pretraining dataset snapshot, then run the 17-dimension readiness gate before any real pretraining.",
            "ta": "ஒரு approved corpus release-ஐ tokenizer-training corpus ஆகவும், ஒரு frozen pretraining dataset snapshot ஆகவும் மாற்றி, உண்மையான pretraining-க்கு முன் 17-dimension readiness gate-ஐ இயக்கவும்.",
        },
        tabs=("Tokenizer Corpus", "Tokenizer Candidates", "Dataset Snapshot", "Training Config & Smoke Runs", "Readiness"),
        related_page_ids=("evaluation",),
        safety_note={
            "en": "A preparation/safety gate only -- it does not itself start a production pretraining run.",
            "ta": "இது ஒரு preparation/safety gate மட்டுமே -- இது production pretraining run-ஐ தானாக தொடங்காது.",
        },
    ),
    PageEntry(
        page_id="evaluation",
        nav_key="Evaluation",
        group="Data",
        implemented=True,
        mode="model",
        title={"en": "Evaluation", "ta": "Evaluation"},
        purpose={
            "en": "Author versioned evaluation fixture suites, run bounded generation against every fixture, review results, and assess chat-readiness for a candidate.",
            "ta": "Version செய்யப்பட்ட evaluation fixture suites-ஐ உருவாக்கி, ஒவ்வொரு fixture-க்கும் bounded generation இயக்கி, results-ஐ review செய்து, ஒரு candidate-இன் chat-readiness-ஐ மதிப்பிடவும்.",
        },
        related_page_ids=("data_overview",),
        safety_note={
            "en": "A candidate remains not_public_chat_ready no matter the outcome recorded here.",
            "ta": "இங்கே பதிவான முடிவு எதுவாக இருந்தாலும், candidate எப்போதும் not_public_chat_ready ஆகவே இருக்கும்.",
        },
    ),
    PageEntry(
        page_id="data_help",
        nav_key="Data Help",
        group="Data",
        implemented=True,
        mode="guide",
        title={"en": "Help & Guide", "ta": "உதவி வழிகாட்டி"},
        purpose={
            "en": "The existing, page-by-page bilingual (English/Tamil) contextual help registry for every Data Studio page -- purpose, prerequisites, workflow steps, common issues, and safety notes.",
            "ta": "ஒவ்வொரு Data Studio பக்கத்திற்கும் ஏற்கனவே உள்ள, பக்கம்-வாரியான இருமொழி (ஆங்கிலம்/தமிழ்) contextual help registry -- purpose, prerequisites, workflow steps, common issues, safety notes.",
        },
        related_page_ids=("data_overview",),
        safety_note={"en": "Read-only.", "ta": "படிக்க மட்டுமே."},
    ),
    PageEntry(
        page_id="tokenizer",
        nav_key="Tokenizer",
        group=None,
        implemented=True,
        mode="model",
        title={"en": "Tokenizer", "ta": "Tokenizer"},
        purpose={
            "en": "Manage tokenizer families and versions, train a tokenizer against a dataset version, test it in a lab, and view/change which assignment (scope) currently uses which tokenizer version.",
            "ta": "Tokenizer families மற்றும் versions-ஐ நிர்வகிக்கவும், ஒரு dataset version-க்கு எதிராக tokenizer train செய்யவும், lab-இல் சோதிக்கவும், எந்த assignment (scope) எந்த tokenizer version-ஐ பயன்படுத்துகிறது எனப் பார்க்கவும்/மாற்றவும்.",
        },
        tabs=("Overview", "Families", "Versions", "Training", "Test Lab", "Assignments"),
        related_page_ids=("core_model", "pretraining_readiness"),
        safety_note={
            "en": "Changing an assignment here changes what a runtime scope uses next -- it never affects a scope mid-request.",
            "ta": "இங்கு ஒரு assignment-ஐ மாற்றுவது அந்த runtime scope அடுத்து எதைப் பயன்படுத்தும் என்பதை மாற்றும் -- ஒரு request நடுவில் இதை பாதிக்காது.",
        },
    ),
    PageEntry(
        page_id="core_model",
        nav_key="Core Model",
        group=None,
        implemented=True,
        mode="model",
        title={"en": "Core Model", "ta": "Core Model"},
        purpose={
            "en": "Define model families and architecture configurations, create versions, run architecture/parameter-count checks and a bounded smoke test, manage checkpoints, and view assignments.",
            "ta": "Model families மற்றும் architecture configurations-ஐ define செய்யவும், versions உருவாக்கவும், architecture/parameter-count checks மற்றும் ஒரு bounded smoke test இயக்கவும், checkpoints நிர்வகிக்கவும், assignments பார்க்கவும்.",
        },
        tabs=("Overview", "Families", "Configurations", "Versions", "Architecture Checks", "Smoke Test", "Checkpoints", "Assignments"),
        related_page_ids=("tokenizer", "training"),
        safety_note={
            "en": "A smoke test here is a bounded correctness check, never a real training run.",
            "ta": "இங்கு smoke test ஒரு bounded correctness check மட்டுமே, ஒருபோதும் உண்மையான training run அல்ல.",
        },
    ),
    PageEntry(
        page_id="training",
        nav_key="Training",
        group=None,
        implemented=True,
        mode="model",
        title={"en": "Training", "ta": "Training"},
        purpose={
            "en": "Run and monitor core-model pretraining jobs: worker status, stale-job recovery, per-job metrics/checkpoints/dataset-coverage/streams, quality assessment, checkpoint retention, and event history.",
            "ta": "Core-model pretraining jobs-ஐ இயக்கி கண்காணிக்கவும்: worker status, stale-job recovery, per-job metrics/checkpoints/dataset-coverage/streams, quality assessment, checkpoint retention, event history.",
        },
        related_page_ids=("base_training", "core_model", "pretraining_readiness"),
        safety_note={
            "en": "Starting or recovering a job here is always an explicit, separate action -- never triggered by another page's build/handoff.",
            "ta": "இங்கு ஒரு job-ஐ தொடங்குவது அல்லது recover செய்வது எப்போதும் ஒரு வெளிப்படையான, தனி செயல் -- வேறு பக்கத்தின் build/handoff இதைத் தூண்டாது.",
        },
    ),
    PageEntry(
        page_id="base_training",
        nav_key="Base Training",
        group=None,
        implemented=True,
        mode="model",
        title={"en": "Base Training", "ta": "Base Training"},
        purpose={
            "en": "Design and run base-training experiments on top of a pretrained checkpoint: queue runs, compare runs, evaluate against language metrics and the tokenizer, verify manifests, and select a candidate.",
            "ta": "ஒரு pretrained checkpoint மீது base-training experiments வடிவமைத்து இயக்கவும்: runs queue செய்யவும், runs ஒப்பிடவும், language metrics மற்றும் tokenizer-க்கு எதிராக evaluate செய்யவும், manifests verify செய்யவும், ஒரு candidate தேர்வு செய்யவும்.",
        },
        related_page_ids=("training", "instruction_tuning"),
        safety_note={
            "en": "Selecting a candidate here only marks it selected -- it does not itself publish or release a model.",
            "ta": "இங்கு ஒரு candidate தேர்வு செய்வது அதை selected எனக் குறிக்கும் மட்டுமே -- இது model-ஐ தானாக publish அல்லது release செய்யாது.",
        },
    ),
    PageEntry(
        page_id="instruction_tuning",
        nav_key="Instruction Tuning",
        group=None,
        implemented=True,
        mode="model",
        title={"en": "Instruction Tuning", "ta": "Instruction Tuning"},
        purpose={
            "en": "Profile the instruction-tuning dataset, manage prompt templates, run/monitor training, review training metrics and language evaluation, run diagnostics and leakage checks, and select a reproducible candidate.",
            "ta": "Instruction-tuning dataset-ஐ profile செய்யவும், prompt templates நிர்வகிக்கவும், training இயக்கி கண்காணிக்கவும், training metrics மற்றும் language evaluation review செய்யவும், diagnostics மற்றும் leakage checks இயக்கவும், ஒரு reproducible candidate தேர்வு செய்யவும்.",
        },
        tabs=("Overview", "Dataset Profile", "Templates", "Runs", "Training Metrics", "Language Evaluation", "Diagnostic Lab", "Leakage Checks", "Candidate Selection", "Reproducibility"),
        related_page_ids=("base_training", "model_registry"),
        safety_note={
            "en": "Leakage checks here isolate evaluation-target records structurally, not just by policy.",
            "ta": "இங்கு leakage checks evaluation-target records-ஐ structural ஆகவே தனிமைப்படுத்தும், policy மூலம் மட்டுமல்ல.",
        },
    ),
    PageEntry(
        page_id="model_registry",
        nav_key="Model Registry",
        group=None,
        implemented=True,
        mode="model",
        title={"en": "Model Registry", "ta": "Model Registry"},
        purpose={
            "en": "The release-candidate system of record: release families, candidates, artifact inventory, public/commercial eligibility, model cards, manifests, approvals, releases, comparisons, bundles, and rollback.",
            "ta": "Release-candidate system of record: release families, candidates, artifact inventory, public/commercial eligibility, model cards, manifests, approvals, releases, comparisons, bundles, rollback.",
        },
        tabs=("Overview", "Release Families", "Candidates", "Artifact Inventory", "Eligibility", "Model Cards", "Manifests", "Approvals", "Releases", "Comparisons", "Bundles", "Rollback"),
        related_page_ids=("instruction_tuning", "inference_runtime"),
        safety_note={
            "en": "Approving or releasing a candidate here is always an explicit action gated on eligibility -- never automatic on a build/handoff elsewhere.",
            "ta": "இங்கு ஒரு candidate-ஐ approve அல்லது release செய்வது எப்போதும் eligibility-இல் gate செய்யப்பட்ட ஒரு வெளிப்படையான செயல் -- வேறு எங்கும் build/handoff-இல் தானாக நடக்காது.",
        },
    ),
    PageEntry(
        page_id="inference_runtime",
        nav_key="Inference Runtime",
        group=None,
        implemented=True,
        mode="model",
        title={"en": "Inference Runtime", "ta": "Inference Runtime"},
        purpose={
            "en": "Runtime profiles/instances, compatibility checks, scope assignments and assignment versions, admin diagnostic/chat-lab scopes, canary rollout, health, usage/failure stats, rollback, and the runtime manifest.",
            "ta": "Runtime profiles/instances, compatibility checks, scope assignments, admin diagnostic/chat-lab scopes, canary rollout, health, usage/failure stats, rollback, runtime manifest.",
        },
        tabs=("Overview", "Runtime Profiles", "Runtime Instances", "Compatibility", "Assignments", "Assignment Versions", "Admin Diagnostic", "Admin Chat Lab", "Canary", "Health", "Usage and Failures", "Rollback", "Runtime Manifest"),
        related_page_ids=("model_registry", "conversation_memory"),
        safety_note={
            "en": "Reassigning a scope here (e.g. public_chat) is a controlled, auditable routing change -- never done implicitly by another workflow.",
            "ta": "இங்கு ஒரு scope-ஐ (எ.கா. public_chat) மாற்றுவது ஒரு கட்டுப்படுத்தப்பட்ட, audit செய்யப்படும் routing மாற்றம் -- வேறு எந்த workflow-உம் மறைமுகமாக இதைச் செய்யாது.",
        },
    ),
    PageEntry(
        page_id="production_readiness",
        nav_key="Production Readiness",
        group=None,
        implemented=True,
        mode="governance",
        title={"en": "Production Readiness", "ta": "Production Readiness"},
        purpose={
            "en": "A governance layer over the existing RAG and model-release infrastructure -- production RAG promotion and model release are separate workflows, each with its own build/validation, its own Admin approval, and its own activation; this page never bypasses an earlier approval and never silently activates production. Covers: RAG promotion requests and eligibility, RAG release candidates (build/validate/activate/rollback), model release requests and canary/activation/rollback, an independent artifact-security re-check, API-abuse and secret-scan readiness, backup/restore readiness and backup-encryption assessment/encryption/isolated encrypted-restore verification, the canonical regression manifest and its runs, deployment readiness and system health, and the final readiness report with Admin acceptance.",
            "ta": "ஏற்கனவே உள்ள RAG மற்றும் model-release infrastructure-க்கு மேலான ஒரு governance layer -- production RAG promotion மற்றும் model release தனித்தனி workflows, ஒவ்வொன்றும் தன் own build/validation, own Admin approval, own activation-உடன்; இந்த பக்கம் ஒரு முந்தைய approval-ஐ ஒருபோதும் தவிர்க்காது, production-ஐ ஒருபோதும் மறைமுகமாக activate செய்யாது. உள்ளடக்கம்: RAG promotion requests/eligibility, RAG release candidates (build/validate/activate/rollback), model release requests மற்றும் canary/activation/rollback, ஒரு independent artifact-security re-check, API-abuse மற்றும் secret-scan readiness, backup/restore readiness மற்றும் backup-encryption assessment/encryption/isolated encrypted-restore verification, canonical regression manifest மற்றும் அதன் runs, deployment readiness மற்றும் system health, இறுதி readiness report மற்றும் Admin acceptance.",
        },
        tabs=("Overview", "RAG Promotion", "RAG Candidates", "Model Release", "Canary & Activation", "Artifact Security", "API Abuse & Secrets", "Backup & Deployment", "Regression", "Readiness Report & Acceptance"),
        related_page_ids=("model_registry", "inference_runtime", "knowledge_rag"),
        safety_note={
            "en": "Activation always requires an already-approved release request/candidate, an already-approved assignment, and (for model activation) a verified rollback plan -- rollback readiness is checked before activation, never assembled after the fact. Backup encryption keys are never exposed through this page, any API response, logs, audit metadata, or reports -- only the environment-variable name holding the key is ever shown.",
            "ta": "Activation எப்போதும் ஏற்கனவே approve செய்யப்பட்ட release request/candidate, ஏற்கனவே approve செய்யப்பட்ட assignment, (model activation-க்கு) ஒரு verify செய்யப்பட்ட rollback plan ஆகியவற்றைத் தேவைப்படும் -- rollback readiness activation-க்கு முன்பே check செய்யப்படும், பின்னர் அல்ல. Backup encryption keys இந்த பக்கம், எந்த API response, logs, audit metadata, அல்லது reports வழியாகவும் ஒருபோதும் வெளிப்படாது -- key-ஐ வைத்திருக்கும் environment-variable பெயர் மட்டுமே எப்போதும் காட்டப்படும்.",
        },
    ),
    PageEntry(
        page_id="knowledge_routing",
        nav_key="Knowledge Routing",
        group=None,
        implemented=True,
        mode="governance",
        title={"en": "Knowledge Routing", "ta": "Knowledge Routing"},
        purpose={
            "en": "A deterministic, CPU-first classification and routing-policy layer for public-chat questions, RAG records, dataset candidates, evaluation prompts, and future knowledge-gap cases -- it classifies language, intent, knowledge domain/subdomain, freshness, evidence requirement, an execution-route recommendation (core_model/approved_rag/trusted_web/tool/memory/clarify/refuse/insufficient), and a separate learning-target recommendation (core_model/rag_only/web_preferred/tool_required/evaluation_only/future_training_candidate/do_not_learn/blocked). It never calls the model, RAG, web, a tool, or memory, and it never changes `/api/chat` -- every result is a recommendation only.",
            "ta": "Public-chat questions, RAG records, dataset candidates, evaluation prompts, எதிர்கால knowledge-gap cases-க்கான ஒரு deterministic, CPU-first classification மற்றும் routing-policy layer -- இது language, intent, knowledge domain/subdomain, freshness, evidence requirement, ஒரு execution-route recommendation (core_model/approved_rag/trusted_web/tool/memory/clarify/refuse/insufficient), தனியான ஒரு learning-target recommendation (core_model/rag_only/web_preferred/tool_required/evaluation_only/future_training_candidate/do_not_learn/blocked) ஆகியவற்றை classify செய்யும். இது model, RAG, web, tool, memory ஆகியவற்றை ஒருபோதும் அழைக்காது, `/api/chat`-ஐ ஒருபோதும் மாற்றாது -- ஒவ்வொரு முடிவும் ஒரு recommendation மட்டுமே.",
        },
        tabs=("Overview", "Try Classifier", "Structured Record", "Recent Decisions", "Reason Codes", "Policy"),
        related_page_ids=("production_readiness", "knowledge_rag", "conversation_memory"),
        safety_note={
            "en": "Recommendation only -- no route was executed. No raw question text is stored, only a SHA-256 input hash plus the structured classification outputs.",
            "ta": "Recommendation மட்டுமே -- எந்த route-உம் execute செய்யப்படவில்லை. மூல கேள்வி text சேமிக்கப்படாது, SHA-256 input hash மற்றும் structured classification outputs மட்டுமே சேமிக்கப்படும்.",
        },
    ),
    PageEntry(
        page_id="public_chat_routing",
        nav_key="Public Chat Routing",
        group=None,
        implemented=True,
        mode="governance",
        title={"en": "Public Chat Routing", "ta": "Public Chat Routing"},
        purpose={
            "en": "Diagnostics for the real public Smart Answer Router at `POST /api/chat`, which resolves every public request to exactly one of core_model/approved_rag/memory/clarify/refuse/insufficient -- Trusted Web and Tool are recognized-but-unavailable, honestly reported rather than silently substituted with a stale model answer or an approximated calculation. Covers overview metrics, route events, per-route views (Model/RAG/Memory/Clarifications/Unavailable), safety status, and Tanglish-output-compliance.",
            "ta": "`POST /api/chat`-இல் உள்ள உண்மையான public Smart Answer Router-க்கான diagnostics -- இது ஒவ்வொரு public request-ஐயும் core_model/approved_rag/memory/clarify/refuse/insufficient-இல் ஒன்றாக மட்டுமே resolve செய்யும் -- Trusted Web மற்றும் Tool recognized-but-unavailable ஆக, ஒரு stale model answer அல்லது approximated calculation-ஆல் மறைமுகமாக மாற்றப்படாமல் நேர்மையாக தெரிவிக்கப்படும். Overview metrics, route events, per-route views (Model/RAG/Memory/Clarifications/Unavailable), safety status, Tanglish-output-compliance ஆகியவற்றை உள்ளடக்கியது.",
        },
        tabs=("Overview", "Route Events", "Model Route", "RAG Route", "Memory Route", "Clarifications", "Safety", "Unavailable Routes", "Language Compliance", "Errors"),
        related_page_ids=("knowledge_routing", "knowledge_gaps", "conversation_memory"),
        safety_note={
            "en": "Operational metadata only -- no raw public question or answer text is ever stored or shown here.",
            "ta": "Operational metadata மட்டுமே -- மூல public question அல்லது answer text ஒருபோதும் இங்கு சேமிக்கப்படாது, காட்டப்படாது.",
        },
    ),
    PageEntry(
        page_id="knowledge_gaps",
        nav_key="Knowledge Gaps",
        group=None,
        implemented=True,
        mode="governance",
        title={"en": "Knowledge Gaps", "ta": "Knowledge Gaps"},
        purpose={
            "en": "A privacy-conscious registry of unresolved public-chat cases -- factual knowledge gaps, Web/Tool capability gaps, language failures, and operational incidents -- kept structurally separate from safety refusals and normal clarifications. Covers case capture/classification, conservative duplicate clustering, explainable priority scoring (including a scoped Tamil-first boost), human review, research notes, resolution tracking, advisory RAG-research/training-assessment eligibility flags, daily reports, and governed deletion. No case may directly enter production RAG or training -- every downstream action remains a separate, human-controlled workflow.",
            "ta": "Unresolved public-chat cases-க்கான ஒரு privacy-conscious registry -- factual knowledge gaps, Web/Tool capability gaps, language failures, operational incidents -- safety refusals மற்றும் normal clarifications-இலிருந்து structural-ஆக தனியாக வைக்கப்பட்டவை. Case capture/classification, conservative duplicate clustering, explainable priority scoring (scoped Tamil-first boost உட்பட), human review, research notes, resolution tracking, advisory RAG-research/training-assessment eligibility flags, daily reports, governed deletion ஆகியவற்றை உள்ளடக்கியது. எந்த case-உம் production RAG அல்லது training-க்குள் நேரடியாக நுழையாது -- ஒவ்வொரு பிற்கால செயலும் தனியான, human-controlled workflow-ஆகவே உள்ளது.",
        },
        tabs=("Overview", "New Cases", "Priority Queue", "Clusters", "Tamil Gaps", "RAG Gaps", "Web Demand", "Tool Demand", "Language Failures", "Operational Failures", "RAG Handoff", "Training Assessment", "Daily Report", "Deletion & History"),
        related_page_ids=("public_chat_routing", "knowledge_routing", "knowledge_rag"),
        safety_note={
            "en": "No raw user question or answer text is ever stored -- only a SHA-256 input hash and a privacy-redacted canonical question. RAG-research and training-assessment eligibility flags here are advisory only; no RAG source, RAG trial, training dataset, or training run is ever created from this page.",
            "ta": "மூல user question அல்லது answer text ஒருபோதும் சேமிக்கப்படாது -- SHA-256 input hash மற்றும் privacy-redacted canonical question மட்டுமே. இங்குள்ள RAG-research மற்றும் training-assessment eligibility flags advisory மட்டுமே; இந்த பக்கத்திலிருந்து எந்த RAG source, RAG trial, training dataset, அல்லது training run-உம் ஒருபோதும் உருவாக்கப்படாது.",
        },
    ),
    PageEntry(
        page_id="trusted_web",
        nav_key="Trusted Web",
        group=None,
        implemented=True,
        mode="governance",
        title={"en": "Trusted Web", "ta": "Trusted Web"},
        purpose={
            "en": "Phase 20's live, source-verified Web search gateway for public chat -- makes Phase 17's `trusted_web` recommendation genuinely executable through a bounded pipeline (search -> policy -> provider -> candidate filtering -> source trust evaluation -> optional safe fetch -> content extraction -> injection filtering -> freshness evaluation -> evidence selection -> conflict detection -> grounded answer -> citation). A search result is never treated as trusted evidence by itself, and a Web-search failure never falls back to stale model knowledge. Covers provider health/demand, the versioned checksummed source-trust policy, search/evidence/fetch event history, freshness and source-conflict visibility, and injection-block visibility.",
            "ta": "Public chat-க்கான Phase 20-இன் நேரடி, source-verified Web search gateway -- Phase 17-இன் `trusted_web` recommendation-ஐ ஒரு bounded pipeline (search -> policy -> provider -> candidate filtering -> source trust evaluation -> optional safe fetch -> content extraction -> injection filtering -> freshness evaluation -> evidence selection -> conflict detection -> grounded answer -> citation) மூலம் உண்மையாக executable ஆக்குகிறது. ஒரு search result தானாகவே trusted evidence ஆக ஒருபோதும் கருதப்படாது, Web-search தோல்வி ஒருபோதும் stale model knowledge-க்கு திரும்பாது. Provider health/demand, versioned checksummed source-trust policy, search/evidence/fetch event history, freshness மற்றும் source-conflict visibility, injection-block visibility ஆகியவற்றை உள்ளடக்கியது.",
        },
        tabs=("Overview", "Demand", "Providers", "Policy", "Search Events", "Sources", "Freshness", "Conflicts", "Injection Blocks", "Health"),
        related_page_ids=("knowledge_gaps", "public_chat_routing", "deterministic_tools"),
        safety_note={
            "en": "Fetched Web content is always treated as untrusted input -- prompt-injection attempts in fetched pages are filtered and excluded, never followed. No provider API key, raw fetched page body, or private cache path is ever exposed through this page or its API. No case here automatically enters production RAG or training.",
            "ta": "Fetch செய்யப்பட்ட Web content எப்போதும் untrusted input ஆகவே கருதப்படும் -- fetch செய்யப்பட்ட பக்கங்களில் உள்ள prompt-injection முயற்சிகள் filter செய்யப்பட்டு விலக்கப்படும், ஒருபோதும் பின்பற்றப்படாது. எந்த provider API key, raw fetched page body, அல்லது private cache path-உம் இந்த பக்கம் அல்லது அதன் API வழியாக ஒருபோதும் வெளிப்படாது. இங்குள்ள எந்த case-உம் production RAG அல்லது training-க்குள் தானாக நுழையாது.",
        },
    ),
    PageEntry(
        page_id="deterministic_tools",
        nav_key="Deterministic Tools",
        group=None,
        implemented=True,
        mode="governance",
        title={"en": "Deterministic Tools", "ta": "Deterministic Tools"},
        purpose={
            "en": "Phase 20's sandboxed deterministic tool gateway -- makes Phase 17's `tool` recommendation genuinely executable for exactly three public-enabled tools (calculator, unit conversion, date/time arithmetic), each schema-validated and deterministic. The model never performs the calculation and never alters the tool's structured result; only the surrounding reply text is templated. Covers the closed tool registry, execution-event history, permission tiers, and MCP-readiness status.",
            "ta": "Phase 20-இன் sandboxed deterministic tool gateway -- Phase 17-இன் `tool` recommendation-ஐ சரியாக மூன்று public-enabled tools-க்கு (calculator, unit conversion, date/time arithmetic) உண்மையாக executable ஆக்குகிறது, ஒவ்வொன்றும் schema-validated மற்றும் deterministic. Model ஒருபோதும் கணக்கீட்டைச் செய்யாது, tool-இன் structured result-ஐ ஒருபோதும் மாற்றாது; சுற்றியுள்ள reply text மட்டுமே templated. Closed tool registry, execution-event history, permission tiers, MCP-readiness status ஆகியவற்றை உள்ளடக்கியது.",
        },
        tabs=("Overview", "Registry", "Calculator", "Unit Conversion", "Date Arithmetic", "Execution Events", "Errors", "Permissions", "MCP Readiness"),
        related_page_ids=("trusted_web", "public_chat_routing", "knowledge_gaps"),
        safety_note={
            "en": "No arbitrary tool name is ever accepted -- only the three fixed, hand-written registry entries can execute. External MCP execution is disabled by default and cannot be enabled through this page or its API; only an internal, non-executing MCP-ready contract exists.",
            "ta": "எந்த arbitrary tool name-உம் ஒருபோதும் ஏற்கப்படாது -- நிலையான, hand-written registry-இல் உள்ள மூன்று entries மட்டுமே execute செய்ய முடியும். External MCP execution இயல்பாகவே disabled, இந்த பக்கம் அல்லது அதன் API வழியாக enable செய்ய முடியாது; ஒரு internal, non-executing MCP-ready contract மட்டுமே உள்ளது.",
        },
    ),
    PageEntry(
        page_id="conversation_memory",
        nav_key="Conversation & Memory",
        group=None,
        implemented=True,
        mode="rag",
        title={"en": "Conversation & Memory", "ta": "Conversation & Memory"},
        purpose={
            "en": "Memory policies, sessions and their turns, summaries, consent, memory items and versions, retrieval, context orchestration, a grounded-conversation lab, privacy/deletion, and evaluation.",
            "ta": "Memory policies, sessions மற்றும் அவற்றின் turns, summaries, consent, memory items/versions, retrieval, context orchestration, grounded-conversation lab, privacy/deletion, evaluation.",
        },
        tabs=("Overview", "Memory Policies", "Sessions", "Session Turns", "Summaries", "Consent", "Memory Items", "Memory Versions", "Memory Retrieval", "Context Orchestration", "Grounded Conversation Lab", "Privacy & Deletion", "Evaluation", "Reproducibility"),
        related_page_ids=("knowledge_rag", "inference_runtime"),
        safety_note={
            "en": "Privacy & Deletion actions here are real and irreversible -- always previewed before confirming.",
            "ta": "இங்கு Privacy & Deletion செயல்கள் உண்மையானவை, மீளமுடியாதவை -- confirm செய்வதற்கு முன் எப்போதும் preview செய்யப்படும்.",
        },
    ),
    PageEntry(
        page_id="feedback_improvement",
        nav_key="Feedback & Improvement",
        group=None,
        implemented=True,
        mode="model",
        title={"en": "Feedback & Improvement", "ta": "Feedback & Improvement"},
        purpose={
            "en": "The feedback-to-dataset loop: feedback policies/events, classification, review queues, human reviews, corrected responses, privacy/safety, dataset candidates and their quality/approvals, regression suites/runs, model comparisons, and improvement reports.",
            "ta": "Feedback-to-dataset loop: feedback policies/events, classification, review queues, human reviews, corrected responses, privacy/safety, dataset candidates மற்றும் அவற்றின் quality/approvals, regression suites/runs, model comparisons, improvement reports.",
        },
        tabs=("Overview", "Feedback Policies", "Feedback Events", "Classification", "Review Queues", "Human Reviews", "Corrected Responses", "Privacy & Safety", "Dataset Candidates", "Candidate Quality", "Candidate Approvals", "Regression Suites", "Regression Runs", "Model Comparisons", "Improvement Reports", "Reproducibility"),
        related_page_ids=("datasets", "model_registry"),
        safety_note={
            "en": "A dataset candidate created here still goes through the same approval gates as any other record -- feedback never writes directly into a dataset version.",
            "ta": "இங்கு உருவாக்கப்படும் ஒரு dataset candidate மற்ற எந்த record-ஐயும் போலவே அதே approval gates வழியாக செல்லும் -- feedback ஒருபோதும் ஒரு dataset version-இல் நேரடியாக எழுதாது.",
        },
    ),
    PageEntry(
        page_id="chat_testing",
        nav_key="Chat Testing",
        group=None,
        implemented=False,
        mode="guide",
        title={"en": "Chat Testing", "ta": "Chat Testing"},
        purpose={
            "en": "Not yet implemented -- currently a placeholder page ('This module will be implemented in a future phase.').",
            "ta": "இன்னும் செயல்படுத்தப்படவில்லை -- தற்போது ஒரு placeholder பக்கம் ('This module will be implemented in a future phase.').",
        },
        related_page_ids=("inference_runtime",),
    ),
    PageEntry(
        page_id="admin_assistant",
        nav_key="Admin Assistant",
        group=None,
        implemented=True,
        mode="governance",
        title={"en": "Admin Assistant", "ta": "Admin Assistant"},
        purpose={
            "en": "The existing, full-page, form-based Admin Assistant: read-only dashboard guidance, a manual action-proposal form, and the Proposals & Admin Review queue -- the same underlying proposals the floating assistant now also surfaces. A per-admin 'Reply language' selector (Tamil/English/Tanglish/Auto) controls the language of every Assistant reply, on both this page and the floating widget -- one saved preference, never two competing copies. Auto detects each message's language and replies in kind; a saved Tamil/English/Tanglish choice always overrides that detection. Technical identifiers (IDs, enum values, paths, URLs) are never translated in any mode. Example Tanglish reply: 'Indha dataset innum training-ku ready illa.'",
            "ta": "ஏற்கனவே உள்ள, முழு பக்க, form-அடிப்படையிலான Admin Assistant: read-only dashboard guidance, ஒரு கைமுறை action-proposal form, Proposals & Admin Review queue -- floating assistant இப்போது காட்டும் அதே proposals. ஒரு per-admin 'Reply language' selector (தமிழ்/English/Tanglish/Auto) இந்த பக்கத்திலும் floating widget-இலும் ஒவ்வொரு Assistant பதிலின் மொழியையும் கட்டுப்படுத்தும் -- ஒரே சேமிக்கப்பட்ட விருப்பம், ஒருபோதும் இரண்டு போட்டியிடும் நகல்கள் அல்ல. Auto ஒவ்வொரு message-இன் மொழியையும் கண்டறிந்து அதற்கேற்ப பதிலளிக்கும்; சேமிக்கப்பட்ட தமிழ்/English/Tanglish தேர்வு எப்போதும் அந்த கண்டறிதலை override செய்யும். Technical identifiers (IDs, enum values, paths, URLs) எந்த modeஇலும் ஒருபோதும் translate செய்யப்படாது.",
        },
        tabs=("Guidance", "Propose an Action", "Proposals & Admin Review"),
        related_page_ids=("system",),
        safety_note={
            "en": "A proposal only executes after an explicit Admin Review approval -- never automatically. Changing the reply language never changes what an action does, its risk level, or its audit record -- only the language of the words describing it.",
            "ta": "ஒரு proposal ஒரு வெளிப்படையான Admin Review approval-க்குப் பிறகே execute ஆகும் -- ஒருபோதும் தானாக அல்ல. Reply language-ஐ மாற்றுவது ஒரு action என்ன செய்கிறது, அதன் risk level, அல்லது அதன் audit record-ஐ ஒருபோதும் மாற்றாது -- அதை விவரிக்கும் வார்த்தைகளின் மொழியை மட்டுமே மாற்றும்.",
        },
    ),
    PageEntry(
        page_id="audit_logs",
        nav_key="Audit Logs",
        group=None,
        implemented=False,
        mode="system",
        title={"en": "Audit Logs", "ta": "Audit Logs"},
        purpose={
            "en": "Not yet implemented as its own page -- currently a placeholder; recent audit events are visible today on the System page.",
            "ta": "தனி பக்கமாக இன்னும் செயல்படுத்தப்படவில்லை -- தற்போது ஒரு placeholder; சமீபத்திய audit events System பக்கத்தில் இப்போதே பார்க்கலாம்.",
        },
        related_page_ids=("system",),
    ),
    PageEntry(
        page_id="settings",
        nav_key="Settings",
        group=None,
        implemented=False,
        mode="system",
        title={"en": "Settings", "ta": "Settings"},
        purpose={
            "en": "Not yet implemented -- currently a placeholder page ('This module will be implemented in a future phase.').",
            "ta": "இன்னும் செயல்படுத்தப்படவில்லை -- தற்போது ஒரு placeholder பக்கம் ('This module will be implemented in a future phase.').",
        },
        related_page_ids=("system",),
    ),
    PageEntry(
        page_id="mini_brain",
        nav_key="Brud Mini Brain",
        group=None,
        implemented=True,
        mode="governance",
        title={"en": "Brud Mini Brain", "ta": "Brud Mini Brain"},
        purpose={
            "en": "The consolidated governance console for the Mini Brain phases (dataset intelligence, training pipeline, evaluation, release governance, external AI gateway, training execution engine, public chat runtime feedback loop, and plugin governance/execution) -- every stage requires explicit Admin action to advance and none auto-approves, auto-deploys, or auto-executes an earlier stage's output.",
            "ta": "Mini Brain phases-களுக்கான (dataset intelligence, training pipeline, evaluation, release governance, external AI gateway, training execution engine, public chat runtime feedback loop, plugin governance/execution) ஒருங்கிணைந்த governance console -- ஒவ்வொரு stage-ஐயும் முன்னெடுக்க வெளிப்படையான Admin action தேவை, எந்த stage-உம் ஒரு முந்தைய stage-இன் output-ஐ தானாக approve/deploy/execute செய்யாது.",
        },
        tabs=(
            "Overview", "Settings", "Logs", "Diagnostics", "Knowledge Core", "Intelligence Engine",
            "Runtime", "Response Quality", "Capability", "Dataset Intelligence", "Learning Supervisor",
            "Release Pipeline", "Continuous Learning", "Continuous Learning Center", "Research Center",
            "Dataset Evolution", "Pipeline Coordinator", "Language Intelligence", "Vision Intelligence",
            "Vision Model Center", "Multimodal Dataset Generator", "Vision RAG", "Training Pipeline",
            "Evaluation Center", "Release Governance", "External AI Gateway", "Training Engine",
            "Public Chat Runtime", "Plugin Governance", "Plugin Runtime", "Future Model",
        ),
        related_page_ids=("admin_assistant", "production_readiness"),
        safety_note={
            "en": "Training execution is simulation-only today -- real training backends deliberately raise an unavailable-backend error rather than silently claiming to have trained a model. Plugin execution has no container or process isolation; guards are cooperative, not adversarial.",
            "ta": "Training execution தற்போது simulation-only -- real training backends ஒரு model-ஐ train செய்ததாக மறைமுகமாக claim செய்யாமல், வேண்டுமென்றே unavailable-backend error-ஐ raise செய்யும். Plugin execution-க்கு container அல்லது process isolation கிடையாது; guards cooperative-ஆகவே உள்ளன, adversarial அல்ல.",
        },
    ),
)

PAGE_BY_ID: dict[str, PageEntry] = {page.page_id: page for page in DASHBOARD_PAGES}
PAGE_BY_NAV_KEY: dict[str, PageEntry] = {page.nav_key: page for page in DASHBOARD_PAGES}


def get_page_by_id(page_id: str) -> PageEntry | None:
    return PAGE_BY_ID.get(page_id)


def get_page_by_nav_key(nav_key: str) -> PageEntry | None:
    return PAGE_BY_NAV_KEY.get(nav_key)


# --- Document SFT deep-link / navigation-target registry (Production Closure) ---------------
#
# One entry per real, already-existing Documents/Wizard UI section a caller (the
# frontend's own URL parsing, or the Admin Assistant's navigation_target response
# field) may navigate to. This is deliberately a *separate* registry from
# `PageEntry.tabs` above -- `tabs` is free-text documentation for the Assistant's
# page-help replies, while `DOCUMENT_NAVIGATION_TARGETS` is the actual, validated
# routing contract: every `documents_tab` value here must be a literal tab label
# `DocumentsPage.jsx` renders, and every `wizard_step` must be a real 1-indexed
# position in `DocumentWizardPage.jsx`'s `STEP_DEFINITIONS`. No key here may be
# invented without a matching real UI section -- "history" was considered and
# excluded because no History tab/section exists anywhere in Documents or the
# Wizard.
@dataclass(frozen=True)
class NavigationTarget:
    tab_key: str
    nav_key: str
    documents_tab: str | None = None
    wizard_step: int | None = None
    label: dict[str, str] = field(default_factory=dict)


DOCUMENT_NAVIGATION_TARGETS: tuple[NavigationTarget, ...] = (
    NavigationTarget(
        "overview", "Documents", documents_tab="Overview",
        label={"en": "Open Documents overview", "ta": "Documents கண்ணோட்டத்தைத் திற"},
    ),
    NavigationTarget(
        "pages", "Documents", documents_tab="Processing",
        label={"en": "Open Pages", "ta": "பக்கங்களைத் திற"},
    ),
    NavigationTarget(
        "critical-pages", "Documents", documents_tab="Processing",
        label={"en": "Open Critical Pages", "ta": "முக்கியமான பக்கங்களைத் திற"},
    ),
    NavigationTarget(
        "cleanup", "Documents", documents_tab="Repeated Elements",
        label={"en": "Open Cleanup", "ta": "Cleanup-ஐத் திற"},
    ),
    NavigationTarget(
        "tamil-quality", "Documents", documents_tab="Tamil Quality",
        label={"en": "Open Tamil Quality", "ta": "தமிழ் தரத்தைத் திற"},
    ),
    NavigationTarget(
        "sft-generation", "Documents", documents_tab="SFT Candidates",
        label={"en": "Open SFT Generation", "ta": "SFT Generation-ஐத் திற"},
    ),
    NavigationTarget(
        "sft-candidates", "Documents", documents_tab="SFT Candidates",
        label={"en": "Open Candidate Review", "ta": "Candidate Review-ஐத் திற"},
    ),
    NavigationTarget(
        "export", "Documents", documents_tab="Export",
        label={"en": "Open Export", "ta": "Export-ஐத் திற"},
    ),
    NavigationTarget(
        "media-tables", "Documents", documents_tab="Media & Tables",
        label={"en": "Open Media & Tables", "ta": "Media & Tables-ஐத் திற"},
    ),
    NavigationTarget(
        "security-review", "Documents", documents_tab="Security Review",
        label={"en": "Open Security Review", "ta": "Security Review-ஐத் திற"},
    ),
    NavigationTarget(
        "dataset-handoff", "Document Wizard", wizard_step=11,
        label={"en": "Open Dataset Handoff", "ta": "Dataset Handoff-ஐத் திற"},
    ),
    NavigationTarget(
        "split-preview", "Document Wizard", wizard_step=12,
        label={"en": "Open Split Preview", "ta": "Split Preview-ஐத் திற"},
    ),
    NavigationTarget(
        "dataset-version", "Document Wizard", wizard_step=13,
        label={"en": "Open Dataset Version build", "ta": "Dataset Version build-ஐத் திற"},
    ),
    NavigationTarget(
        "training-readiness", "Document Wizard", wizard_step=14,
        label={"en": "Open Training Readiness", "ta": "Training Readiness-ஐத் திற"},
    ),
    NavigationTarget(
        "chunks", "Chunk & Record Studio",
        label={"en": "Open Chunk & Record Studio", "ta": "Chunk & Record Studio-ஐத் திற"},
    ),
    NavigationTarget(
        "assistant", "Admin Assistant",
        label={"en": "Open Admin Assistant", "ta": "Admin Assistant-ஐத் திற"},
    ),
)

NAVIGATION_TARGET_BY_KEY: dict[str, NavigationTarget] = {
    target.tab_key: target for target in DOCUMENT_NAVIGATION_TARGETS
}


def resolve_document_navigation(
    tab_key: str, document_public_id: str | None = None
) -> dict[str, object] | None:
    """Validates `tab_key` against the registered, real navigation targets and
    returns a safe navigation payload -- or `None` if the key is unknown, which
    every caller must treat as "fall back to a safe default", never as a
    fabricated route. `document_public_id` is passed through as-is (the caller
    is responsible for having already validated it against a real document --
    this function never queries the database)."""

    target = NAVIGATION_TARGET_BY_KEY.get(tab_key)
    if target is None:
        return None
    payload: dict[str, object] = {
        "page_id": get_page_by_nav_key(target.nav_key).page_id
        if get_page_by_nav_key(target.nav_key)
        else None,
        "nav_key": target.nav_key,
        "tab_key": target.tab_key,
        "document_public_id": document_public_id,
        "label": target.label,
    }
    if target.documents_tab is not None:
        payload["documents_tab"] = target.documents_tab
    if target.wizard_step is not None:
        payload["wizard_step"] = target.wizard_step
    return payload


def pages_for_mode(mode: str) -> tuple[PageEntry, ...]:
    return tuple(page for page in DASHBOARD_PAGES if page.mode == mode)
