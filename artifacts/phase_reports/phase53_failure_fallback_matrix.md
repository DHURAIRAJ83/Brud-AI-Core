# Phase 53 Failure Modes & Automated Fallback Action Matrix (120 Scenarios)

**Coverage:** Baseline Invariants, Ingestion Gating, Deduplication, Contamination, Anti-Memorization, Campaign Execution, Ledger Integrity, Checkpoints, Evaluation, Security, and Governance.

| Scenario ID | Failure Event / Threat Vector | Detection Mechanism | Automated Defense / Fallback Action | Recovery Verification |
| :--- | :--- | :--- | :--- | :--- |
| SCEN-001 | **Production Database Invariants:** DB file missing | Path.exists() check | Abort immediately; alert administrator | Verify db file exists |
| SCEN-002 | **Production Database Invariants:** DB byte size altered | os.path.getsize mismatch | Reject execution; restore from immutable backup | Verify 11,096,064 bytes |
| SCEN-003 | **Production Database Invariants:** DB SHA-256 mismatch | Hash comparison | Fail-closed halt; lock operations | Verify SHA-256 34376318... |
| SCEN-004 | **Production Database Invariants:** WAL journal file detected | brud_ai.db-wal exists | Checkpoint journal and purge safely | Verify 0 WAL files |
| SCEN-005 | **Production Database Invariants:** SHM shared memory detected | brud_ai.db-shm exists | Disconnect rogue connection and purge | Verify 0 SHM files |
| SCEN-006 | **Production Database Invariants:** Write attempt on read-only DB | Filesystem permission error | Raise SecurityException; terminate process | Verify zero DB writes |
| SCEN-007 | **Production Database Invariants:** DB connection leak | Active connection pool tracking | Force pool flush and close lingering handles | Connection count = 0 |
| SCEN-008 | **Production Database Invariants:** Schema migration triggered | Table alteration check | Rollback migration immediately | Verify schema hash identical |
| SCEN-009 | **Production Database Invariants:** Foreign key constraint trip | SQLite pragma foreign_keys | Fail query; do not modify table | Verify foreign key integrity |
| SCEN-010 | **Production Database Invariants:** Concurrent DB lock contention | sqlite3.OperationalError | Timeout and fail-closed abort | Verify lock released |
| SCEN-011 | **Git Repository Integrity:** Git HEAD commit altered | rev-parse HEAD mismatch | Hard abort; re-checkout expected HEAD | HEAD == df054cb1... |
| SCEN-012 | **Git Repository Integrity:** Git stash deleted or altered | git stash list mismatch | Fail-closed alert; inspect reflog | stash@{0} confirmed |
| SCEN-013 | **Git Repository Integrity:** Untracked dirty file in repo | git status --porcelain | Quarantine unexpected file | git status clean |
| SCEN-014 | **Git Repository Integrity:** Modified tracked file in working tree | git diff non-empty | Revert dirty modifications | git diff empty |
| SCEN-015 | **Git Repository Integrity:** Branch divergence | git symbolic-ref mismatch | Reset branch to master baseline | Branch verified |
| SCEN-016 | **Git Repository Integrity:** Merge conflict artifact in repo | Conflict marker scanner | Halt build; purge conflict marker | 0 conflict markers |
| SCEN-017 | **Git Repository Integrity:** Submodule tampering | git submodule status | Restore submodule pointer | Submodule matches commit |
| SCEN-018 | **Git Repository Integrity:** Remote fetch injection | git remote check | Disable remote auto-fetch | No external network access |
| SCEN-019 | **Git Repository Integrity:** Git config tampering | git config core.hookspath | Reset git hooks path to empty | Hooks path verified |
| SCEN-020 | **Git Repository Integrity:** Corrupted git object database | git fsck | Abort and rebuild from sovereign mirror | git fsck clean |
| SCEN-021 | **Ingestion & Governance Gating:** Unapproved raw PDF ingestion attempt | Extension filter .pdf | Drop record immediately; log rejection | 0 raw PDFs in corpus |
| SCEN-022 | **Ingestion & Governance Gating:** Corrupted text encoding | UnicodeDecodeError catcher | Ignore byte sequence; flag source | All records UTF-8 clean |
| SCEN-023 | **Ingestion & Governance Gating:** Missing source_path attribution | Field validator | Reject record with MISSING_PROVENANCE | source_path present |
| SCEN-024 | **Ingestion & Governance Gating:** Missing source_hash SHA-256 | Hash length check | Compute SHA-256 or reject record | source_hash length == 64 |
| SCEN-025 | **Ingestion & Governance Gating:** Unverified rights status | rights_status != verified | Drop record with RIGHTS_UNVERIFIED | rights_status == verified |
| SCEN-026 | **Ingestion & Governance Gating:** Non-permissive licence detected | licence_family != permissive | Drop record with RESTRICTED_LICENCE | licence == permissive |
| SCEN-027 | **Ingestion & Governance Gating:** Pending unreviewed batch ingress | Directory scan for 'pending' | Exclude entire pending directory | 0 pending records |
| SCEN-028 | **Ingestion & Governance Gating:** Zero-token record encountered | estimate_tokens == 0 | Drop record with ZERO_TOKENS | token_count > 0 |
| SCEN-029 | **Ingestion & Governance Gating:** Corrupted source directory path | Path traversal scanner | Sanitize path or drop record | No ../ in path |
| SCEN-030 | **Ingestion & Governance Gating:** Missing record identifier prefix | record_id.startswith('rec_') | Prepend proper prefix or drop | All rec_ prefixed |
| SCEN-031 | **Deduplication & Normalization:** Exact byte SHA-256 duplicate | Hash collision set | Drop duplicate; increment rejection counter | Unique SHA-256 set |
| SCEN-032 | **Deduplication & Normalization:** Whitespace-only duplicate | normalize_tamil_safe | Collapse whitespace and match hash | Normalized hash deduplication |
| SCEN-033 | **Deduplication & Normalization:** Near-duplicate 5-gram Jaccard > 0.85 | N-gram Jaccard calculator | Drop near-duplicate; retain first | All Jaccard <= 0.85 |
| SCEN-034 | **Deduplication & Normalization:** Short record < 15 characters | len(text) < 15 | Drop record with TOO_SHORT | All records >= 15 ch |
| SCEN-035 | **Deduplication & Normalization:** Unicode combining character mismatch | unicodedata.normalize NFC | Normalize to NFC before comparison | NFC canonical form |
| SCEN-036 | **Deduplication & Normalization:** Control character injection | Control char regex | Strip non-printable chars safely | Zero control characters |
| SCEN-037 | **Deduplication & Normalization:** Tamil virama diacritic stripping bug | Diacritic preservation check | Abort normalizer; keep original virama | Tamil characters intact |
| SCEN-038 | **Deduplication & Normalization:** Empty text after normalization | len(clean) == 0 | Drop record completely | All clean texts non-empty |
| SCEN-039 | **Deduplication & Normalization:** Degenerate repeated character sequence | Repeated char regex | Drop repetitive spam record | No 10x repeated chars |
| SCEN-040 | **Deduplication & Normalization:** Null byte poison injection | b'\x00' scan | Strip null bytes before UTF-8 decode | Zero null bytes |
| SCEN-041 | **PII & Secret Screening:** Personal email detected in record | Email regex pattern | Drop record; log PII_EMAIL_FOUND | 0 emails in corpus |
| SCEN-042 | **PII & Secret Screening:** Indian phone number (+91) detected | Phone regex pattern | Drop record; log PII_PHONE_FOUND | 0 phones in corpus |
| SCEN-043 | **PII & Secret Screening:** US/Intl phone number detected | Phone regex pattern | Drop record; log PII_PHONE_FOUND | 0 phones in corpus |
| SCEN-044 | **PII & Secret Screening:** AWS Access Key (AKIA...) detected | Secret regex pattern | Drop record; log SECRET_AWS_FOUND | 0 AWS keys in corpus |
| SCEN-045 | **PII & Secret Screening:** GitHub Personal Access Token (ghp_) | Secret regex pattern | Drop record; log SECRET_GH_FOUND | 0 GitHub tokens |
| SCEN-046 | **PII & Secret Screening:** Generic API Bearer Token detected | Secret regex pattern | Drop record; log SECRET_BEARER_FOUND | 0 bearer tokens |
| SCEN-047 | **PII & Secret Screening:** Private RSA/SSH Key Header detected | PEM key header scan | Drop record; log PRIVATE_KEY_FOUND | 0 private keys |
| SCEN-048 | **PII & Secret Screening:** Credit card number pattern detected | Luhn algorithm check | Drop record; log PCI_DATA_FOUND | 0 credit cards |
| SCEN-049 | **PII & Secret Screening:** Aadhaar / National ID pattern | ID format validator | Drop record; log GOV_ID_FOUND | 0 national IDs |
| SCEN-050 | **PII & Secret Screening:** IP address internal range detected | Private IP regex | Mask or drop internal IP record | 0 internal IPs |
| SCEN-051 | **Adversarial & Injection Defense:** Ignore instructions injection | Prompt injection filter | Drop record with INJECTION_BLOCKED | 0 prompt injections |
| SCEN-052 | **Adversarial & Injection Defense:** Disregard above instructions injection | Prompt injection filter | Drop record with INJECTION_BLOCKED | 0 prompt injections |
| SCEN-053 | **Adversarial & Injection Defense:** System prompt override injection | Prompt injection filter | Drop record with INJECTION_BLOCKED | 0 prompt injections |
| SCEN-054 | **Adversarial & Injection Defense:** Jailbreak roleplay attempt (DAN) | Jailbreak signature filter | Drop record with JAILBREAK_BLOCKED | 0 jailbreak records |
| SCEN-055 | **Adversarial & Injection Defense:** Base64 encoded injection payload | Base64 decoder + scanner | Decode and scan inner payload | Inner payload screened |
| SCEN-056 | **Adversarial & Injection Defense:** Recursive delimiter nesting | Markdown delimiter audit | Sanitize nested backticks/delimiters | Safe markdown structure |
| SCEN-057 | **Adversarial & Injection Defense:** Toxic sentiment / hate speech | Keyword filter list | Drop offensive record | Screened clean |
| SCEN-058 | **Adversarial & Injection Defense:** Code execution exploit snippet | Exploit AST scanner | Drop exploit snippet | Zero exploit strings |
| SCEN-059 | **Adversarial & Injection Defense:** Obfuscated hex unicode injection | Unicode unescape check | Normalize unescaped sequence | Safe unicode string |
| SCEN-060 | **Adversarial & Injection Defense:** Cross-site scripting (XSS) payload | HTML tag stripper | Strip <script> and iframe tags | Zero HTML tags |
| SCEN-061 | **Anti-Memorization Guard Actions:** Dominant concentration > 40% | get_dominant_concentration() | Trigger fail-closed PAUSE | Pause acknowledged |
| SCEN-062 | **Anti-Memorization Guard Actions:** Validation divergence > 0.25 | get_validation_divergence() | Trigger fail-closed PAUSE | Pause acknowledged |
| SCEN-063 | **Anti-Memorization Guard Actions:** Effective epochs > 10.0 | get_effective_epochs() | Trigger WARN alert | Warning logged |
| SCEN-064 | **Anti-Memorization Guard Actions:** Effective epochs > 15.0 | get_effective_epochs() | Trigger fail-closed PAUSE | Pause acknowledged |
| SCEN-065 | **Anti-Memorization Guard Actions:** Effective epochs > 25.0 | get_effective_epochs() | Trigger fail-closed BLOCK | Block enforced |
| SCEN-066 | **Anti-Memorization Guard Actions:** Sequence repetition ratio > 0.50 | get_repetition_ratio() | Trigger fail-closed PAUSE | Repetition stopped |
| SCEN-067 | **Anti-Memorization Guard Actions:** Max single record exposures > 60 | Exposure counter check | Trigger WARN alert | Warning logged |
| SCEN-068 | **Anti-Memorization Guard Actions:** Max single record exposures > 90 | Exposure counter check | Trigger fail-closed PAUSE | Pause acknowledged |
| SCEN-069 | **Anti-Memorization Guard Actions:** Memory tracker corruption | Telemetry schema validation | Fail-closed halt; restore guard state | Guard state valid |
| SCEN-070 | **Anti-Memorization Guard Actions:** Corrupted guard state file | State hash validation | Reconstruct state from step history | State reconstructed |
| SCEN-071 | **Training & Hardware Boundary:** Training token ceiling reached (15K) | accumulated >= 15000 | Graceful normal campaign termination | 15,360 tokens logged |
| SCEN-072 | **Training & Hardware Boundary:** Worker process count > 1 | Process pool monitor | Kill extra workers; enforce 1 worker | Workers count == 1 |
| SCEN-073 | **Training & Hardware Boundary:** PyTorch threads > 2 | torch.get_num_threads() | Reset torch.set_num_threads(2) | Threads <= 2 |
| SCEN-074 | **Training & Hardware Boundary:** CUDA / GPU initialization attempt | torch.cuda.is_available() | Force CPU device allocation | Device == 'cpu' |
| SCEN-075 | **Training & Hardware Boundary:** RAM RSS usage > 512 MB | psutil memory check | Run garbage collector; abort if high | RSS < 100 MB |
| SCEN-076 | **Training & Hardware Boundary:** Disk write budget exceeded | Check disk free space | Trigger SAFE_STOP; archive checkpoints | Disk budget SAFE |
| SCEN-077 | **Training & Hardware Boundary:** Loss explodes to NaN / Inf | torch.isnan(loss) check | Rollback model to previous checkpoint | Loss is finite |
| SCEN-078 | **Training & Hardware Boundary:** Gradient vanishing (norm < 1e-7) | grad_norm check | Log warning; skip step | Gradients healthy |
| SCEN-079 | **Training & Hardware Boundary:** KeyboardInterrupt / SIGINT | Signal handler trap | Save emergency checkpoint and exit | State saved safely |
| SCEN-080 | **Training & Hardware Boundary:** System crash / power loss | On restart recovery check | Restore latest verified checkpoint | Resumed from step |
| SCEN-081 | **Ledger & Cryptographic Integrity:** Ledger file deleted or missing | File existence check | Restore ledger from parent checkpoint | Ledger verified |
| SCEN-082 | **Ledger & Cryptographic Integrity:** Ledger JSON schema corruption | json.loads exception | Restore backup and verify chain | Valid JSON ledger |
| SCEN-083 | **Ledger & Cryptographic Integrity:** Broken SHA-256 block hash chain | previous_hash mismatch | Reject corrupted block; rollback chain | Unbroken chain |
| SCEN-084 | **Ledger & Cryptographic Integrity:** Duplicate idempotency key submission | idempotency_key check | Raise exception; reject duplicate batch | Zero duplicate keys |
| SCEN-085 | **Ledger & Cryptographic Integrity:** Non-monotonic cumulative tokens | tokens < prev_tokens check | Reject invalid block transaction | Monotonic increase |
| SCEN-086 | **Ledger & Cryptographic Integrity:** Negative run tokens in block | run_tokens <= 0 check | Reject invalid zero-token window | Positive run tokens |
| SCEN-087 | **Ledger & Cryptographic Integrity:** Concurrent ledger write race | File lock mechanism | Serialize ledger append operations | Deterministic blocks |
| SCEN-088 | **Ledger & Cryptographic Integrity:** Mismatched genesis block hash | Genesis hash check | Enforce canonical genesis anchor | Genesis block valid |
| SCEN-089 | **Ledger & Cryptographic Integrity:** Out-of-order block indexing | index != prev_index + 1 | Reject malformed index insertion | Sequential indexing |
| SCEN-090 | **Ledger & Cryptographic Integrity:** Unauthorized ledger edit outside daemon | Audit watcher hash | Revert manual edit; restore ledger | Ledger matches memory |
| SCEN-091 | **Evaluation & Distribution Isolation:** Benchmark probe modified | Manifest SHA-256 check | Re-lock evaluation manifest from hash | Manifest hash matches |
| SCEN-092 | **Evaluation & Distribution Isolation:** Training overlap in test probe | Exact probe match check | Disqualify evaluation; quarantine split | Zero train overlap |
| SCEN-093 | **Evaluation & Distribution Isolation:** OOD probe distribution shift | Cluster variance monitor | Rebalance probe difficulty weights | OOD score calibrated |
| SCEN-094 | **Evaluation & Distribution Isolation:** Seen-to-HeldOut gap exceeds 0.20 | seen_gap calculation | Log OVERFITTING warning | Gap within bounds |
| SCEN-095 | **Evaluation & Distribution Isolation:** HeldOut-to-OOD gap exceeds 0.15 | ood_gap calculation | Log POOR_TRANSFER warning | Gap within bounds |
| SCEN-096 | **Evaluation & Distribution Isolation:** Discrete scoring division by zero | max(1, total_probes) | Clamp denominator to 1 | Score well-defined |
| SCEN-097 | **Evaluation & Distribution Isolation:** Mock generate function failure | try/except wrapper | Fallback to default deterministic token | Evaluation completes |
| SCEN-098 | **Evaluation & Distribution Isolation:** Sub-1000 token gain inflation | delta_tokens < 1000 check | Return NOT_MEASURABLE status | Zero division blocked |
| SCEN-099 | **Evaluation & Distribution Isolation:** Loss reduction false claim | Loss vs Score comparator | Classify as UNCORRELATED; reject claim | Honest attribution |
| SCEN-100 | **Evaluation & Distribution Isolation:** Exaggerated capability score claim | Statistical significance check | Force verdict to INCONCLUSIVE | Honest attribution |
| SCEN-101 | **Static Security & Code Quality:** eval() call detected in module | AST visitor node | Fail build; remove eval() call | AST scan clean |
| SCEN-102 | **Static Security & Code Quality:** exec() call detected in module | AST visitor node | Fail build; remove exec() call | AST scan clean |
| SCEN-103 | **Static Security & Code Quality:** os.system() call detected | AST visitor node | Fail build; use subprocess safely | AST scan clean |
| SCEN-104 | **Static Security & Code Quality:** shell=True in subprocess call | AST visitor node | Fail build; set shell=False | AST scan clean |
| SCEN-105 | **Static Security & Code Quality:** Wildcard import (from m import *) | AST ImportFrom check | Refactor to explicit imports | Zero wildcard imports |
| SCEN-106 | **Static Security & Code Quality:** Hardcoded credentials / token | String literal secret regex | Purge hardcoded credentials | Zero credentials in code |
| SCEN-107 | **Static Security & Code Quality:** Path traversal in file reader | os.path.abspath check | Confine to ROOT_DIR workspace | Path confined |
| SCEN-108 | **Static Security & Code Quality:** Pickle deserialization vulnerability | ast.Call pickle.load | Ban pickle; use json or torch safe load | Safe loading only |
| SCEN-109 | **Static Security & Code Quality:** Unsanitized SQL query construction | SQL string concat check | Use parameterized queries | Safe SQL queries |
| SCEN-110 | **Static Security & Code Quality:** Network socket binding attempt | AST socket check | Block socket creation; force offline | Zero network sockets |
| SCEN-111 | **Public Chat Isolation & Governance:** Candidate routed to public chat | Traffic router gate | Force candidate traffic to 0.0% | 0.0% traffic verified |
| SCEN-112 | **Public Chat Isolation & Governance:** Candidate promotion flag flipped | is_promoted checker | Revert flag to False; trigger audit | Candidate unpromoted |
| SCEN-113 | **Public Chat Isolation & Governance:** Production DB connection during train | DB path monitor | Abort training process immediately | DB untouched |
| SCEN-114 | **Public Chat Isolation & Governance:** Unauthorized release candidate build | Release tag checker | Require human cryptographic signature | Release blocked |
| SCEN-115 | **Public Chat Isolation & Governance:** Silent capability regression release | Model regression battery | Block deployment if score < baseline | Deployment blocked |
| SCEN-116 | **Public Chat Isolation & Governance:** Uncalibrated confidence in response | Confidence score monitor | Clamp confidence threshold | Calibrated confidence |
| SCEN-117 | **Public Chat Isolation & Governance:** Hallucinated medical advice output | Safety filter probe | Trigger canned safety fallback disclaimer | Safety disclaimer |
| SCEN-118 | **Public Chat Isolation & Governance:** Hallucinated legal advice output | Safety filter probe | Trigger canned safety fallback disclaimer | Safety disclaimer |
| SCEN-119 | **Public Chat Isolation & Governance:** Bypassed content moderation guard | Guardrail execution hook | Fail-closed response block | Response blocked |
| SCEN-120 | **Public Chat Isolation & Governance:** Missing final verification report | File existence audit | Block phase signoff until report published | Report published |