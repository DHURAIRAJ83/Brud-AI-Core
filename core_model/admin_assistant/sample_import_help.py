"""Phase 12 Step 30: deterministic (never LLM-generated) answers to
the 10 fixed sample-import/quarantine questions the Admin Assistant
must answer consistently in Tamil/English/Tanglish/Auto. Tanglish is
always *derived* from each entry's own "ta" value via
`core_model.admin_assistant.localization.message_catalog.localize()`
(Phase 10A's own system) -- never hand-written a third time.

Every answer here restates one of Phase 12's own non-negotiable
rules; none of it is invented, and none of it may drift from the
structural invariants enforced in code (`core_model.sample_import`,
the sample-import services). If a rule described here ever changes in
code, this file must change with it -- there is no independent source
of truth.
"""

from __future__ import annotations

SAMPLE_IMPORT_FAQ: dict[str, dict[str, object]] = {
    "why_sample_import_separate_from_dataset_approval": {
        "keywords": (
            "why is sample import separate", "sample import separate from dataset approval",
            "dataset verified vs sample import",
        ),
        "en": (
            "A finalized Phase 11 verification case only means the dataset's licence/rights "
            "were checked -- it never means any file was downloaded or inspected. Sample "
            "import is a separate, explicitly bound approval (its own record/byte limits and "
            "expiry) because inspecting real file content carries its own risks -- unsafe "
            "files, PII, quality issues -- that licence verification alone cannot detect."
        ),
        "ta": (
            "ஒரு finalize செய்யப்பட்ட Phase 11 verification case, dataset-இன் licence/rights "
            "சரிபார்க்கப்பட்டது என்று மட்டுமே பொருள் -- இது ஒருபோதும் எந்த file-உம் "
            "download செய்யப்பட்டது அல்லது ஆய்வு செய்யப்பட்டது என்று பொருள் அல்ல. "
            "Sample import என்பது தனியான, தெளிவாக bound செய்யப்பட்ட approval (அதன் சொந்த "
            "record/byte limits மற்றும் expiry) -- ஏனெனில் real file content-ஐ ஆய்வு "
            "செய்வது, licence verification மட்டும் கண்டறிய முடியாத unsafe files, PII, "
            "quality issues போன்ற தனித் தனி risks-ஐ கொண்டுள்ளது."
        ),
    },
    "what_is_quarantine": {
        "keywords": ("what is quarantine", "quarantine meaning", "what does quarantine mean"),
        "en": (
            "Quarantine is an isolated storage area, one directory per sample import, "
            "structurally separate from approved dataset storage, RAG indexes, training "
            "data, model artifacts, and frontend static files. Nothing outside Phase 12's "
            "own code ever reads from it, and it is never reachable through a public URL."
        ),
        "ta": (
            "Quarantine என்பது ஒரு தனிமைப்படுத்தப்பட்ட storage area -- ஒரு sample import-க்கு "
            "ஒரு directory, approved dataset storage, RAG indexes, training data, model "
            "artifacts, மற்றும் frontend static files-இலிருந்து கட்டமைப்பு ரீதியாக தனியாக "
            "உள்ளது. Phase 12-இன் சொந்த code-ஐத் தவிர வேறு எதுவும் இதிலிருந்து படிக்காது, "
            "மேலும் இது ஒருபோதும் public URL மூலம் அடையக்கூடியதாக இருக்காது."
        ),
    },
    "why_cant_quarantined_data_enter_rag": {
        "keywords": (
            "quarantined data enter rag", "why can't quarantined data enter rag",
            "quarantine enter rag",
        ),
        "en": (
            "No quarantined record may enter RAG or training -- this is a structural rule, "
            "not a policy choice an admin can override. A sample must be validated, "
            "reviewed, and finalized first; even then, the report only ever produces "
            "`rag_sandbox_eligible = true/false`, never a RAG index. Building an actual RAG "
            "index only ever happens in Phase 13, on separately-approved data."
        ),
        "ta": (
            "எந்த quarantined record-உம் RAG அல்லது training-க்குள் நுழையக்கூடாது -- இது "
            "ஒரு structural rule, ஒரு admin மாற்றக்கூடிய policy choice அல்ல. ஒரு sample "
            "முதலில் validate, review, மற்றும் finalize செய்யப்பட வேண்டும்; அப்போது கூட, "
            "report ஒருபோதும் `rag_sandbox_eligible = true/false` ஐ மட்டுமே உருவாக்கும், "
            "ஒரு RAG index-ஐ அல்ல. உண்மையான RAG index உருவாக்குவது Phase 13-இல் மட்டுமே, "
            "தனியாக approve செய்யப்பட்ட data-இல் நடக்கும்."
        ),
    },
    "what_is_an_archive_bomb": {
        "keywords": ("archive bomb", "what is an archive bomb", "zip bomb"),
        "en": (
            "An archive bomb is a small compressed file crafted to expand into an enormous "
            "amount of data (or an enormous number of files) once extracted, aiming to "
            "exhaust disk/memory. Phase 12 defends against this with a maximum member "
            "count, a maximum total expanded size, and a compression-ratio threshold -- "
            "extraction aborts the instant any of these is exceeded, and any partial output "
            "is deleted."
        ),
        "ta": (
            "Archive bomb என்பது extract செய்யப்பட்டதும், disk/memory-ஐ தீர்த்துவிட "
            "நோக்கத்துடன், மிகப் பெரிய அளவு data (அல்லது மிகப் பெரிய எண்ணிக்கையிலான "
            "files) ஆக விரிவடையும்படி வடிவமைக்கப்பட்ட ஒரு சிறிய compressed file. Phase "
            "12, ஒரு maximum member count, ஒரு maximum total expanded size, மற்றும் ஒரு "
            "compression-ratio threshold மூலம் இதை எதிர்க்கிறது -- இவற்றில் ஏதேனும் "
            "மீறப்பட்ட உடனேயே extraction நிறுத்தப்படும், மேலும் எந்த partial output-உம் "
            "delete செய்யப்படும்."
        ),
    },
    "what_happens_when_pii_is_detected": {
        "keywords": ("pii is detected", "what happens when pii", "pii detected"),
        "en": (
            "The original quarantined record is never modified. A finding is recorded with "
            "its category, confidence, and location (never the raw matched value in a "
            "summary or log); ambiguous findings always require human review. An Admin may "
            "propose a redacted derived copy, but the original stays exactly as downloaded."
        ),
        "ta": (
            "Original quarantine செய்யப்பட்ட record ஒருபோதும் மாற்றப்படாது. ஒரு finding, "
            "அதன் category, confidence, மற்றும் location-உடன் பதிவு செய்யப்படும் (ஒருபோதும் "
            "raw matched value summary அல்லது log-இல் இல்லை); ambiguous findings எப்போதும் "
            "human review தேவைப்படும். ஒரு Admin ஒரு redacted derived copy-ஐ முன்மொழியலாம், "
            "ஆனால் original download செய்யப்பட்டதைப் போலவே அப்படியே இருக்கும்."
        ),
    },
    "why_isnt_a_sample_enough_for_training_approval": {
        "keywords": (
            "sample not enough for training", "sample enough for training approval",
            "why isn't a sample enough",
        ),
        "en": (
            "A bounded sample can only produce an advisory `training_assessment_status` "
            "(not_assessed / potentially_suitable / needs_more_review / not_suitable / "
            "blocked) -- there is no 'training_approved' value anywhere in this phase's "
            "code. A small sample cannot represent an entire dataset's quality, coverage, "
            "or contamination risk; real training approval is a separate, later governed "
            "decision outside Phase 12 entirely."
        ),
        "ta": (
            "ஒரு bounded sample, ஒரு advisory `training_assessment_status`-ஐ மட்டுமே "
            "உருவாக்க முடியும் (not_assessed / potentially_suitable / needs_more_review / "
            "not_suitable / blocked) -- இந்த phase-இன் code-இல் எங்கும் 'training_approved' "
            "என்ற value கிடையாது. ஒரு சிறிய sample, ஒரு முழு dataset-இன் quality, coverage, "
            "அல்லது contamination risk-ஐ பிரதிநிதித்துவப்படுத்த முடியாது; உண்மையான "
            "training approval, Phase 12-க்கு முற்றிலும் வெளியே, தனியான, பிற்கால governed "
            "முடிவாகும்."
        ),
    },
    "what_does_rag_sandbox_eligible_mean": {
        "keywords": ("rag sandbox eligible", "what does rag sandbox eligible mean"),
        "en": (
            "`rag_sandbox_eligible = true` means this sample's finalized report cleared "
            "every check (legal, security, PII, quality, review) needed to be inspected in "
            "Phase 13's RAG Sandbox. It is not production RAG approval and it does not "
            "create a RAG index -- Phase 12 never builds one."
        ),
        "ta": (
            "`rag_sandbox_eligible = true` என்றால், இந்த sample-இன் finalize செய்யப்பட்ட "
            "report, Phase 13-இன் RAG Sandbox-இல் ஆய்வு செய்யப்படத் தேவையான ஒவ்வொரு check-ஐயும் "
            "(legal, security, PII, quality, review) கடந்துவிட்டது என்று பொருள். இது "
            "production RAG approval அல்ல, மேலும் இது ஒரு RAG index-ஐ உருவாக்காது -- "
            "Phase 12 ஒருபோதும் ஒன்றை உருவாக்காது."
        ),
    },
    "why_was_this_file_blocked": {
        "keywords": ("why was this file blocked", "file blocked", "why is my file blocked"),
        "en": (
            "A file is blocked when its filename, detected MIME type, or magic-byte "
            "signature matches a disallowed class (executables, scripts, macros, archives "
            "with unsafe entries, unknown binary blobs, model-weight files, and others) -- "
            "never based on its extension alone. The file's `blocked_class` and "
            "`rejection_reason` fields explain exactly why."
        ),
        "ta": (
            "ஒரு file-இன் filename, detected MIME type, அல்லது magic-byte signature, "
            "அனுமதிக்கப்படாத ஒரு class-உடன் (executables, scripts, macros, unsafe entries "
            "கொண்ட archives, unknown binary blobs, model-weight files, மற்றும் பிற) "
            "பொருந்தும் போது ஒரு file block செய்யப்படும் -- ஒருபோதும் அதன் extension "
            "மட்டும் அடிப்படையில் அல்ல. File-இன் `blocked_class` மற்றும் "
            "`rejection_reason` fields இதற்கான காரணத்தை துல்லியமாக விளக்கும்."
        ),
    },
    "why_is_an_original_file_immutable": {
        "keywords": ("original file immutable", "why is an original file immutable"),
        "en": (
            "The original quarantined file/record is never modified by any review, scan, "
            "or normalization step -- it stays byte-identical to what was downloaded, "
            "forever. Every correction (redaction, edited derived copy) is stored as a "
            "separate, append-only derived version, so the original always remains the "
            "ground truth for later audit or dispute."
        ),
        "ta": (
            "Original quarantine செய்யப்பட்ட file/record, எந்த review, scan, அல்லது "
            "normalization step மூலமும் ஒருபோதும் மாற்றப்படாது -- இது download "
            "செய்யப்பட்டதைப் போலவே, என்றென்றும் byte-identical ஆக இருக்கும். ஒவ்வொரு "
            "correction-உம் (redaction, edited derived copy) தனியான, append-only derived "
            "version ஆக சேமிக்கப்படும், எனவே original எப்போதும் பிற்கால audit அல்லது "
            "dispute-க்கான ground truth ஆக இருக்கும்."
        ),
    },
    "why_are_evaluation_duplicates_dangerous": {
        "keywords": (
            "evaluation duplicates dangerous", "why are evaluation duplicates dangerous",
            "contamination dangerous",
        ),
        "en": (
            "If a training record is actually a duplicate of something in a validation, "
            "test, or evaluation-fixture set, a model trained on it can appear to perform "
            "well simply because it memorized the answer -- not because it actually "
            "learned. Confirmed contamination against those sets always blocks "
            "`training_assessment_status`, though the record may still be retained as "
            "evaluation-only data if rights permit and an Admin explicitly reviews it."
        ),
        "ta": (
            "ஒரு training record உண்மையில் ஒரு validation, test, அல்லது evaluation-fixture "
            "set-இல் உள்ளதன் duplicate ஆக இருந்தால், அதில் train செய்யப்பட்ட ஒரு model, "
            "உண்மையில் கற்றுக்கொள்ளாமல், விடையை மனப்பாடம் செய்ததால் மட்டுமே நன்றாக "
            "செயல்படுவது போல் தோன்றலாம். அந்த sets-க்கு எதிரான confirmed contamination "
            "எப்போதும் `training_assessment_status`-ஐ block செய்யும், இருப்பினும் rights "
            "அனுமதித்தால் மற்றும் ஒரு Admin தெளிவாக review செய்தால், record evaluation-only "
            "data ஆக இன்னும் தக்கவைக்கப்படலாம்."
        ),
    },
}


def match_sample_import_question(message: str) -> str | None:
    """Returns the matching FAQ key for a message, or `None`. Matches
    the longest keyword found so a more specific phrase always wins
    over an accidental shorter substring match."""

    message_lower = message.lower()
    best_key: str | None = None
    best_length = 0
    for key, entry in SAMPLE_IMPORT_FAQ.items():
        for keyword in entry["keywords"]:
            if keyword in message_lower and len(keyword) > best_length:
                best_key = key
                best_length = len(keyword)
    return best_key
