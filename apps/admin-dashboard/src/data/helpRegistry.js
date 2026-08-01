// Contextual help registry for the "Data" section of the Admin Dashboard
// (Phase 1 of the Data Studio upgrade). Each entry documents one existing,
// already-implemented Data submenu page -- this is a foundation, not a
// competing help system, and it never describes functionality that isn't
// real yet (see docs/data_studio/phase1_existing_data_system_audit.md).
//
// Shape:
// {
//   pageId, activeKey, title: {en, ta}, purpose: {en, ta},
//   prerequisites: [{en, ta}], workflowSteps: [{en, ta}],
//   commonIssues: [{en, ta}], nextPageIds: [pageId],
//   safetyNote: {en, ta},
// }

export const dataHelpEntries = [
  {
    pageId: 'data_overview',
    activeKey: 'Data Overview',
    title: { en: 'Data Overview', ta: 'தரவு கண்ணோட்டம்' },
    purpose: {
      en: 'A single read-only snapshot of every data-related area: sources, documents, dataset records, quality, duplicates, versions, corpus builds, RAG knowledge spaces, and pretraining readiness.',
      ta: 'மூலங்கள், ஆவணங்கள், dataset records, தரம், நகல்கள், versions, corpus builds, RAG knowledge spaces, pretraining readiness ஆகிய அனைத்தையும் ஒரே பார்வையில் காட்டும் read-only பக்கம்.',
    },
    prerequisites: [],
    workflowSteps: [
      { en: 'Start here to see what needs attention before opening a specific workspace.', ta: 'ஒரு குறிப்பிட்ட பணியிடத்தை திறப்பதற்கு முன் இங்கிருந்து தொடங்குங்கள்.' },
      { en: 'Use the navigation actions to jump directly to Datasets, Documents, Corpus Builder, or RAG.', ta: 'Datasets, Documents, Corpus Builder, RAG பக்கங்களுக்கு நேரடியாக செல்ல navigation பொத்தான்களை பயன்படுத்துங்கள்.' },
    ],
    commonIssues: [
      { en: '"Not available in the current system" means that one subsystem could not be reached -- it is never a fabricated zero.', ta: '"Not available in the current system" என்றால் அந்த ஒரு பகுதியை அணுக முடியவில்லை என்று அர்த்தம் -- இது ஒருபோதும் கற்பனையான பூஜ்ஜியம் அல்ல.' },
    ],
    nextPageIds: ['datasets', 'documents'],
    safetyNote: {
      en: 'Read-only: this page never creates, approves, or exports anything.',
      ta: 'இந்த பக்கம் படிக்க மட்டுமே -- இது எதையும் உருவாக்காது, approve செய்யாது, export செய்யாது.',
    },
  },
  {
    pageId: 'datasets',
    activeKey: 'Datasets',
    title: { en: 'Datasets', ta: 'Datasets' },
    purpose: {
      en: 'Manage dataset sources and records: create manual sources, add records, run the review queue, assess quality, inspect duplicate conflicts, import files, and build/export dataset versions.',
      ta: 'Dataset sources மற்றும் records-ஐ நிர்வகிக்கவும்: manual sources உருவாக்குதல், records சேர்த்தல், review queue, quality assessment, duplicate conflicts பார்வையிடல், கோப்புகளை import செய்தல், dataset versions உருவாக்கி export செய்தல்.',
    },
    prerequisites: [
      { en: 'An admin session (already required to reach this page).', ta: 'ஒரு admin session (இந்த பக்கத்தை அடைய ஏற்கனவே தேவை).' },
    ],
    workflowSteps: [
      { en: 'Sources tab: register where records come from.', ta: 'Sources tab: records எங்கிருந்து வருகிறது என்பதை பதிவு செய்யவும்.' },
      { en: 'Records tab: create a draft record, or use Imports to bring in a file.', ta: 'Records tab: ஒரு draft record உருவாக்கவும், அல்லது Imports மூலம் ஒரு கோப்பை கொண்டு வரவும்.' },
      { en: 'Review Queue: approve, reject, or request changes on pending_review records.', ta: 'Review Queue: pending_review records-ஐ approve, reject அல்லது request changes செய்யவும்.' },
      { en: 'Quality tab: assess draft records and inspect top issue codes.', ta: 'Quality tab: draft records-ஐ assess செய்து top issue codes-ஐ பார்க்கவும்.' },
      { en: 'Versions tab: create a build preview, run it, then verify or export the resulting version.', ta: 'Versions tab: ஒரு build preview உருவாக்கி, அதை run செய்து, பிறகு verify அல்லது export செய்யவும்.' },
    ],
    commonIssues: [
      { en: 'A record must be submitted (status=pending_review) before it can be reviewed.', ta: 'ஒரு record-ஐ review செய்ய, அது முதலில் submit ஆகி pending_review நிலையில் இருக்க வேண்டும்.' },
      { en: 'A build with require_ready_quality checked will refuse records that failed quality assessment.', ta: 'require_ready_quality தேர்ந்தெடுக்கப்பட்ட build, quality assessment-இல் தோற்ற records-ஐ ஏற்காது.' },
    ],
    nextPageIds: ['manual_data', 'sources_rights', 'documents', 'data_overview'],
    safetyNote: {
      en: 'Imported/uploaded content always lands as a draft record -- nothing is auto-approved.',
      ta: 'Import/upload செய்யப்பட்ட உள்ளடக்கம் எப்போதும் draft record ஆகவே சேமிக்கப்படும் -- எதுவும் தானாக approve ஆகாது.',
    },
  },
  {
    pageId: 'manual_data',
    activeKey: 'Manual Data',
    title: { en: 'Manual Data', ta: 'கைமுறை தரவு' },
    purpose: {
      en: 'A governed staging area for hand-authored Tamil/English/Tanglish language data: spoken examples, conversations, Q&A, instructions, dictionary entries, translations, and knowledge notes -- record shapes the Datasets page has no columns for. Manual data is different from an existing document or a downloaded dataset: nobody else wrote it down first, so it still needs a source declaration (who created it and what rights apply) exactly like anything else entering Brud AI.',
      ta: 'கையால் எழுதப்பட்ட தமிழ்/ஆங்கிலம்/டேங்கிலீஷ் தரவுக்கான ஒரு regulated staging பகுதி: spoken examples, conversations, Q&A, instructions, dictionary entries, translations, knowledge notes -- Datasets பக்கத்தில் இவற்றுக்கு column கிடையாது. கைமுறை தரவு என்பது ஒரு ஆவணம் அல்லது download செய்யப்பட்ட dataset போன்றது அல்ல -- யாரும் முன்பே எழுதி வைக்கவில்லை, அதனால் இதற்கும் ஒரு source declaration (யார் உருவாக்கியது, என்ன உரிமைகள் பொருந்தும்) தேவை.',
    },
    prerequisites: [
      { en: 'A Phase 2 source to link the record to -- reuse an existing human-created source (e.g. "Dhurai -- Spoken Tamil") or create one inline while creating the record.', ta: 'Record-ஐ இணைக்க ஒரு Phase 2 source தேவை -- ஏற்கனவே உள்ள ஒரு human-created source-ஐ (உதா. "Dhurai -- Spoken Tamil") மீண்டும் பயன்படுத்தவும் அல்லது record உருவாக்கும்போதே ஒன்றை உருவாக்கவும்.' },
    ],
    workflowSteps: [
      { en: 'Create Data tab: choose a data type, link a source, fill in only the fields that type needs, and save as a draft -- direct final approval is never offered here.', ta: 'Create Data tab: ஒரு data type தேர்ந்தெடுத்து, ஒரு source இணைத்து, அந்த type-க்கு தேவையான fields மட்டும் நிரப்பி draft ஆக சேமிக்கவும் -- இங்கிருந்து நேரடியாக approve செய்ய முடியாது.' },
      { en: 'Review Queue tab: run the quality & duplicate check, submit a language/translation/factual/domain review, and either request a correction or move it toward approval.', ta: 'Review Queue tab: quality &amp; duplicate check இயக்கவும், language/translation/factual/domain review submit செய்யவும், பிறகு correction கோரவும் அல்லது approval நோக்கி நகர்த்தவும்.' },
      { en: 'Verification Queue tab: for records marked high-risk or fact-dependent, attach a supporting source and record a verification before approval can proceed.', ta: 'Verification Queue tab: high-risk அல்லது fact-dependent எனக் குறிக்கப்பட்ட records-க்கு, approval தொடர ஒரு supporting source இணைத்து verification பதிவு செய்யவும்.' },
      { en: 'Approving a record records exactly which uses (RAG, training, evaluation, commercial, public export, redistribution) were granted -- never one blanket "approved".', ta: 'ஒரு record-ஐ approve செய்யும்போது எந்தெந்த uses (RAG, training, evaluation, commercial, public export, redistribution) அளிக்கப்பட்டன என்பது தனித்தனியாக பதிவாகும் -- ஒரே "approved" கிடையாது.' },
      { en: 'Approved tab: use "Create Dataset Candidate" to explicitly send an approved record into the existing Datasets pipeline -- this never happens automatically.', ta: 'Approved tab: ஒரு approved record-ஐ existing Datasets pipeline-க்கு அனுப்ப "Create Dataset Candidate"-ஐ பயன்படுத்தவும் -- இது தானாக நடக்காது.' },
    ],
    commonIssues: [
      { en: 'Human-created data (e.g. Dhurai\'s own spoken Tamil or Tanglish) still needs a source and a rights declaration -- being hand-typed by an admin is not itself a permission.', ta: 'கைமுறையாக உருவாக்கப்பட்ட தரவுக்கும் (உதா. Dhurai-இன் சொந்த பேச்சுத் தமிழ் அல்லது Tanglish) source மற்றும் rights declaration தேவை -- ஒரு admin தட்டச்சு செய்தது என்பதே அனுமதி அல்ல.' },
      { en: 'AI-assisted or AI-generated drafts (e.g. an AI-drafted Q&A pair) are blocked from every use except internal review until a human explicitly reviews them -- this can never be skipped.', ta: 'AI-assisted அல்லது AI-generated drafts (உதா. AI உருவாக்கிய Q&A) ஒரு human review செய்யும் வரை internal review தவிர வேறு எந்த use-க்கும் தடுக்கப்படும் -- இதை தவிர்க்க முடியாது.' },
      { en: 'A record marked high-risk or time-sensitive (e.g. a government-service procedure or medical information) is blocked from approval until a supporting source is verified -- a well-written sentence does not substitute for verification.', ta: 'high-risk அல்லது time-sensitive எனக் குறிக்கப்பட்ட ஒரு record (உதா. அரசு சேவை நடைமுறை அல்லது மருத்துவ தகவல்) supporting source verify ஆகும் வரை approve செய்ய முடியாது -- நன்றாக எழுதப்பட்ட வாக்கியம் verification-க்கு பதிலாகாது.' },
      { en: 'Editing an already-approved record never overwrites it -- it creates a new draft revision, and the previously approved revision is preserved in the History tab for comparison.', ta: 'ஏற்கனவே approve செய்யப்பட்ட ஒரு record-ஐ edit செய்வது அதை மேலெழுதாது -- ஒரு புதிய draft revision உருவாகும், முந்தைய approved revision History tab-இல் ஒப்பீட்டுக்காக பாதுகாக்கப்படும்.' },
    ],
    nextPageIds: ['sources_rights', 'datasets', 'data_overview'],
    safetyNote: {
      en: 'Every manual record starts as a draft and is never training-ready solely because an admin created it -- approval always records exactly which uses were granted, and every mutation is captured in the record\'s own History tab.',
      ta: 'ஒவ்வொரு கைமுறை record-உம் draft ஆகவே தொடங்கும், ஒரு admin உருவாக்கியது என்பதற்காக மட்டும் training-ready ஆகாது -- approval எப்போதும் எந்தெந்த uses அளிக்கப்பட்டன என்பதை பதிவு செய்யும், ஒவ்வொரு மாற்றமும் அந்த record-இன் History tab-இல் பதிவாகும்.',
    },
  },
  {
    pageId: 'sources_rights',
    activeKey: 'Sources & Rights',
    title: { en: 'Sources & Rights', ta: 'மூலங்களும் உரிமைகளும்' },
    purpose: {
      en: 'A governed registry answering, for every piece of data entering Brud AI: where it came from, who owns it, what license or permission applies, and exactly which uses (RAG, training, evaluation, commercial, public export, redistribution) are allowed -- separately from every other data page, because "where it came from" (a source) and "what you may do with it" (its rights) are two different questions with two different answers.',
      ta: 'Brud AI-ஐ சேரும் ஒவ்வொரு தரவுக்கும்: அது எங்கிருந்து வந்தது, யாருக்கு உரிமை உண்டு, என்ன license/permission பொருந்தும், மற்றும் எந்தெந்த பயன்பாடுகள் (RAG, training, evaluation, commercial, public export, redistribution) அனுமதிக்கப்படுகின்றன என்பதை பதிவு செய்யும் அமைப்பு. "இது எங்கிருந்து வந்தது" (source) என்பதும் "இதை என்ன செய்யலாம்" (rights) என்பதும் வெவ்வேறு கேள்விகள் -- அதனால் இரண்டும் தனித்தனியாக பதிவு செய்யப்படுகின்றன.',
    },
    prerequisites: [],
    workflowSteps: [
      { en: 'Sources tab: register a source with a stable source code (e.g. SRC-HUMAN-DHURAI-0001) and the closest matching source type.', ta: 'Sources tab: ஒரு நிலையான source code (உதா. SRC-HUMAN-DHURAI-0001) மற்றும் பொருத்தமான source type-உடன் ஒரு source-ஐ பதிவு செய்யவும்.' },
      { en: 'Rights Review tab: declare the rights_status and every one of the six per-use permissions explicitly -- there is deliberately no single "approved" checkbox.', ta: 'Rights Review tab: rights_status மற்றும் ஆறு per-use அனுமதிகளையும் தனித்தனியாக declare செய்யவும் -- ஒரே "approved" checkbox வேண்டுமென்றே இல்லை.' },
      { en: 'Submit for review, then have a second admin Verify (document/owner/legal), Restrict, or Reject -- never the same admin rubber-stamping their own declaration silently.', ta: 'Submit for review செய்த பிறகு, இரண்டாவது admin ஒருவர் Verify (document/owner/legal), Restrict, அல்லது Reject செய்ய வேண்டும்.' },
      { en: 'Usage Eligibility tab: check a specific target use, or "all uses at a glance", before relying on this source anywhere.', ta: 'Usage Eligibility tab: எங்காவது இந்த source-ஐ நம்புவதற்கு முன், ஒரு குறிப்பிட்ட பயன்பாட்டையோ அல்லது "all uses at a glance"-ஐயோ சரிபார்க்கவும்.' },
    ],
    commonIssues: [
      { en: 'A source being publicly accessible, government-hosted, old, called "nationalized", or simply having a download URL never by itself implies permission -- none of these are read by the eligibility check at all.', ta: 'ஒரு source பொது அணுகலில் இருப்பது, government hosting, பழமையானது, "nationalized" என்று அழைக்கப்படுவது, அல்லது வெறும் download URL இருப்பது -- இவை எதுவும் தானாக அனுமதியை தராது; eligibility check இவற்றை படிக்கவே இல்லை.' },
      { en: 'Unknown or pending-review rights fail closed for training, commercial use, and public export -- they may only be eligible for internal-only RAG, and only when an explicit policy flag allows it.', ta: 'தெரியாத அல்லது pending rights, training/commercial/public export-க்கு fail-closed ஆகும் -- internal-only RAG-க்கு மட்டுமே தகுதி பெறலாம், அதுவும் ஒரு வெளிப்படையான policy அனுமதித்தால் மட்டுமே.' },
      { en: 'AI-assisted or AI-generated content is blocked from every use except internal RAG until a human reviewer verifies it -- this can never be skipped.', ta: 'AI-assisted அல்லது AI-generated உள்ளடக்கம், ஒரு human reviewer verify செய்யும் வரை internal RAG தவிர வேறு எந்த பயன்பாட்டிற்கும் தடுக்கப்படும் -- இதை தவிர்க்க முடியாது.' },
      { en: 'A rejected or archived source is blocked from every use, and an archived source cannot receive new links until restored.', ta: 'Reject அல்லது archive செய்யப்பட்ட source எல்லா பயன்பாட்டிற்கும் தடுக்கப்படும்; archive செய்யப்பட்ட source, restore செய்யும் வரை புதிய links பெறாது.' },
    ],
    nextPageIds: ['documents', 'corpus_builder', 'knowledge_rag'],
    safetyNote: {
      en: 'Existing records without a source/rights link remain fully readable -- this registry never retroactively marks anything as authorized, and never fabricates a source, owner, or licence it has no evidence for.',
      ta: 'Source/rights link இல்லாத ஏற்கனவே இருக்கும் records முழுமையாக படிக்கக்கூடியதாகவே இருக்கும் -- இந்த அமைப்பு எதையும் பின்னோக்கி authorized ஆக்காது, ஆதாரம் இல்லாத source/owner/licence-ஐ ஒருபோதும் கற்பனை செய்யாது.',
    },
  },
  {
    pageId: 'external_data_providers',
    activeKey: 'External Data Providers',
    title: { en: 'External Data Providers', ta: 'வெளிப்புற தரவு வழங்குநர்கள்' },
    purpose: {
      en: 'A governed registry of external organizations/websites Brud AI could potentially pull training/RAG data from -- separate from Sources & Rights (which records rights for one specific piece of content already inside Brud AI). A provider is "where you might look"; a source is "what you actually brought in and what you may do with it" -- two different questions.',
      ta: 'Brud AI training/RAG தரவை எடுக்கக்கூடிய வெளிப்புற நிறுவனங்கள்/வலைத்தளங்களின் ஒரு regulated registry -- Sources & Rights-இலிருந்து (ஏற்கனவே Brud AI-க்குள் கொண்டு வரப்பட்ட ஒரு குறிப்பிட்ட உள்ளடக்கத்தின் உரிமைகளை பதிவு செய்வது) தனியானது. ஒரு provider என்பது "எங்கு பார்க்கலாம்"; ஒரு source என்பது "எதை உண்மையில் கொண்டு வந்தீர்கள், அதை என்ன செய்யலாம்" -- இரண்டு வெவ்வேறு கேள்விகள்.',
    },
    prerequisites: [],
    workflowSteps: [
      { en: 'Providers tab: browse the 8 built-in templates (AI4Bharat, Hugging Face, GitHub, Wikimedia, Bhashini, and 3 generic templates) or your own custom providers -- every one starts draft/unverified/disabled.', ta: 'Providers tab: 8 built-in templates (AI4Bharat, Hugging Face, GitHub, Wikimedia, Bhashini, 3 generic templates) அல்லது உங்கள் சொந்த custom providers-ஐ பார்க்கவும் -- ஒவ்வொன்றும் draft/unverified/disabled ஆகவே தொடங்கும்.' },
      { en: 'Add Provider tab: register a new provider not covered by a built-in template -- fill in the real name, official website, and access/authentication type.', ta: 'Add Provider tab: built-in template இல்லாத ஒரு புதிய provider-ஐ பதிவு செய்யவும் -- உண்மையான பெயர், official website, access/authentication type-ஐ நிரப்பவும்.' },
      { en: 'Domains tab: register the provider\'s official/api/download domains, then mark each one verified or failed with a written evidence note -- domain ownership is never claimed from a page title alone.', ta: 'Domains tab: provider-இன் official/api/download domains-ஐ பதிவு செய்து, ஒவ்வொன்றையும் ஒரு எழுதப்பட்ட evidence note உடன் verified அல்லது failed எனக் குறிக்கவும் -- domain ownership ஒருபோதும் ஒரு page title-இலிருந்து மட்டும் கருதப்படாது.' },
      { en: 'Providers tab: use "Evaluate verification" to check evidence and (only if a domain is already independently verified) upgrade trust_status to domain_verified -- higher trust tiers require a separate, reasoned admin judgment.', ta: '"Evaluate verification"-ஐ பயன்படுத்தி ஆதாரத்தை சரிபார்க்கவும் -- ஒரு domain ஏற்கனவே தனித்தனியாக verify செய்யப்பட்டிருந்தால் மட்டுமே trust_status domain_verified ஆக உயரும். உயர்ந்த trust tiers-க்கு தனி, காரணத்துடன் கூடிய admin முடிவு தேவை.' },
      { en: 'Connection Tests tab: run a bounded, read-only reachability check before enabling a provider -- this never searches or downloads anything.', ta: 'Connection Tests tab: ஒரு provider-ஐ enable செய்வதற்கு முன் ஒரு bounded, read-only reachability check இயக்கவும் -- இது எதையும் search அல்லது download செய்யாது.' },
      { en: 'Providers tab: Enable a provider only after you are satisfied with its trust/verification -- enabling only permits read-only discovery, never automatic download or training use.', ta: 'Providers tab: trust/verification-இல் திருப்தி அடைந்த பிறகே ஒரு provider-ஐ Enable செய்யவும் -- enable செய்வது read-only discovery-ஐ மட்டுமே அனுமதிக்கும், ஒருபோதும் தானாக download அல்லது training use அல்ல.' },
    ],
    commonIssues: [
      { en: 'Gated/private access requires a credential reference (an environment variable name) -- the actual secret value is configured in the server environment, never typed into or stored by this page.', ta: 'Gated/private access-க்கு ஒரு credential reference (environment variable பெயர்) தேவை -- உண்மையான secret value server environment-இல் கட்டமைக்கப்படும், இந்த பக்கத்தில் ஒருபோதும் தட்டச்சு செய்யப்படாது/சேமிக்கப்படாது.' },
      { en: 'Registering, verifying, or enabling a provider never grants a dataset licence, RAG use, training use, or commercial use by itself -- each piece of content later discovered through it still needs its own Sources & Rights decision.', ta: 'ஒரு provider-ஐ பதிவு, verify, அல்லது enable செய்வது தானாகவே dataset licence, RAG use, training use, அல்லது commercial use-ஐ வழங்காது -- அதன் மூலம் பின்னர் கண்டறியப்படும் ஒவ்வொரு உள்ளடக்கத்திற்கும் அதன் சொந்த Sources & Rights முடிவு தேவை.' },
      { en: 'An unknown provider (never registered here) or an unverified/disabled one is never trusted automatically -- a random admin-pasted URL does not become a trusted provider just by being typed.', ta: 'பதிவு செய்யப்படாத ஒரு provider அல்லது unverified/disabled ஒன்று ஒருபோதும் தானாக நம்பப்படாது -- admin தட்டச்சு செய்த ஒரு URL மட்டும் ஒரு trusted provider ஆகாது.' },
      { en: 'Public/gated/private access modes are declared, not inferred -- a provider claiming "public" access is still checked with a real, bounded connection test before being relied on.', ta: 'Public/gated/private access modes declare செய்யப்படுகின்றன, ஊகிக்கப்படுவதில்லை -- "public" access எனக் கூறும் ஒரு provider-உம் நம்புவதற்கு முன் ஒரு real, bounded connection test மூலம் சரிபார்க்கப்படும்.' },
    ],
    nextPageIds: ['sources_rights', 'data_overview', 'dataset_discovery'],
    safetyNote: {
      en: 'This page never downloads, searches, or compares datasets, and no credential value is ever stored, logged, or returned by any API -- only a reference. Training, RAG use, and commercial use remain blocked regardless of a provider\'s trust or lifecycle status.',
      ta: 'இந்த பக்கம் ஒருபோதும் datasets-ஐ download, search, அல்லது compare செய்யாது, மேலும் எந்த credential value-உம் ஒருபோதும் எந்த API-ஆலும் சேமிக்கப்படாது, log செய்யப்படாது, அல்லது திரும்பத் தரப்படாது -- ஒரு reference மட்டுமே. ஒரு provider-இன் trust அல்லது lifecycle status எதுவாக இருந்தாலும், training, RAG use, commercial use தடுக்கப்பட்டே இருக்கும்.',
    },
  },
  {
    pageId: 'dataset_discovery',
    activeKey: 'Dataset Discovery',
    title: { en: 'Dataset Discovery', ta: 'தரவுத்தொகுப்பு கண்டுபிடிப்பு' },
    purpose: {
      en: 'A governed research workspace: describe a dataset requirement, search enabled external providers, review normalized/deduplicated/scored candidates, compare 2-5 of them, and save the research session -- separate from External Data Providers (which registers where you might look) and from Sources & Rights (which records what you actually brought in and what you may do with it).',
      ta: 'ஒரு regulated ஆராய்ச்சி workspace: dataset தேவையை விவரிக்கவும், enabled external providers-ஐ தேடவும், normalize/deduplicate/score செய்யப்பட்ட candidates-ஐ பார்க்கவும், 2-5 candidates-ஐ ஒப்பிடவும், research session-ஐ சேமிக்கவும் -- External Data Providers (எங்கு பார்க்கலாம் என்பதை பதிவு செய்வது) மற்றும் Sources & Rights (எதை உண்மையில் கொண்டு வந்தீர்கள், அதை என்ன செய்யலாம் என்பதை பதிவு செய்வது) இலிருந்து தனியானது.',
    },
    prerequisites: [
      { en: 'At least one External Data Provider already enabled -- an unenabled provider is never searched.', ta: 'குறைந்தது ஒரு External Data Provider ஏற்கனவே enable செய்யப்பட்டிருக்க வேண்டும் -- enable செய்யப்படாத provider ஒருபோதும் தேடப்படாது.' },
    ],
    workflowSteps: [
      { en: 'Sessions tab: create a new research session and give it a title.', ta: 'Sessions tab: ஒரு புதிய research session உருவாக்கி, அதற்கு ஒரு தலைப்பு கொடுக்கவும்.' },
      { en: 'Requirement tab: describe modality, languages, tasks, intended use, and commercial requirement -- a free-text note becomes the search query when given.', ta: 'Requirement tab: modality, languages, tasks, intended use, commercial requirement-ஐ விவரிக்கவும் -- ஒரு free-text குறிப்பு கொடுக்கப்பட்டால் அதுவே search query ஆகும்.' },
      { en: 'Sessions tab: click "Run search" -- every currently enabled/searchable provider is searched, bounded and best-effort; one provider failing never discards another provider\'s results.', ta: 'Sessions tab: "Run search"-ஐ கிளிக் செய்யவும் -- தற்போது enabled/searchable ஆன ஒவ்வொரு providerம் bounded, best-effort ஆக தேடப்படும்; ஒரு provider தோல்வியடைந்தாலும் மற்ற providers-ன் results இழக்கப்படாது.' },
      { en: 'Candidates tab: review each candidate\'s normalized metadata, explainable per-dimension score, warnings (missing card, unknown licence), and provider source(s); exclude or restore as needed, or add one you already know about manually.', ta: 'Candidates tab: ஒவ்வொரு candidate-இன் normalized metadata, explainable per-dimension score, warnings (missing card, unknown licence), provider source(s)-ஐ பார்க்கவும்; தேவைக்கேற்ப exclude/restore செய்யவும், அல்லது ஏற்கனவே தெரிந்த ஒன்றை கைமுறையாக சேர்க்கவும்.' },
      { en: 'Comparison tab: select 2-5 candidates from the Candidates tab, then create a saved, dimension-by-dimension comparison.', ta: 'Comparison tab: Candidates tab-இலிருந்து 2-5 candidates தேர்ந்தெடுத்து, ஒரு சேமிக்கப்பட்ட, dimension-வாரியான ஒப்பீட்டை உருவாக்கவும்.' },
    ],
    commonIssues: [
      { en: 'A session with zero enabled/searchable providers finishes as "failed" immediately -- enable a provider on the External Data Providers page first.', ta: 'எந்த enabled/searchable provider-உம் இல்லாத ஒரு session உடனடியாக "failed" ஆக முடியும் -- முதலில் External Data Providers பக்கத்தில் ஒரு provider-ஐ enable செய்யவும்.' },
      { en: 'An unknown licence always stays "unknown" and a missing dataset card is always shown as a warning -- neither is ever guessed or hidden.', ta: 'தெரியாத licence எப்போதும் "unknown" ஆகவே இருக்கும், missing dataset card எப்போதும் warning ஆகவே காட்டப்படும் -- இரண்டும் ஒருபோதும் ஊகிக்கப்படாது/மறைக்கப்படாது.' },
      { en: 'A "possible duplicate" flag is never an automatic merge -- both candidates remain visible for a human to decide.', ta: '"Possible duplicate" flag ஒருபோதும் ஒரு automatic merge அல்ல -- ஒரு மனிதர் முடிவெடுக்க இரண்டு candidates-உம் தெரியும்.' },
    ],
    nextPageIds: ['external_data_providers', 'sources_rights', 'data_overview'],
    safetyNote: {
      en: 'This page never downloads a file, imports a dataset, clones a repository, or executes anything from a provider\'s response. No candidate here has a dataset licence, RAG use, training use, evaluation use, or commercial use approved by this workspace -- that always remains a separate Sources & Rights Registry decision.',
      ta: 'இந்த பக்கம் ஒருபோதும் ஒரு கோப்பை download செய்யாது, dataset-ஐ import செய்யாது, ஒரு repository-ஐ clone செய்யாது, அல்லது ஒரு provider-இன் response-இலிருந்து எதையும் execute செய்யாது. இங்குள்ள எந்த candidate-க்கும் dataset licence, RAG use, training use, evaluation use, அல்லது commercial use இந்த workspace-ஆல் approve செய்யப்படாது -- இது எப்போதும் ஒரு தனி Sources & Rights Registry முடிவாகவே இருக்கும்.',
    },
  },
  {
    pageId: 'documents',
    activeKey: 'Documents',
    title: { en: 'Documents', ta: 'ஆவணங்கள்' },
    purpose: {
      en: 'Upload PDFs, link a source/rights record, extract text (embedded or Tamil-English OCR), review and correct each page side-by-side with the original scan, clean up repeated headers/footers, and hand off approved pages to segmentation.',
      ta: 'PDF பதிவேற்றி, ஒரு source/rights பதிவை இணைத்து, உரையைப் பிரித்தெடுத்து (embedded அல்லது தமிழ்-ஆங்கில OCR), ஒவ்வொரு பக்கத்தையும் மூல ஸ்கேனுடன் ஒப்பிட்டு சரிபார்த்து திருத்தி, மீண்டும் வரும் headers/footers-ஐ சுத்தம் செய்து, approved பக்கங்களை segmentation-க்கு அனுப்பவும்.',
    },
    prerequisites: [
      { en: 'A PDF file within the size/page limits shown on the Upload tab.', ta: 'Upload tab-இல் காட்டப்படும் அளவு/பக்க வரம்பிற்குள் இருக்கும் ஒரு PDF கோப்பு.' },
      { en: 'A registered source/rights record (Sources & Rights) to link before any page can be approved.', ta: 'எந்த பக்கத்தையும் approve செய்வதற்கு முன், இணைக்க ஒரு பதிவு செய்யப்பட்ட source/rights பதிவு (Sources & Rights) தேவை.' },
    ],
    workflowSteps: [
      { en: 'Upload tab: choose extraction strategy (automatic, embedded-only, OCR-only, or hybrid) and preferred language.', ta: 'Upload tab: extraction strategy (automatic, embedded-only, OCR-only, hybrid) மற்றும் மொழியை தேர்ந்தெடுக்கவும்.' },
      { en: 'Processing tab: link a source/rights record, analyze pages, then process/extract; watch readiness, review-status counts, and job history.', ta: 'Processing tab: ஒரு source/rights பதிவை இணைத்து, பக்கங்களை analyze செய்து, extract செய்யவும்; readiness, review-status எண்ணிக்கைகள், job history-ஐ கவனிக்கவும்.' },
      { en: 'Page Review tab: compare the original page image against Raw/Corrected/Compare/Metadata text, save corrections (each saved as a new, restorable revision -- the raw extraction is never overwritten), request an OCR or extraction rerun, then Approve, Reject, Exclude, Reopen, or Request Correction.', ta: 'Page Review tab: மூலப் பக்க படத்தை Raw/Corrected/Compare/Metadata உரையுடன் ஒப்பிட்டு, திருத்தங்களை சேமிக்கவும் (ஒவ்வொன்றும் ஒரு புதிய, மீட்டமைக்கக்கூடிய revision ஆக சேமிக்கப்படும் -- raw extraction ஒருபோதும் மேலெழுதப்படாது), OCR அல்லது extraction rerun கோரவும், பிறகு Approve, Reject, Exclude, Reopen, அல்லது Request Correction செய்யவும்.' },
      { en: 'Repeated Elements tab: detect headers/footers/page numbers that repeat across pages and accept, reject, or apply the removal to all matching pages -- nothing is removed until explicitly confirmed.', ta: 'Repeated Elements tab: பக்கங்கள் முழுவதும் மீண்டும் வரும் headers/footers/page numbers-ஐ கண்டறிந்து, accept, reject செய்யவும், அல்லது பொருந்தும் அனைத்து பக்கங்களுக்கும் நீக்கத்தை apply செய்யவும் -- வெளிப்படையாக உறுதிப்படுத்தும் வரை எதுவும் நீக்கப்படாது.' },
      { en: 'Once at least one page is approved and a source is linked, send approved pages to the existing segmentation/candidates workflow from the Processing tab; Candidates tab: generate segmented candidates, edit/select/reject them, then explicitly confirm the draft import.', ta: 'குறைந்தது ஒரு பக்கம் approve செய்யப்பட்டு, ஒரு source இணைக்கப்பட்ட பிறகு, Processing tab-இல் இருந்து approved பக்கங்களை existing segmentation/candidates workflow-க்கு அனுப்பவும்; Candidates tab: பிரிக்கப்பட்ட candidates உருவாக்கி, edit/select/reject செய்து, பிறகு draft import-ஐ உறுதிப்படுத்தவும்.' },
    ],
    commonIssues: [
      { en: 'OCR may be unavailable in some environments -- embedded-text extraction still works.', ta: 'சில சூழல்களில் OCR கிடைக்காமல் போகலாம் -- embedded-text extraction இன்னும் வேலை செய்யும்.' },
      { en: 'A page cannot be approved until the document has a linked source -- link one on the Processing tab first.', ta: 'ஆவணத்திற்கு ஒரு source இணைக்கப்படும் வரை ஒரு பக்கத்தை approve செய்ய முடியாது -- முதலில் Processing tab-இல் ஒன்றை இணைக்கவும்.' },
      { en: 'OCR confidence is only shown when Tesseract actually reports one -- an unavailable score is never invented.', ta: 'Tesseract உண்மையில் ஒரு மதிப்பெண் தெரிவிக்கும் போது மட்டுமே OCR confidence காட்டப்படும் -- கிடைக்காத மதிப்பெண் ஒருபோதும் கற்பனை செய்யப்படாது.' },
      { en: 'Candidate import requires the confirmation checkbox and at least one selected candidate.', ta: 'Candidate import-க்கு confirmation checkbox மற்றும் குறைந்தது ஒரு selected candidate தேவை.' },
    ],
    nextPageIds: ['chunk_studio', 'datasets', 'sources_rights'],
    safetyNote: {
      en: 'Approving a page only records a human review decision on its text -- it never implies dataset, rights, or training approval, and unknown source rights are never treated as permission to train.',
      ta: 'ஒரு பக்கத்தை approve செய்வது அதன் உரையின் மீதான ஒரு human review முடிவை மட்டுமே பதிவு செய்யும் -- இது dataset, rights, அல்லது training approval-ஐ ஒருபோதும் குறிக்காது, தெரியாத source rights ஒருபோதும் train செய்ய அனுமதியாக கருதப்படாது.',
    },
  },
  {
    pageId: 'chunk_studio',
    activeKey: 'Chunk & Record Studio',
    title: { en: 'Chunk & Record Studio', ta: 'Chunk & Record Studio' },
    purpose: {
      en: 'Turn approved PDF pages into typed semantic chunks (headings, paragraphs, definitions, examples, dictionary entries, grammar rules, Q&A, tables...), then build reviewed structured dataset candidates (dictionary, grammar, Q&A, translation, Tanglish, knowledge, RAG) from those chunks -- always preserving exact source page/character lineage.',
      ta: 'Approve செய்யப்பட்ட PDF பக்கங்களை typed semantic chunks ஆக (headings, paragraphs, definitions, examples, dictionary entries, grammar rules, Q&A, tables...) மாற்றி, பிறகு அந்த chunks-இலிருந்து reviewed structured dataset candidates (dictionary, grammar, Q&A, translation, Tanglish, knowledge, RAG) உருவாக்கவும் -- மூலப் பக்கம்/character lineage எப்போதும் சரியாக பாதுகாக்கப்படும்.',
    },
    prerequisites: [
      { en: 'At least one document page already approved in the Documents workspace, with a linked source.', ta: 'Documents workspace-இல் ஏற்கனவே approve செய்யப்பட்ட, ஒரு source இணைக்கப்பட்ட குறைந்தது ஒரு ஆவணப் பக்கம்.' },
    ],
    workflowSteps: [
      { en: 'Documents tab: select a document, then Generate draft chunks -- only approved pages are used; a document with some unapproved pages is clearly labeled partial.', ta: 'Documents tab: ஒரு ஆவணத்தைத் தேர்ந்தெடுத்து, Generate draft chunks செய்யவும் -- approve செய்யப்பட்ட பக்கங்கள் மட்டுமே பயன்படுத்தப்படும்; சில பக்கங்கள் approve செய்யப்படாத ஆவணம் தெளிவாக partial என லேபிள் செய்யப்படும்.' },
      { en: 'Chunk Editor tab: review each chunk\'s text against its own page/character lineage, split a chunk, merge it with a neighbor, move a boundary, or correct its text -- every boundary operation is validated so no source text is ever lost or duplicated.', ta: 'Chunk Editor tab: ஒவ்வொரு chunk-இன் உரையையும் அதன் சொந்த பக்கம்/character lineage-உடன் ஒப்பிட்டு, chunk-ஐ split செய்யவும், அருகில் உள்ளதனுடன் merge செய்யவும், boundary-ஐ நகர்த்தவும், அல்லது உரையை திருத்தவும் -- source உரை ஒருபோதும் இழக்கப்படாமல் அல்லது நகல் செய்யப்படாமல் ஒவ்வொரு boundary செயலும் சரிபார்க்கப்படும்.' },
      { en: 'Structure tab: optionally assign a parent chunk (heading -> paragraph -> example) and adjust reading order -- hierarchy is optional, never required.', ta: 'Structure tab: விரும்பினால் ஒரு parent chunk-ஐ ஒதுக்கவும் (heading -> paragraph -> example) மற்றும் reading order-ஐ மாற்றவும் -- hierarchy விரும்பினால் மட்டுமே, கட்டாயமில்லை.' },
      { en: 'Submit each chunk for review and approve it -- editing an approved chunk always reopens it for re-review rather than silently changing approved content.', ta: 'ஒவ்வொரு chunk-ஐயும் review-க்கு சமர்ப்பித்து approve செய்யவும் -- approve செய்யப்பட்ட ஒரு chunk-ஐ திருத்துவது எப்போதும் அதை மீண்டும் review-க்காக திறக்கும், approve செய்யப்பட்ட உள்ளடக்கத்தை மௌனமாக மாற்றாது.' },
      { en: 'Record Builder tab: choose a structured record type, select one or more reviewed chunks as evidence, and fill in only the fields that type needs -- unsupported fields (a missing definition, translation, or answer) are left empty rather than invented.', ta: 'Record Builder tab: ஒரு structured record வகையைத் தேர்ந்தெடுத்து, evidence ஆக reviewed chunks ஒன்று அல்லது அதற்கு மேற்பட்டவற்றைத் தேர்ந்தெடுத்து, அந்த வகைக்குத் தேவையான fields-ஐ மட்டும் நிரப்பவும் -- ஆதரிக்கப்படாத fields (இல்லாத definition, translation, அல்லது answer) கற்பனை செய்யப்படாமல் காலியாக விடப்படும்.' },
      { en: 'Conflicts tab: check text coverage per page and check a structured record for conflicts (an alternate dictionary sense, a conflicting Q&A answer, an inconsistent translation) before relying on it.', ta: 'Conflicts tab: ஒரு structured record-ஐ நம்புவதற்கு முன், ஒவ்வொரு பக்கத்திற்கும் text coverage-ஐ சரிபார்த்து, அதற்கான conflicts-ஐயும் (மாற்று dictionary sense, முரண்பட்ட Q&A answer, முரண்பட்ட translation) சரிபார்க்கவும்.' },
      { en: 'Approved tab: check usage eligibility per target use (RAG, training, evaluation, ...), then explicitly Export to Existing Dataset Record or mark ready for RAG handoff -- neither happens automatically.', ta: 'Approved tab: ஒவ்வொரு target use-க்கும் (RAG, training, evaluation, ...) usage eligibility-ஐ சரிபார்த்து, பிறகு வெளிப்படையாக Export to Existing Dataset Record செய்யவும் அல்லது RAG handoff-க்கு தயார் எனக் குறிக்கவும் -- இரண்டும் தானாக நடக்காது.' },
    ],
    commonIssues: [
      { en: 'Chunk generation requires at least one approved page and a linked source -- link a source and approve a page in Documents first.', ta: 'Chunk generation-க்கு குறைந்தது ஒரு approve செய்யப்பட்ட பக்கம் மற்றும் ஒரு இணைக்கப்பட்ட source தேவை -- முதலில் Documents-இல் ஒரு source இணைத்து ஒரு பக்கத்தை approve செய்யவும்.' },
      { en: 'Splitting, merging, or moving the boundary of an already-approved chunk is blocked -- request a correction (or edit its text directly) to reopen it first.', ta: 'ஏற்கனவே approve செய்யப்பட்ட ஒரு chunk-இன் split, merge, அல்லது boundary move தடுக்கப்படும் -- முதலில் ஒரு correction கோரவும் (அல்லது நேரடியாக உரையை திருத்தவும்) அதை மீண்டும் திறக்க.' },
      { en: 'A dictionary word or Q&A question matching an existing entry is not automatically treated as a duplicate -- differing meanings/answers are surfaced as a conflict for manual review instead.', ta: 'ஏற்கனவே உள்ள entry-உடன் பொருந்தும் ஒரு dictionary word அல்லது Q&A question தானாக duplicate எனக் கருதப்படாது -- வேறுபட்ட meanings/answers ஒரு conflict ஆக manual review-க்கு காட்டப்படும்.' },
      { en: 'An answer, translation, or grammar explanation not directly present in the source chunks is marked admin-authored/human-synthesized and requires human review before it is usable for training.', ta: 'Source chunks-இல் நேரடியாக இல்லாத ஒரு answer, translation, அல்லது grammar explanation admin-authored/human-synthesized எனக் குறிக்கப்பட்டு, training-க்கு பயன்படுத்தும் முன் human review தேவைப்படும்.' },
    ],
    nextPageIds: ['quality_approval', 'datasets', 'knowledge_rag'],
    safetyNote: {
      en: 'Approving a chunk or a structured record candidate never implies source-rights, training, commercial, or public-export approval by itself -- always run a usage-eligibility check for the specific target use before exporting or handing off to RAG.',
      ta: 'ஒரு chunk அல்லது structured record candidate-ஐ approve செய்வது தானாகவே source-rights, training, commercial, அல்லது public-export approval-ஐ குறிக்காது -- export செய்வதற்கு அல்லது RAG-க்கு handoff செய்வதற்கு முன் குறிப்பிட்ட target use-க்கான usage-eligibility check-ஐ எப்போதும் இயக்கவும்.',
    },
  },
  {
    pageId: 'quality_approval',
    activeKey: 'Quality & Approval',
    title: { en: 'Quality & Approval', ta: 'Quality & Approval' },
    purpose: {
      en: 'One consolidated review queue across every governed entity (document pages, manual data records, semantic chunks, structured record candidates, document candidates, dataset records): normalized quality issues, persisted duplicate/conflict groups, and a per-target-use approval decision -- never a single global "approved" flag.',
      ta: 'Governed செய்யப்படும் ஒவ்வொரு entity-க்கும் (document pages, manual data records, semantic chunks, structured record candidates, document candidates, dataset records) ஒரே consolidated review queue: normalized quality issues, சேமிக்கப்பட்ட duplicate/conflict groups, மற்றும் ஒவ்வொரு target use-க்கும் தனித்தனி approval முடிவு -- ஒரே global "approved" flag ஒருபோதும் இல்லை.',
    },
    prerequisites: [
      { en: 'An entity (a manual data record, semantic chunk, structured record candidate, document page, document candidate, or dataset record) already created in its own workspace.', ta: 'அதன் சொந்த workspace-இல் ஏற்கனவே உருவாக்கப்பட்ட ஒரு entity (manual data record, semantic chunk, structured record candidate, document page, document candidate, அல்லது dataset record).' },
    ],
    workflowSteps: [
      { en: 'Queue tab: filter the unified queue by status, priority, or entity type, and open any item for detail -- or open a new review item manually for an entity that needs attention.', ta: 'Queue tab: unified queue-ஐ status, priority, அல்லது entity type வாரியாக filter செய்து, எந்த item-ஐயும் detail-க்காக திறக்கவும் -- அல்லது கவனம் தேவைப்படும் ஒரு entity-க்காக ஒரு புதிய review item-ஐ கைமுறையாக திறக்கவும்.' },
      { en: 'Review Detail tab: see every open issue and target-approval decision on one item, assign it to an admin, add a note, or change its status -- resolving an item is blocked while an unresolved blocking issue remains.', ta: 'Review Detail tab: ஒரு item-இன் ஒவ்வொரு open issue-ஐயும் target-approval முடிவையும் ஒரே இடத்தில் பார்க்கவும், அதை ஒரு admin-க்கு assign செய்யவும், ஒரு note சேர்க்கவும், அல்லது அதன் status-ஐ மாற்றவும் -- தீர்க்கப்படாத ஒரு blocking issue இருக்கும் வரை item-ஐ resolve செய்ய முடியாது.' },
      { en: 'Quality tab: run a quality assessment on a dataset record, manual data record, or semantic chunk -- this reads that entity\'s own existing quality result and never recomputes a score a subsystem already owns; a blocking issue automatically opens (or reuses) a review item.', ta: 'Quality tab: ஒரு dataset record, manual data record, அல்லது semantic chunk-இன் மீது quality assessment இயக்கவும் -- இது அந்த entity-இன் சொந்த quality result-ஐ படிக்கும், ஒரு subsystem ஏற்கனவே கொண்டிருக்கும் score-ஐ ஒருபோதும் மீண்டும் கணக்கிடாது; ஒரு blocking issue தானாக ஒரு review item-ஐ திறக்கும் (அல்லது மீண்டும் பயன்படுத்தும்).' },
      { en: 'Duplicates/Conflicts tabs: run a duplicate or conflict check (reusing the existing pairwise detectors), persist the result as a group, and explicitly resolve it with a reason -- a duplicate/conflict group is never auto-deleted, auto-merged, or auto-rejected, and an alternate dictionary sense/answer/translation is surfaced as a conflict, never treated as a duplicate.', ta: 'Duplicates/Conflicts tabs: (ஏற்கனவே உள்ள pairwise detectors-ஐ மீண்டும் பயன்படுத்தி) ஒரு duplicate அல்லது conflict check இயக்கி, முடிவை ஒரு group ஆக சேமித்து, ஒரு காரணத்துடன் அதை வெளிப்படையாக resolve செய்யவும் -- ஒரு duplicate/conflict group ஒருபோதும் auto-delete, auto-merge, அல்லது auto-reject செய்யப்படாது, மாற்று dictionary sense/answer/translation ஒரு conflict ஆக காட்டப்படும், duplicate ஆக ஒருபோதும் கருதப்படாது.' },
      { en: 'Approvals tab: load an entity\'s per-target-use matrix, evaluate a specific target use, or record an explicit admin override -- an override always requires a reason and is always audited; a high quality score never overrides a blocking issue.', ta: 'Approvals tab: ஒரு entity-இன் per-target-use matrix-ஐ ஏற்றவும், ஒரு குறிப்பிட்ட target use-ஐ evaluate செய்யவும், அல்லது ஒரு வெளிப்படையான admin override-ஐ பதிவு செய்யவும் -- ஒரு override எப்போதும் ஒரு காரணத்தை கோரும், எப்போதும் audit செய்யப்படும்; ஒரு உயர் quality score ஒருபோதும் ஒரு blocking issue-ஐ மீறாது.' },
      { en: 'Export Readiness tab: check whether dataset export or RAG handoff is currently allowed for an entity before attempting it -- the export/handoff actions themselves run this exact same check first.', ta: 'Export Readiness tab: dataset export அல்லது RAG handoff-ஐ முயற்சிப்பதற்கு முன், அது ஒரு entity-க்கு தற்போது அனுமதிக்கப்படுகிறதா எனச் சரிபார்க்கவும் -- export/handoff செயல்கள் தாமே இந்த சரிபார்ப்பையே முதலில் இயக்கும்.' },
      { en: 'History tab: load the full append-only event trail for a review item -- opened, assigned, note added, status changed, and every target-approval decision.', ta: 'History tab: ஒரு review item-இன் முழுமையான append-only event trail-ஐ ஏற்றவும் -- opened, assigned, note added, status changed, மற்றும் ஒவ்வொரு target-approval முடிவும்.' },
    ],
    commonIssues: [
      { en: 'An entity with no governance activity at all is never blocked by export/handoff -- the preflight guard only blocks when an unresolved review item, duplicate group, or conflict group actually exists for it.', ta: 'எந்த governance activity-யும் இல்லாத ஒரு entity ஒருபோதும் export/handoff-இல் தடுக்கப்படாது -- தீர்க்கப்படாத ஒரு review item, duplicate group, அல்லது conflict group உண்மையில் இருந்தால் மட்டுமே preflight guard தடுக்கும்.' },
      { en: 'A canonical dimension the source quality system does not measure is shown as not-measured, never a fabricated number.', ta: 'மூல quality system அளவிடாத ஒரு canonical dimension "அளவிடப்படவில்லை" எனக் காட்டப்படும், ஒருபோதும் கற்பனையான எண் அல்ல.' },
      { en: 'Approval is per target use (RAG, training, evaluation, commercial, public export, redistribution, dataset export, RAG handoff) -- there is no single record-wide "approved" switch.', ta: 'Approval ஒவ்வொரு target use-க்கும் (RAG, training, evaluation, commercial, public export, redistribution, dataset export, RAG handoff) தனித்தனியாக இருக்கும் -- ஒரே record-wide "approved" switch கிடையாது.' },
    ],
    nextPageIds: ['builds_pipelines', 'chunk_studio', 'manual_data', 'datasets'],
    safetyNote: {
      en: 'This page never deletes, merges, or auto-approves anything -- every resolution and every override is a deliberate, reasoned, audited human action, and approved content elsewhere in the system remains immutable and revisioned exactly as its own workspace already enforces.',
      ta: 'இந்த பக்கம் எதையும் ஒருபோதும் delete, merge, அல்லது auto-approve செய்யாது -- ஒவ்வொரு resolution மற்றும் override-உம் ஒரு வேண்டுமென்றே, காரணத்துடன், audit செய்யப்பட்ட human action ஆகும்; அமைப்பில் வேறு இடங்களில் உள்ள approved content அதன் சொந்த workspace ஏற்கனவே செயல்படுத்தும் விதமாகவே immutable ஆகவும் revisioned ஆகவும் தொடரும்.',
    },
  },
  {
    pageId: 'builds_pipelines',
    activeKey: 'Builds & Pipelines',
    title: { en: 'Builds & Pipelines', ta: 'Builds & Pipelines' },
    purpose: {
      en: 'Turn approved, traceable Data Studio content into a governed, immutable dataset version for a specific target pipeline (dataset version, RAG, tokenizer, pretraining, instruction tuning, evaluation, commercial release, public export), then hand it off explicitly into RAG ingestion or the tokenizer/pretraining/instruction-tuning workflows -- reusing the existing dataset builder, RAG ingestion, and training systems rather than replacing any of them.',
      ta: 'Approve செய்யப்பட்ட, traceable Data Studio content-ஐ ஒரு குறிப்பிட்ட target pipeline-க்காக (dataset version, RAG, tokenizer, pretraining, instruction tuning, evaluation, commercial release, public export) ஒரு governed, immutable dataset version ஆக மாற்றி, பிறகு அதை RAG ingestion அல்லது tokenizer/pretraining/instruction-tuning workflows-க்கு வெளிப்படையாக handoff செய்யவும் -- இது ஏற்கனவே உள்ள dataset builder, RAG ingestion, training அமைப்புகளை மீண்டும் பயன்படுத்துகிறது, அவற்றில் எதையும் மாற்றாது.',
    },
    prerequisites: [
      { en: 'At least one dataset record that has already been through an explicit governance scan (Quality & Approval) for the target use this build needs -- a record with no governance activity at all is treated as legacy/unclassified and is never silently included.', ta: 'இந்த build-க்குத் தேவையான target use-க்காக ஏற்கனவே ஒரு வெளிப்படையான governance scan (Quality & Approval) செய்யப்பட்ட குறைந்தது ஒரு dataset record. எந்த governance activity-யும் இல்லாத ஒரு record legacy/unclassified எனக் கருதப்பட்டு ஒருபோதும் மௌனமாக சேர்க்கப்படாது.' },
    ],
    workflowSteps: [
      { en: 'Create Build tab: choose a target pipeline, optionally filter by record type/language/explicit entity IDs, and create the build request -- nothing is selected or built yet.', ta: 'Create Build tab: ஒரு target pipeline-ஐத் தேர்ந்தெடுத்து, விரும்பினால் record type/language/வெளிப்படையான entity IDs வாரியாக filter செய்து, build request-ஐ உருவாக்கவும் -- இன்னும் எதுவும் select அல்லது build செய்யப்படவில்லை.' },
      { en: 'Build Preview tab: run an ephemeral Preview to explore eligibility, then run the real Preflight -- which persists exactly which records are eligible, blocked, warning, or excluded, and why; toggle any non-blocked item\'s inclusion before confirming.', ta: 'Build Preview tab: eligibility-ஐ ஆராய ஒரு ephemeral Preview-ஐ இயக்கவும், பிறகு உண்மையான Preflight-ஐ இயக்கவும் -- இது எந்த records eligible, blocked, warning, அல்லது excluded என்பதையும் ஏன் என்பதையும் சரியாகச் சேமிக்கும்; confirm செய்வதற்கு முன் blocked இல்லாத எந்த item-இன் inclusion-ஐயும் toggle செய்யலாம்.' },
      { en: 'Confirm, then Execute -- Execute is the only step that calls the existing dataset builder for real and creates an immutable dataset version; nothing is created before this explicit action.', ta: 'Confirm செய்து, பிறகு Execute செய்யவும் -- Execute மட்டுமே ஏற்கனவே உள்ள dataset builder-ஐ உண்மையாக அழைத்து ஒரு immutable dataset version-ஐ உருவாக்கும் படி; இந்த வெளிப்படையான செயலுக்கு முன் எதுவும் உருவாக்கப்படாது.' },
      { en: 'Blocked Records tab: see every blocked record with its exact reason, linked back to the Quality & Approval review item that needs resolving.', ta: 'Blocked Records tab: ஒவ்வொரு blocked record-ஐயும் அதன் சரியான காரணத்துடன் பார்க்கவும், தீர்க்க வேண்டிய Quality & Approval review item-உடன் இணைக்கப்பட்டிருக்கும்.' },
      { en: 'RAG Handoffs tab: once a rag-target build is completed, ingest its dataset version into an existing knowledge space as a real RAG source -- the resulting index is never activated automatically.', ta: 'RAG Handoffs tab: ஒரு rag-target build முடிந்தவுடன், அதன் dataset version-ஐ ஏற்கனவே உள்ள knowledge space-இல் ஒரு உண்மையான RAG source ஆக ingest செய்யவும் -- இதன் விளைவான index ஒருபோதும் தானாக activate செய்யப்படாது.' },
      { en: 'Tokenizer & Training / Evaluation Builds tabs: hand a completed dataset version off to the tokenizer, pretraining, instruction-tuning, or evaluation workflow -- this only marks it ready; starting the actual run remains the existing, separate, manual action on its own page.', ta: 'Tokenizer & Training / Evaluation Builds tabs: முடிக்கப்பட்ட ஒரு dataset version-ஐ tokenizer, pretraining, instruction-tuning, அல்லது evaluation workflow-க்கு handoff செய்யவும் -- இது தயார் எனக் குறிக்கும் மட்டுமே; உண்மையான run-ஐ தொடங்குவது அதன் சொந்த பக்கத்தில் உள்ள ஏற்கனவே இருக்கும், தனி, கைமுறை செயலாகவே தொடரும்.' },
      { en: 'Manifests tab: generate and view the governance-extended manifest (source/rights/quality/duplicate/conflict summaries, attribution, checksums) alongside the existing dataset version manifest.', ta: 'Manifests tab: governance-extended manifest-ஐ (source/rights/quality/duplicate/conflict summaries, attribution, checksums) ஏற்கனவே உள்ள dataset version manifest-உடன் சேர்த்து உருவாக்கி பார்க்கவும்.' },
      { en: 'Lineage tab: trace a dataset record\'s full upstream/downstream chain -- a gap is always shown as "lineage incomplete," never a fabricated link.', ta: 'Lineage tab: ஒரு dataset record-இன் முழு upstream/downstream chain-ஐ trace செய்யவும் -- ஒரு இடைவெளி எப்போதும் "lineage incomplete" எனக் காட்டப்படும், ஒருபோதும் கற்பனையான இணைப்பு அல்ல.' },
    ],
    commonIssues: [
      { en: 'A record with zero governance activity is always blocked (legacy/unclassified) on its first preflight, even if its underlying rights look fine -- run an explicit governance scan (Quality & Approval) or use a documented legacy override first.', ta: 'எந்த governance activity-யும் இல்லாத ஒரு record, அதன் rights நன்றாக இருந்தாலும், அதன் முதல் preflight-இல் எப்போதும் தடுக்கப்படும் (legacy/unclassified) -- முதலில் ஒரு வெளிப்படையான governance scan (Quality & Approval) இயக்கவும் அல்லது ஒரு documented legacy override பயன்படுத்தவும்.' },
      { en: 'A record approved for one target pipeline (e.g. RAG) is never automatically eligible for another (e.g. pretraining) -- each pipeline is evaluated independently.', ta: 'ஒரு target pipeline-க்கு (எ.கா. RAG) approve செய்யப்பட்ட ஒரு record, இன்னொன்றுக்கு (எ.கா. pretraining) ஒருபோதும் தானாக eligible ஆகாது -- ஒவ்வொரு pipeline-உம் தனித்தனியாக evaluate செய்யப்படும்.' },
      { en: 'Evaluation-target records are always isolated from train/validation splits in any other build -- confirmed structurally, not just by policy.', ta: 'Evaluation-target records எப்போதும் வேறு எந்த build-இன் train/validation splits-இலிருந்தும் தனிமைப்படுத்தப்படும் -- இது structural ஆகவே உறுதிப்படுத்தப்படுகிறது, policy மூலம் மட்டுமல்ல.' },
      { en: 'Confirming or executing a build never starts a RAG index build/activation or a training run by itself -- those remain separate, existing, manual actions.', ta: 'ஒரு build-ஐ confirm அல்லது execute செய்வது ஒருபோதும் தானாக ஒரு RAG index build/activation அல்லது training run-ஐ தொடங்காது -- அவை தனி, ஏற்கனவே இருக்கும், கைமுறை செயல்களாகவே தொடரும்.' },
    ],
    nextPageIds: ['datasets', 'knowledge_rag', 'pretraining_readiness'],
    safetyNote: {
      en: 'Nothing here is published, released, or trained automatically -- every build requires an explicit Confirm and Execute, every handoff is a separate explicit action, and public-export/commercial builds are fail-closed on unresolved rights, exactly like the rest of Data Studio governance.',
      ta: 'இங்கு எதுவும் தானாக publish, release, அல்லது train செய்யப்படாது -- ஒவ்வொரு build-க்கும் ஒரு வெளிப்படையான Confirm மற்றும் Execute தேவை, ஒவ்வொரு handoff-உம் ஒரு தனி வெளிப்படையான செயல், மேலும் public-export/commercial builds தீர்க்கப்படாத rights-இல் fail-closed ஆகும் -- Data Studio governance-இன் மற்ற பகுதிகளைப் போலவே.',
    },
  },
  {
    pageId: 'corpus_builder',
    activeKey: 'Corpus Builder',
    title: { en: 'Corpus Builder', ta: 'Corpus Builder' },
    purpose: {
      en: 'Assemble a large Tamil/English/Tanglish corpus with proven origin, licence, quality, privacy, and contamination safety before any content becomes an immutable, exportable corpus version.',
      ta: 'origin, licence, quality, privacy, contamination பாதுகாப்பு நிரூபிக்கப்பட்ட பிறகே ஒரு பெரிய Tamil/English/Tanglish corpus-ஐ, immutable, exportable corpus version ஆக உருவாக்கவும்.',
    },
    prerequisites: [
      { en: 'A registered source with a reviewed licence before it can reach training eligibility.', ta: 'Training eligibility அடைய, review செய்யப்பட்ட licence உள்ள ஒரு பதிவு செய்யப்பட்ட source தேவை.' },
    ],
    workflowSteps: [
      { en: 'Policies tab: define and activate a corpus policy.', ta: 'Policies tab: ஒரு corpus policy-ஐ define செய்து activate செய்யவும்.' },
      { en: 'Sources & Licences: register a source, verify its origin, and review its licence.', ta: 'Sources & Licences: ஒரு source-ஐ பதிவு செய்து, origin-ஐ verify செய்து, licence-ஐ review செய்யவும்.' },
      { en: 'Snapshots & Extraction → Normalization & Segmentation: take an immutable snapshot, extract, normalize, and segment.', ta: 'Snapshots & Extraction → Normalization & Segmentation: ஒரு immutable snapshot எடுத்து, extract, normalize, segment செய்யவும்.' },
      { en: 'Quality & Safety, Deduplication & Contamination: screen every segment before it can enter a collection.', ta: 'Quality & Safety, Deduplication & Contamination: ஒரு collection-இல் சேருவதற்கு முன் ஒவ்வொரு segment-ஐயும் சரிபார்க்கவும்.' },
      { en: 'Collections & Balance → Builds & Partitions → Versions/Export/Manifest: assemble, build, and export the final corpus version.', ta: 'Collections & Balance → Builds & Partitions → Versions/Export/Manifest: இறுதி corpus version-ஐ சேர்த்து, build செய்து, export செய்யவும்.' },
    ],
    commonIssues: [
      { en: 'An unknown-licence or use-mismatched source is structurally blocked from training eligibility.', ta: 'தெரியாத licence அல்லது பயன்பாடு பொருந்தாத source, training eligibility-இல் இருந்து முழுமையாக தடுக்கப்படும்.' },
      { en: 'Finalizing a corpus export never starts model training automatically.', ta: 'Corpus export-ஐ finalize செய்வது தானாக model training-ஐ தொடங்காது.' },
    ],
    nextPageIds: ['pretraining_readiness'],
    safetyNote: {
      en: 'Genuine secrets/credentials are always blocked from the corpus regardless of policy.',
      ta: 'உண்மையான secrets/credentials, policy எதுவாக இருந்தாலும் corpus-இல் இருந்து எப்போதும் தடுக்கப்படும்.',
    },
  },
  {
    pageId: 'knowledge_rag',
    activeKey: 'Knowledge & RAG',
    title: { en: 'Knowledge & RAG', ta: 'Knowledge & RAG' },
    purpose: {
      en: 'Ingest approved knowledge sources into chunked, indexed evidence, then test grounded retrieval and generation in a private admin lab.',
      ta: 'Approved knowledge sources-ஐ chunk செய்து, index செய்து, private admin lab-இல் grounded retrieval மற்றும் generation-ஐ சோதிக்கவும்.',
    },
    prerequisites: [
      { en: 'A knowledge space and at least one approved source version.', ta: 'ஒரு knowledge space மற்றும் குறைந்தது ஒரு approved source version.' },
    ],
    workflowSteps: [
      { en: 'Knowledge Spaces → Sources → Source Versions: register and version the source content.', ta: 'Knowledge Spaces → Sources → Source Versions: மூல உள்ளடக்கத்தை பதிவு செய்து version செய்யவும்.' },
      { en: 'Chunking → Chunk Quality: split content and screen for injection-style text.', ta: 'Chunking → Chunk Quality: உள்ளடக்கத்தை பிரித்து, injection-பாணி உரையை சரிபார்க்கவும்.' },
      { en: 'Embedding Models/Runs → Vector/Keyword Indexes: build and activate the retrieval indexes.', ta: 'Embedding Models/Runs → Vector/Keyword Indexes: retrieval indexes-ஐ build செய்து activate செய்யவும்.' },
      { en: 'Retrieval Lab / RAG Chat Lab: exercise grounded generation before trusting it.', ta: 'Retrieval Lab / RAG Chat Lab: நம்புவதற்கு முன் grounded generation-ஐ சோதிக்கவும்.' },
    ],
    commonIssues: [
      { en: 'Only approved sources’ chunks are ever eligible for embedding or keyword indexing.', ta: 'Approved sources-இன் chunks மட்டுமே embedding அல்லது keyword indexing-க்கு தகுதி பெறும்.' },
      { en: 'Insufficient evidence produces an explicit safe no-answer result, never a fabricated one.', ta: 'போதுமான evidence இல்லாதபோது, ஒரு தெளிவான safe no-answer result தரப்படும் -- கற்பனையானது அல்ல.' },
    ],
    nextPageIds: ['data_overview'],
    safetyNote: {
      en: 'The public chatbot is never connected here -- this remains an admin-only lab.',
      ta: 'பொது chatbot இங்கே ஒருபோதும் இணைக்கப்படவில்லை -- இது admin-மட்டும் lab ஆகவே இருக்கும்.',
    },
  },
  {
    pageId: 'pretraining_readiness',
    activeKey: 'Pretraining Readiness',
    title: { en: 'Pretraining Readiness', ta: 'Pretraining Readiness' },
    purpose: {
      en: 'Bridge an approved corpus release into a tokenizer-training corpus and a frozen pretraining dataset snapshot, then run the 17-dimension readiness gate before any real pretraining.',
      ta: 'ஒரு approved corpus release-ஐ tokenizer-training corpus ஆகவும், ஒரு frozen pretraining dataset snapshot ஆகவும் மாற்றி, உண்மையான pretraining-க்கு முன் 17-dimension readiness gate-ஐ இயக்கவும்.',
    },
    prerequisites: [
      { en: 'An approved, exported Corpus Builder release.', ta: 'Corpus Builder-இல் approve செய்யப்பட்டு export செய்யப்பட்ட ஒரு release.' },
    ],
    workflowSteps: [
      { en: 'Tokenizer Corpus: build and check sufficiency.', ta: 'Tokenizer Corpus: build செய்து sufficiency-ஐ சரிபார்க்கவும்.' },
      { en: 'Tokenizer Candidates: compare candidates and approve one.', ta: 'Tokenizer Candidates: candidates-ஐ ஒப்பிட்டு ஒன்றை approve செய்யவும்.' },
      { en: 'Dataset Snapshot: freeze the pretraining dataset snapshot.', ta: 'Dataset Snapshot: pretraining dataset snapshot-ஐ freeze செய்யவும்.' },
      { en: 'Training Config & Smoke Runs → Readiness: validate configuration, run a smoke test, then evaluate all 17 dimensions.', ta: 'Training Config & Smoke Runs → Readiness: configuration-ஐ validate செய்து, smoke test இயக்கி, 17 dimensions-ஐயும் evaluate செய்யவும்.' },
    ],
    commonIssues: [
      { en: 'Any failing dimension forces "not_ready"; a warning caps the result at "ready_for_experimental_pretraining", never silently upgraded.', ta: 'ஒரு dimension தோற்றால் "not_ready" ஆகிவிடும்; ஒரு warning "ready_for_experimental_pretraining"-இல் நிறுத்தும், தானாக மேம்படாது.' },
    ],
    nextPageIds: ['evaluation'],
    safetyNote: {
      en: 'This is a preparation/safety gate only -- it does not itself start a production pretraining run.',
      ta: 'இது ஒரு preparation/safety gate மட்டுமே -- இது production pretraining run-ஐ தானாக தொடங்காது.',
    },
  },
  {
    pageId: 'evaluation',
    activeKey: 'Evaluation',
    title: { en: 'Evaluation', ta: 'Evaluation' },
    purpose: {
      en: 'Author versioned evaluation fixture suites, run bounded generation against every fixture, review results, and assess chat-readiness for a candidate.',
      ta: 'Version செய்யப்பட்ட evaluation fixture suites-ஐ உருவாக்கி, ஒவ்வொரு fixture-க்கும் bounded generation இயக்கி, results-ஐ review செய்து, ஒரு candidate-இன் chat-readiness-ஐ மதிப்பிடவும்.',
    },
    prerequisites: [
      { en: 'A candidate eligible for evaluation and at least one activated fixture suite.', ta: 'Evaluation-க்கு தகுதியான ஒரு candidate மற்றும் குறைந்தது ஒரு activate செய்யப்பட்ட fixture suite.' },
    ],
    workflowSteps: [
      { en: 'Create a suite and add fixtures across the categories you need to cover.', ta: 'ஒரு suite உருவாக்கி, தேவையான categories-இல் fixtures சேர்க்கவும்.' },
      { en: 'Activate the suite, then create and execute a run against a candidate.', ta: 'Suite-ஐ activate செய்து, ஒரு candidate-க்கு எதிராக run உருவாக்கி இயக்கவும்.' },
      { en: 'Review outputs/metrics/issues, add human review where it disagrees with the automated score.', ta: 'Outputs/metrics/issues-ஐ review செய்து, automated score-உடன் உடன்படாதபோது human review சேர்க்கவும்.' },
      { en: 'Assess readiness once evidence is complete.', ta: 'Evidence முழுமையானதும் readiness-ஐ மதிப்பிடவும்.' },
    ],
    commonIssues: [
      { en: 'Any blocking issue (unsafe compliance, role-token leakage, unverified checkpoint) forces evaluation_blocked regardless of other scores.', ta: 'ஒரு blocking issue (unsafe compliance, role-token leakage, unverified checkpoint) இருந்தால், மற்ற scores எதுவாக இருந்தாலும் evaluation_blocked ஆகிவிடும்.' },
    ],
    nextPageIds: ['data_overview'],
    safetyNote: {
      en: 'A candidate remains not_public_chat_ready no matter the outcome recorded here.',
      ta: 'இங்கே பதிவான முடிவு எதுவாக இருந்தாலும், candidate எப்போதும் not_public_chat_ready ஆகவே இருக்கும்.',
    },
  },
]

export function getHelpEntry(pageId) {
  return dataHelpEntries.find((entry) => entry.pageId === pageId) ?? null
}
