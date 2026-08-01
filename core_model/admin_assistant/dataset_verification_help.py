"""Phase 11 Step 25: deterministic (never LLM-generated) answers to
the 8 fixed licence/rights-verification questions the Admin Assistant
must answer consistently in Tamil/English/Tanglish/Auto. Tanglish is
always *derived* from each entry's own "ta" value via
`core_model.admin_assistant.localization.message_catalog.localize()`
(Phase 10A's own system) -- never hand-written a third time.

Every answer here restates one of Phase 11's own non-negotiable
rules; none of it is invented, and none of it may drift from the
structural invariants enforced in code (`core_model.data_verification`,
the verification services). If a rule described here ever changes in
code, this file must change with it -- there is no independent source
of truth.
"""

from __future__ import annotations

DATASET_VERIFICATION_FAQ: dict[str, dict[str, object]] = {
    "what_is_declared_licence": {
        "keywords": ("declared licence", "declared license"),
        "en": (
            "A 'declared licence' is whatever a provider or the dataset's own metadata "
            "*claims* the licence is -- it is provider-declared information, not verified "
            "fact. It only becomes 'verified' once real licence evidence (a licence file or "
            "licence page) has been collected and its text independently confirms it."
        ),
        "ta": (
            "'Declared licence' என்பது ஒரு provider அல்லது dataset-இன் metadata "
            "*claim* செய்யும் licence -- இது provider-declared தகவல் மட்டுமே, "
            "verified fact அல்ல. உண்மையான licence evidence (ஒரு licence file அல்லது "
            "licence page) சேகரிக்கப்பட்டு, அதன் text சுயேச்சையாக இதை உறுதிப்படுத்தும் "
            "போது மட்டுமே இது 'verified' ஆகும்."
        ),
    },
    "why_is_provider_licence_not_enough": {
        "keywords": ("provider licence not enough", "provider license not enough"),
        "en": (
            "Provider-level or repository-level licence metadata is never treated as proof "
            "that every file in the dataset actually uses that licence -- it can be wrong, "
            "outdated, or simply not apply to every file. Only the dataset's own licence "
            "evidence (its licence file/page text) can move a case's licence_status to "
            "'verified'."
        ),
        "ta": (
            "Provider-level அல்லது repository-level licence metadata, dataset-இன் "
            "ஒவ்வொரு file-உம் அந்த licence-ஐயே பயன்படுத்துகிறது என்பதற்கு proof ஆக "
            "ஒருபோதும் கருதப்படாது -- இது தவறாக இருக்கலாம், பழையதாக இருக்கலாம், "
            "அல்லது எல்லா files-க்கும் பொருந்தாமல் இருக்கலாம். dataset-இன் சொந்த licence "
            "evidence (அதன் licence file/page text) மட்டுமே case-இன் licence_status-ஐ "
            "'verified' ஆக மாற்ற முடியும்."
        ),
    },
    "why_is_commercial_permission_separate": {
        "keywords": ("commercial permission separate", "why is commercial"),
        "en": (
            "Training permission and commercial permission are structurally independent -- "
            "a dataset being suitable for training never automatically means commercial use "
            "is allowed. Commercial use is always assessed on its own, requires an explicit "
            "intended-use category, and can never be automatically set to 'likely_allowed' "
            "by the system -- only an Admin's own reviewed decision can approve it."
        ),
        "ta": (
            "Training permission-உம் commercial permission-உம் structurally independent -- "
            "ஒரு dataset training-க்கு பொருந்தும் என்பது commercial use அனுமதிக்கப்பட்டது "
            "என்று ஒருபோதும் பொருள் தராது. Commercial use எப்போதும் தனியாக assess "
            "செய்யப்படும், ஒரு வெளிப்படையான intended-use category தேவை, மேலும் system "
            "இதை ஒருபோதும் தானாக 'likely_allowed' என அமைக்காது -- Admin-இன் சொந்த "
            "reviewed முடிவு மட்டுமே இதை approve செய்ய முடியும்."
        ),
    },
    "why_is_upstream_verification_required": {
        "keywords": ("upstream source verification", "upstream verification", "why is upstream"),
        "en": (
            "A dataset that aggregates or derives from other sources can only be as trusted "
            "as its weakest upstream source. While any linked upstream source remains "
            "unverified, this dataset's own training and commercial permissions stay capped "
            "at needs_legal_review -- they can never reach an automated 'likely_allowed', "
            "let alone an Admin approval, until upstream rights are resolved."
        ),
        "ta": (
            "மற்ற sources-இலிருந்து aggregate அல்லது derive செய்யப்படும் ஒரு dataset, "
            "அதன் மிகவும் பலவீனமான upstream source அளவுக்கே நம்பகமானதாக இருக்கும். "
            "linked upstream source ஏதேனும் unverified ஆக இருக்கும் வரை, இந்த dataset-இன் "
            "சொந்த training மற்றும் commercial permissions needs_legal_review-இல் "
            "கட்டுப்படுத்தப்படும் -- upstream rights தீர்க்கப்படும் வரை இவை automated "
            "'likely_allowed'-ஐ ஒருபோதும் எட்டாது, Admin approval-ஐ பற்றி சொல்லவே வேண்டாம்."
        ),
    },
    "why_is_dataset_card_insufficient": {
        "keywords": ("dataset card insufficient", "dataset card enough", "why is a dataset card"),
        "en": (
            "A dataset card is official supporting evidence, not the licence text itself -- "
            "it sits below a dedicated licence file/page in the evidence-authority hierarchy. "
            "If a dataset card's licence field conflicts with the actual licence file, the "
            "licence file (higher authority) is never silently overridden, and the conflict "
            "is recorded, not hidden."
        ),
        "ta": (
            "Dataset card ஒரு official supporting evidence மட்டுமே, licence text அதுவே "
            "அல்ல -- இது evidence-authority hierarchy-இல் ஒரு dedicated licence file/page-க்கு "
            "கீழே வருகிறது. ஒரு dataset card-இன் licence field, உண்மையான licence file-உடன் "
            "முரண்பட்டால், licence file (உயர் authority) ஒருபோதும் மௌனமாக override "
            "செய்யப்படாது, மேலும் conflict மறைக்கப்படாமல் பதிவு செய்யப்படும்."
        ),
    },
    "what_does_approved_with_conditions_mean": {
        "keywords": ("approved_with_conditions", "approved with conditions"),
        "en": (
            "'approved_with_conditions' means an Admin has explicitly approved this "
            "permission, but only subject to specific conditions recorded alongside the "
            "review (e.g. attribution required, non-commercial only). It is not a full, "
            "unconditional approval -- the recorded conditions must still be honored."
        ),
        "ta": (
            "'approved_with_conditions' என்றால், ஒரு Admin இந்த permission-ஐ "
            "வெளிப்படையாக approve செய்துள்ளார், ஆனால் review-உடன் பதிவு செய்யப்பட்ட "
            "குறிப்பிட்ட conditions-க்கு உட்பட்டு மட்டுமே (எ.கா. attribution தேவை, "
            "non-commercial மட்டும்). இது முழுமையான, நிபந்தனையற்ற approval அல்ல -- "
            "பதிவு செய்யப்பட்ட conditions இன்னும் கடைபிடிக்கப்பட வேண்டும்."
        ),
    },
    "what_happens_if_terms_change": {
        "keywords": ("terms change", "if terms change", "licence changes", "licence change"),
        "en": (
            "Licence and terms are re-checked lazily -- either on an explicit Admin-triggered "
            "reverify, or when a withdrawal notice is recorded. If the referenced evidence's "
            "checksum has changed, the case is marked 'source_changed' and every prior "
            "Admin-approved permission on it is automatically demoted back to "
            "needs_legal_review -- a changed source is never silently kept trusted."
        ),
        "ta": (
            "Licence மற்றும் terms lazy ஆக மீண்டும் சரிபார்க்கப்படும் -- ஒரு "
            "வெளிப்படையான Admin-triggered reverify மூலமாக, அல்லது ஒரு withdrawal "
            "notice பதிவு செய்யப்படும் போது. referenced evidence-இன் checksum "
            "மாறியிருந்தால், case 'source_changed' எனக் குறிக்கப்பட்டு, அதன் மீதான "
            "முந்தைய Admin-approved permissions அனைத்தும் தானாக needs_legal_review-க்கு "
            "தாழ்த்தப்படும் -- மாறிய source ஒருபோதும் மௌனமாக நம்பப்படாது."
        ),
    },
    "why_cant_the_dataset_be_downloaded_yet": {
        "keywords": (
            "download the dataset", "can't be downloaded", "cannot be downloaded",
            "be downloaded yet", "dataset be downloaded",
        ),
        "en": (
            "Dataset verification is not sample import approval -- they are structurally "
            "separate. This phase only ever produces an evidence-backed verification record; "
            "it never downloads a dataset payload file, imports records, activates RAG, "
            "creates a training dataset version, starts training, or releases a model. "
            "Those are all separate, later approval gates."
        ),
        "ta": (
            "Dataset verification என்பது sample import approval அல்ல -- இவை "
            "structurally தனித்தனியானவை. இந்த phase எப்போதும் evidence-backed "
            "verification record-ஐ மட்டுமே உருவாக்கும்; இது ஒருபோதும் dataset payload "
            "file-ஐ download செய்யாது, records-ஐ import செய்யாது, RAG-ஐ activate "
            "செய்யாது, training dataset version உருவாக்காது, training தொடங்காது, "
            "அல்லது model release செய்யாது. இவை அனைத்தும் தனித்தனி, பிற்கால approval "
            "gates."
        ),
    },
}


def match_dataset_verification_question(message: str) -> str | None:
    """Returns the matching FAQ key for a message, or `None`. Matches
    the longest keyword found so a more specific phrase always wins
    over an accidental shorter substring match."""

    message_lower = message.lower()
    best_key: str | None = None
    best_length = 0
    for key, entry in DATASET_VERIFICATION_FAQ.items():
        for keyword in entry["keywords"]:
            if keyword in message_lower and len(keyword) > best_length:
                best_key = key
                best_length = len(keyword)
    return best_key
