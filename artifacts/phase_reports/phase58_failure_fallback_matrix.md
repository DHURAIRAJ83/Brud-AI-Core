# Phase 58 Failure & Fallback Matrix

**Workstream:** 19 — Failure / Fallback Matrix  
**Timestamp:** 2026-08-30T18:25:00Z  
**Status:** ✅ 180 SCENARIOS SPECIFIED ACROSS 6 OPERATIONAL CATEGORIES

---

## 1. Executive Summary

This matrix establishes defensive detection mechanisms, fallback protocols, and safe final states for **180 realistic failure modes** spanning Tokenizer, Model, Data, Security, Infrastructure, and Governance boundaries.

---

## TOKENIZER Failure Scenarios (30 Scenarios)

| ID | Specific Failure Mode | Detection Mechanism | Defensive Protocol | Fallback Action | Safe Final State |
|---|---|---|---|---|---|
| `FAIL-TOK-001` | Corrupted tokenizer model file | sp.Load() raises runtime error or CRC failure | Verify file SHA-256 against phase58_tokenizer_v2_manifest.json | Restore from immutable git or backup store | **Validated v2 tokenizer model** |
| `FAIL-TOK-002` | Vocabulary size mismatch | sp.GetPieceSize() != 1024 | Check size during initialization hook | Fail closed; reject model loading | **Guaranteed 1024-token vocabulary** |
| `FAIL-TOK-003` | Duplicate piece entry in vocab | len(set(vocab)) < len(vocab) | Hash table unique piece assertion on load | Rebuild tokenizer with unique vocabulary guarantee | **Strictly bijective piece mapping** |
| `FAIL-TOK-004` | Missing special token <pad> | sp.pad_id() == -1 or != 0 | Inspect special token registry index 0 | Fail closed; require pad_id=0 | **Canonical pad token mapped** |
| `FAIL-TOK-005` | Missing special token <unk> | sp.unk_id() == -1 or != 1 | Inspect special token registry index 1 | Fail closed; require unk_id=1 | **Canonical unk token mapped** |
| `FAIL-TOK-006` | Missing special token <s> | sp.bos_id() == -1 or != 2 | Inspect special token registry index 2 | Fail closed; require bos_id=2 | **Canonical bos token mapped** |
| `FAIL-TOK-007` | Missing special token </s> | sp.eos_id() == -1 or != 3 | Inspect special token registry index 3 | Fail closed; require eos_id=3 | **Canonical eos token mapped** |
| `FAIL-TOK-008` | Special token ID collision | pad_id == unk_id or bos_id == eos_id | Check pairwise distinctness of indices 0..10 | Halt startup; regenerate special token registry | **Disjoint special token IDs** |
| `FAIL-TOK-009` | Byte fallback disabled | byte_fallback flag in config is False | Check config byte_fallback field | Re-train SentencePiece with byte_fallback=True | **Zero UNK byte fallback guarantee** |
| `FAIL-TOK-010` | Tamil Uyirmei diacritic detachment | Unicode pulli forms orphan token without consonant | Round-trip assertion on standard uyirmei | Apply NFKC normalization pre-tokenization | **Preserved grapheme integrity** |
| `FAIL-TOK-011` | English lowercase character omission | Any of a-z produces UNK ID 1 | Audit tokenization of lowercase alphabet | Ensure 100% character coverage in training spec | **Zero English UNK** |
| `FAIL-TOK-012` | English uppercase character omission | Any of A-Z produces UNK ID 1 | Audit tokenization of uppercase alphabet | Fallback to byte tokens for rare uppercase chars | **Zero English UNK** |
| `FAIL-TOK-013` | Numeric digit omission | Any of 0-9 produces UNK ID 1 | Audit tokenization of digits 0-9 | Verify all digits natively indexed | **Zero numeric UNK** |
| `FAIL-TOK-014` | Math symbol omission | Operators (+, -, *, /) produce UNK | Encode arithmetic test sentence | Byte fallback handles unindexed operators | **Zero math operator UNK** |
| `FAIL-TOK-015` | Whitespace collapse failure | Multiple spaces corrupted into single byte | Verify SentencePiece dummy whitespace prefix ▁ | Enforce treat_whitespace_as_suffix=False | **Lossless whitespace semantics** |
| `FAIL-TOK-016` | Newline stripping failure | Newlines stripped without delimiter | Decode assertion on multi-line text | Map newlines to standard separator or explicit piece | **Structured layout preservation** |
| `FAIL-TOK-017` | Empty string tokenization crash | sp.Encode('') throws exception | Unit test on empty input | Return empty list [] | **Graceful empty handling** |
| `FAIL-TOK-018` | Excessively long token string (>4096) | Tokenizer buffer overflow or hang | Length check before encoding | Truncate or chunk at context boundary | **Bounded sequence length** |
| `FAIL-TOK-019` | Control token spoofing in user text | User text contains raw '<system>' string | Check whether user symbols are tokenized as special IDs | Set enable_user_defined_symbols=False during inference | **Prompt injection blocked** |
| `FAIL-TOK-020` | UTF-8 encoding validation failure | Malformed non-UTF-8 byte sequence passed | Python utf-8 decode validation before SentencePiece | Replace or reject invalid bytes with error handler | **Clean UTF-8 stream** |
| `FAIL-TOK-021` | Grantha script corruption | Grantha characters (ஸ்ரீ, க்ஷ்) decode incorrectly | Round-trip Grantha test battery | Native piece indexing + byte fallback | **Preserved cultural script** |
| `FAIL-TOK-022` | Tamil numerals corruption | Classical numerals (௧, ௨, ௩) produce UNK | Audit classical numerals in corpus | Verify presence in vocabulary inventory | **Preserved Tamil heritage text** |
| `FAIL-TOK-023` | Bilingual boundary glitch | Code-switched word boundaries merged awkwardly | Test Tanglish 'naan veetuku poren' | SentencePiece whitespace preservation | **Clean code-switching** |
| `FAIL-TOK-024` | Punctuation paired inversion | Open parenthesis '(' decoded as ')' | Round-trip assertion on paired punctuation | Exact piece-level decode verification | **Correct bracket structure** |
| `FAIL-TOK-025` | Emoji byte flood | Long emoji string consumes context | Count byte pieces generated per emoji | Cap byte fallback sequence length | **Context window protected** |
| `FAIL-TOK-026` | Unknown byte piece ID out of range | Piece ID outside 0..1023 returned | Assert all token IDs < vocab_size | Clamp or drop out-of-bound IDs | **Strict array boundary safety** |
| `FAIL-TOK-027` | Tokenizer config file missing | tokenizer_config.json deleted or absent | Startup file existence assertion | Regenerate from tokenizer metadata template | **Complete configuration artifact** |
| `FAIL-TOK-028` | Special token registry missing | special_token_registry.json missing | Startup check | Regenerate from tokenizer.model inspection | **Registry available** |
| `FAIL-TOK-029` | Vocab inventory hash mismatch | Inventory does not match tokenizer.model pieces | Compute SHA-256 of piece list | Rebuild inventory from live model | **Synchronized vocabulary inventory** |
| `FAIL-TOK-030` | Model file truncate corruption | Incomplete file copy of tokenizer.model | Check stat().st_size == expected_bytes | Re-copy from immutable artifact directory | **Valid model binary** |

## MODEL Failure Scenarios (30 Scenarios)

| ID | Specific Failure Mode | Detection Mechanism | Defensive Protocol | Fallback Action | Safe Final State |
|---|---|---|---|---|---|
| `FAIL-MOD-031` | Embedding matrix row count mismatch | embedding.weight.shape[0] != 1024 | Model init dimension assertion | Re-instantiate model with vocab_size=1024 | **Exact tensor matching** |
| `FAIL-MOD-032` | LM head row count mismatch | fc_out.weight.shape[0] != 1024 | Model init dimension assertion | Re-instantiate LM head with out_features=1024 | **Exact tensor matching** |
| `FAIL-MOD-033` | LM head bias length mismatch | fc_out.bias.shape[0] != 1024 | Model init dimension assertion | Re-instantiate LM head bias | **Exact tensor matching** |
| `FAIL-MOD-034` | Hidden dimension mismatch | embedding.weight.shape[1] != 128 | Check d_model configuration | Ensure all sub-layers use d_model=128 | **Consistent hidden dimension** |
| `FAIL-MOD-035` | Attention head dimension non-integer | d_model % nhead != 0 | Check 128 % 4 == 0 | Enforce head dimension = d_model // nhead | **Integer head dimension (32)** |
| `FAIL-MOD-036` | Context length overflow | Sequence length > 128 passed to forward | Tensor shape check at forward entry | Slice input tensor to [:128] | **Strict context capping** |
| `FAIL-MOD-037` | Legacy checkpoint load attempt | Attempting to load Phase 56 [128, 64] checkpoint | Catches size mismatch RuntimeError | Reject legacy weights; require Model v2 initialization | **Clean v2 weights** |
| `FAIL-MOD-038` | NaN loss during forward pass | torch.isnan(loss) == True | Loss finiteness assertion | Check for infinite logits; apply gradient zeroing | **Numerically stable loss** |
| `FAIL-MOD-039` | Inf gradient during backward pass | torch.isinf(grad).any() == True | Gradient norm clipping check | Skip optimizer step; clip gradients at 1.0 | **Bounded gradient updates** |
| `FAIL-MOD-040` | Zero gradient on embedding weights | embedding.weight.grad is None or all zeros | Gradient check after backward | Verify embedding requires_grad=True and token active in loss | **Active embedding learning** |
| `FAIL-MOD-041` | Zero gradient on attention weights | in_proj_weight.grad is all zeros | Inspect layer 0 & 1 self-attn grads | Check input masking does not block all tokens | **Active attention learning** |
| `FAIL-MOD-042` | Zero gradient on feed-forward weights | linear1.weight.grad is all zeros | Inspect FFN grads | Check activation function not dead | **Active FFN learning** |
| `FAIL-MOD-043` | Zero gradient on LM head weights | fc_out.weight.grad is all zeros | Inspect LM head grads | Check loss cross-entropy target alignment | **Active head learning** |
| `FAIL-MOD-044` | Causal mask future leakage | Upper triangular mask has finite values | Verify mask has -inf on upper triangle | Regenerate causal mask via generate_square_subsequent_mask | **Strict causality** |
| `FAIL-MOD-045` | Padding token gradient corruption | Pad tokens (ID 0) contribute to loss | Verify CrossEntropyLoss ignore_index=0 | Enforce ignore_index=0 in loss constructor | **Zero loss on padding** |
| `FAIL-MOD-046` | Unused vocabulary slot gradient leakage | Rare tokens receiving random updates | Monitor weight norms | L2 weight decay (0.01) regularizes rare slots | **Regularized weights** |
| `FAIL-MOD-047` | Exploding parameter norm | Weight norm increases exponentially | Track max weight tensor delta | Apply AdamW weight decay + grad clipping | **Bounded parameter norms** |
| `FAIL-MOD-048` | Vanishing learning rate | LR decays to 0 prematurely | Check scheduler schedule function | Enforce min_lr floor (1e-5) | **Sustained learning signal** |
| `FAIL-MOD-049` | Dropout during evaluation | model.eval() not called; non-deterministic logits | Assert not model.training during inference | Call model.eval() before evaluation | **Deterministic greedy output** |
| `FAIL-MOD-050` | Nested tensor warning in PyTorch | PyTorch warning when num_heads is odd or unnested | Configure nhead=4 (even power of 2) | Warning eliminated; efficient execution | **Clean runtime logs** |
| `FAIL-MOD-051` | Greedy decoding infinite loop | Model never emits EOS (ID 3) | Max token cap in generation loop | Break generation when step == max_new_tokens | **Guaranteed loop termination** |
| `FAIL-MOD-052` | Argmax tie breaking instability | Equal logit scores for top tokens | Check float precision | Deterministic torch.argmax() lowest index tie-break | **Deterministic inference** |
| `FAIL-MOD-053` | Model state dict key mismatch | Unexpected prefix in keys (e.g. 'module.') | Strip 'module.' from state_dict keys | Normalize keys to canonical architecture names | **Clean weight loading** |
| `FAIL-MOD-054` | CPU core affinity thrashing | PyTorch spawns too many threads on 2-core CPU | Set torch.set_num_threads(2) | Limit thread pool to physical core count | **Stable CPU throughput** |
| `FAIL-MOD-055` | CUDA call on CPU-only hardware | Code calls .cuda() or torch.cuda.is_available() | AST assertion against cuda calls | Enforce map_location='cpu' | **Strict CPU execution** |
| `FAIL-MOD-056` | Memory leak across batches | Tensors accumulating in computational graph | Detach loss before logging; opt.zero_grad(set_to_none=True) | Free intermediate activation tensors | **Constant memory usage** |
| `FAIL-MOD-057` | Optimizer state dict mismatch | Optimizer AdamW buffers incompatible with new model | Instantiate fresh optimizer instance | Discard legacy optimizer state | **Fresh AdamW moments** |
| `FAIL-MOD-058` | Model dtype precision drift | Model weights cast to float16 on CPU | Assert weight.dtype == torch.float32 | Enforce strict float32 on CPU | **Full numerical precision** |
| `FAIL-MOD-059` | LayerNorm epsilon underflow | Division by zero in LayerNorm standard deviation | Set eps=1e-5 in LayerNorm | Stable variance normalization | **Stable activations** |
| `FAIL-MOD-060` | Loss scale explosion on small batch | Loss multiplied by batch size incorrectly | CrossEntropyLoss reduction='mean' | Standard mean reduction | **Batch-invariant loss scale** |

## DATA Failure Scenarios (20 Scenarios)

| ID | Specific Failure Mode | Detection Mechanism | Defensive Protocol | Fallback Action | Safe Final State |
|---|---|---|---|---|---|
| `FAIL-DAT-061` | Phase 55 records file hash mismatch | SHA-256 != 3e1481c3... | Startup checksum audit | Halt execution; restore from immutable backup | **Authoritative corpus intact** |
| `FAIL-DAT-062` | Phase 55 record count mismatch | Record count != 396 | Line count check on JSONL | Halt execution; restore corpus | **Exact 396 records** |
| `FAIL-DAT-063` | Phase 55 Merkle root mismatch | Merkle root != 972b6fba... | Merkle tree recalculation | Halt execution; restore corpus | **Verified Merkle tree** |
| `FAIL-DAT-064` | Corrupted JSON line in corpus | json.loads() raises JSONDecodeError | JSON validation on load | Reject corrupted line; alert governance | **Valid JSON records** |
| `FAIL-DAT-065` | Empty text field in record | record['text'].strip() == '' | Text length assertion | Reject empty record | **Non-empty training data** |
| `FAIL-DAT-066` | Split leakage between train and val | record_id in train and val | Disjoint set check on record IDs | Enforce strict partition | **Zero train/val leakage** |
| `FAIL-DAT-067` | Split leakage between train and test | record_id in train and test | Disjoint set check on record IDs | Enforce strict partition | **Zero train/test leakage** |
| `FAIL-DAT-068` | Benchmark prompt in training corpus | Exact match between probe and training record | SHA-256 cross-check against benchmark | Remove contaminated record | **0.0% contamination** |
| `FAIL-DAT-069` | Benchmark answer in training corpus | Exact match of expected output in training text | Substring & exact hash screen | Remove contaminated record | **0.0% contamination** |
| `FAIL-DAT-070` | Malformed split tag in record | split not in ['train', 'val', 'validation', 'test'] | Split tag validation hook | Default to 'train' or quarantine record | **Well-defined data splits** |
| `FAIL-DAT-071` | Excessive token count in single record | Record exceeds 512 tokens | Pre-tokenization sequence length audit | Chunk record at sentence boundaries | **Bounded training blocks** |
| `FAIL-DAT-072` | Zero-token record after encoding | len(sp.EncodeAsIds(text)) == 0 | Filter out zero-length sequences | Skip record in dataloader | **Non-empty batch sequences** |
| `FAIL-DAT-073` | Unbalanced domain representation | Single domain exceeds 50% of tokens | Track domain histogram | Apply domain-balanced batch sampling | **Diverse domain exposure** |
| `FAIL-DAT-074` | Unverified rights record ingestion | rights_verified != True | Governance metadata audit | Quarantine unverified records | **100% verified rights** |
| `FAIL-DAT-075` | PII pattern detected in training text | Regex matches phone, email, SSN | Pre-training PII scanner hook | Redact PII before tokenizer encoding | **PII-clean corpus** |
| `FAIL-DAT-076` | Secret key detected in training text | Regex matches API keys, passwords | Pre-training secret scanner hook | Quarantine record immediately | **Secret-clean corpus** |
| `FAIL-DAT-077` | Encoding mismatch (non-UTF-8) | File contains non-UTF8 bytes | Open with encoding='utf-8' and strict error handling | Reject non-UTF8 files | **Strict UTF-8 corpus** |
| `FAIL-DAT-078` | Duplicate record ID in dataset | len(set(ids)) < len(ids) | Unique ID assertion | Deduplicate on record ID | **Unique record identifiers** |
| `FAIL-DAT-079` | Missing required fields in record | record missing 'record_id' or 'text' | Schema validation against dataset spec | Quarantine invalid records | **Schema-compliant dataset** |
| `FAIL-DAT-080` | Corrupted JSONL trailing whitespace | Trailing spaces causing JSON decode error | Strip lines before json.loads() | Robust line-by-line parsing | **Clean data ingestion** |

## SECURITY Failure Scenarios (20 Scenarios)

| ID | Specific Failure Mode | Detection Mechanism | Defensive Protocol | Fallback Action | Safe Final State |
|---|---|---|---|---|---|
| `FAIL-SEC-081` | eval() call in tokenizer loading | AST scan detects eval() | Pre-execution static analysis | Block execution; remove eval() | **Zero eval calls** |
| `FAIL-SEC-082` | exec() call in model script | AST scan detects exec() | Pre-execution static analysis | Block execution; remove exec() | **Zero exec calls** |
| `FAIL-SEC-083` | os.system call in training pipeline | AST scan detects os.system() | Pre-execution static analysis | Block execution; use subprocess with args list | **Zero shell injection** |
| `FAIL-SEC-084` | subprocess shell=True vulnerability | AST scan detects shell=True | Security linter hook | Enforce shell=False with explicit arg list | **Zero shell vulnerabilities** |
| `FAIL-SEC-085` | Unsafe pickle.load of model weights | Code uses pickle directly on untrusted file | Enforce torch.load(weights_only=True) or safe tensors | Block insecure deserialization | **Safe tensor loading** |
| `FAIL-SEC-086` | Path traversal via tokenizer path | Tokenizer path contains '../' | Sanitize path via Path.resolve() | Restrict paths to project root | **Confined filesystem access** |
| `FAIL-SEC-087` | Symlink pointing outside project root | Path.is_symlink() resolves outside workspace | Symlink audit hook | Reject out-of-bounds symlinks | **Filesystem isolation** |
| `FAIL-SEC-088` | Network socket creation during training | socket.socket() called | Run in sandboxed environment without network | Block network access | **Hermetic offline training** |
| `FAIL-SEC-089` | HTTP request to external telemetry | requests.post() or urllib called | Network proxy firewall / sandbox isolation | Reject external telemetry calls | **Local JSONL telemetry only** |
| `FAIL-SEC-090` | Arbitrary executable in tokenizer dir | File has executable bit set (chmod +x) | Filesystem permission scan | Clear execute permissions (chmod 644) | **Non-executable data files** |
| `FAIL-SEC-091` | Environment variable injection | Unsanitized os.environ access modifying runtime | Validate environment variables against allowlist | Ignore unexpected environment overrides | **Predictable configuration** |
| `FAIL-SEC-092` | Temporary file race condition | Insecure tempfile creation (mktemp) | Use tempfile.NamedTemporaryFile() with context manager | Safe ephemeral files | **Zero tempfile races** |
| `FAIL-SEC-093` | Model weight tampering during run | Model file modified while process is active | Memory-lock weights after loading | Reload from disk and abort if modified | **Immutable model weights** |
| `FAIL-SEC-094` | Arbitrary code in SentencePiece model | SentencePiece binary contains payload | Protobuf structure validation | SentencePiece C++ parser rejects non-protobuf | **Safe model loading** |
| `FAIL-SEC-095` | Unauthorized script execution in v2 dir | Python script found in data/tokenizers/ | Assert no .py files in tokenizer version directory | Quarantine script | **Pure artifact directory** |
| `FAIL-SEC-096` | World-writable permission on model file | stat.S_IWOTH set on tokenizer.model | File permission audit | chmod 644 on all artifacts | **Secured file permissions** |
| `FAIL-SEC-097` | Privilege escalation via sudo | Code contains 'sudo' | Static code check | Block sudo execution | **Standard user execution** |
| `FAIL-SEC-098` | Dynamic code compilation via compile() | AST scan detects compile() | Security scanner | Block dynamic compilation | **Static code only** |
| `FAIL-SEC-099` | Unrestricted file write outside artifacts | Writing to /tmp or /etc | Assert TargetFile starts with project root | Reject out-of-workspace writes | **Strict path confinement** |
| `FAIL-SEC-100` | Memory inspection via ptrace | Unauthorized debugger attachment | Process isolation | Block external ptrace attach | **Isolated execution** |

## INFRASTRUCTURE Failure Scenarios (20 Scenarios)

| ID | Specific Failure Mode | Detection Mechanism | Defensive Protocol | Fallback Action | Safe Final State |
|---|---|---|---|---|---|
| `FAIL-INF-101` | Disk full during tokenizer training | No space left on device | Pre-check available disk space (> 1 GB) | Clean temporary scratch directory; abort if low | **Protected disk resources** |
| `FAIL-INF-102` | RAM exhaustion during tokenization | Process exceeds available 12 GB RAM | Monitor memory via psutil; batch processing | Process corpus in streaming chunks | **Bounded RAM usage** |
| `FAIL-INF-103` | CPU thermal throttling | CPU temperature exceeds safe threshold | Monitor CPU load; restrict threads to 2 | Throttle execution or pause between batches | **Hardware longevity** |
| `FAIL-INF-104` | Process SIGINT interruption | User presses Ctrl+C during tokenizer build | Signal handler catches KeyboardInterrupt | Delete incomplete temporary model; exit cleanly | **Atomic file creation** |
| `FAIL-INF-105` | Process SIGTERM from OS OOM killer | Process terminated by kernel | Keep batch size = 1, context = 128 | Prevent OOM by design | **Stable OS lifecycle** |
| `FAIL-INF-106` | Corrupted virtual environment | venv/bin/python3 binary broken or missing modules | Pre-run sanity check importing torch & sentencepiece | Reinstall virtual environment | **Functional toolchain** |
| `FAIL-INF-107` | Missing C++ runtime libraries | libstdc++.so missing for SentencePiece | Check dynamic linker ldd on sentencepiece.so | Install standard libstdc++ package | **Operational native binaries** |
| `FAIL-INF-108` | Stale pytest cache interfering with tests | .pytest_cache contains outdated AST | Run pytest with -o cache_dir=/tmp/pytest_cache | Clean test execution | **Accurate test results** |
| `FAIL-INF-109` | Lockfile contention on SQLite DB | sqlite3.OperationalError: database is locked | Verify no background processes accessing DB | Zero concurrent DB access in Phase 58 | **Uncontended database** |
| `FAIL-INF-110` | File descriptor exhaustion | Too many open files error | Ensure all open() calls use context managers ('with') | Explicit file descriptor closing | **Bounded file handles** |
| `FAIL-INF-111` | Slow disk I/O causing timeouts | I/O wait exceeds test timeouts | Use local SSD/HDD storage without NFS | Tune timeout thresholds for CPU environment | **Predictable execution times** |
| `FAIL-INF-112` | Corrupted pyc bytecode cache | Python bytecode out of sync with source | Run with PYTHONDONTWRITEBYTECODE=1 or clean __pycache__ | Fresh bytecode compilation | **Accurate code execution** |
| `FAIL-INF-113` | Multi-threading deadlock in PyTorch | Deadlock in dataloader workers | Set num_workers=0 (single-process dataloading) | Deterministic single-thread loading | **Deadlock-free training** |
| `FAIL-INF-114` | System clock drift | System time changes backwards during run | Use time.monotonic() for duration measurements | Resilient timing logic | **Accurate elapsed metrics** |
| `FAIL-INF-115` | Corrupted terminal output stream | ANSI escape sequences breaking logs | Clean text logging without raw escapes | Legible audit reports | **Clear forensic records** |
| `FAIL-INF-116` | Artifact directory permission denied | Cannot write to artifacts/ or data/ | Check os.access(dir, os.W_OK) | Fix directory permissions before run | **Writable artifact storage** |
| `FAIL-INF-117` | Dangling background subagent task | Previous subagent leaves orphaned task running | Manage_task list and kill stale tasks | Clean process table | **Zero orphan processes** |
| `FAIL-INF-118` | Corrupted git index file | .git/index broken | git status validation check | Restore git index from HEAD | **Operational git repository** |
| `FAIL-INF-119` | Log file disk space runaway | Verbose logging fills disk | Truncate logs or log every 10 steps only | Bounded log file sizes | **Protected storage** |
| `FAIL-INF-120` | Crash during JSON serialization | Non-serializable object passed to json.dumps | Custom default=str handler or strict type validation | Clean JSON output | **Valid telemetry files** |

## GOVERNANCE Failure Scenarios (20 Scenarios)

| ID | Specific Failure Mode | Detection Mechanism | Defensive Protocol | Fallback Action | Safe Final State |
|---|---|---|---|---|---|
| `FAIL-GOV-121` | Unauthorized production DB mutation | DB SHA changes from 34376318... | Verify SHA before and after every phase | Rollback immediately from immutable backup; alert | **Unmodified production database** |
| `FAIL-GOV-122` | Production DB file size modification | DB size changes from 11096064 bytes | Verify exact byte size | Restore database; halt phase | **Unmodified production database** |
| `FAIL-GOV-123` | Production DB WAL file creation | brud_ai.db-wal exists | Check for WAL existence | Checkpoint and remove WAL | **Clean database state** |
| `FAIL-GOV-124` | Public routing activation of candidate | Candidate model set to active in routing | Check public_chat_routing_events table | Set is_public_chat_eligible=False; 0.0% traffic | **Public isolation preserved** |
| `FAIL-GOV-125` | Canary deployment of unapproved model | canary_enabled set to True | Check config isolation block | Enforce canary_enabled=False | **Zero public exposure** |
| `FAIL-GOV-126` | Auto-promotion trigger execution | auto_promotion set to True | Check config isolation block | Enforce auto_promotion=False | **Manual governance barrier** |
| `FAIL-GOV-127` | Git HEAD divergence | HEAD commit differs from df054cb1... | Verify git rev-parse HEAD | Hard reset to df054cb1... | **Linear git lineage** |
| `FAIL-GOV-128` | Git stash@{0} loss | Phase 7C-1 pilot stash lost | Verify git stash list | Re-create stash from commit history | **Historical stash preserved** |
| `FAIL-GOV-129` | Unauthorized full training launch | Training steps > 100 executed in Phase 58 | Audit step counter against diagnostic ceiling | Kill process immediately | **Zero unauthorized training** |
| `FAIL-GOV-130` | Fabricated capability claim | Reporting non-zero capability without evidence | Cross-verify report against raw telemetry JSONL | Enforce Rule 1 Zero Fabrication | **Scientifically honest reports** |
| `FAIL-GOV-131` | Modification of frozen evaluation probes | phase53_evaluation_manifest.json modified | Verify manifest_sha256 matches 8f08ac36... | Restore frozen manifest | **Uncompromised benchmark** |
| `FAIL-GOV-132` | Removal of failing benchmark probes | Probe count < 32 | Assert len(probes) == 32 | Restore all 32 frozen probes | **Integrity of evaluation** |
| `FAIL-GOV-133` | Direct checkpoint Frankenstein slicing | Slicing old weights into new vocab dimensions | Inspect model loading logic in codebase | Enforce fresh initialization for new architecture | **Methodological purity** |
| `FAIL-GOV-134` | Claiming capability from loss reduction alone | Asserting model improved because loss fell | Enforce Rule 10 Loss != Capability decoupling | Require independent evaluation probe verification | **Rigorous scientific standard** |
| `FAIL-GOV-135` | Bypassing sandbox without authorization | Command runs outside sandbox without necessity | Enforce sandbox mode by default | Require manual approval for unsandboxed commands | **Secure execution boundary** |
| `FAIL-GOV-136` | Skipping quality gates | Marking phase complete with failing gates | Automated quality gate verification script | Block phase completion if any gate fails | **Enforced quality standards** |
| `FAIL-GOV-137` | Unapproved Phase 59 launch | Starting Phase 59 without explicit user prompt | Enforce STOP condition at WS24 | Wait for user authorization | **Strict user command hierarchy** |
| `FAIL-GOV-138` | Silent error suppression | Try-except blocks swallowing critical exceptions | Code review against bare except passes | Log all exceptions with full tracebacks | **Transparent error handling** |
| `FAIL-GOV-139` | Telemetry event deletion | Deleting lines from training telemetry JSONL | Append-only telemetry file policy | Audit line count monotonicity | **Tamper-evident audit trail** |
| `FAIL-GOV-140` | Premature model registration in DB | Inserting candidate row into model_registry | Query model_registry for candidate name | Delete premature registration | **Clean production registry** |


## Extended Governance, Infrastructure & Linguistic Failure Scenarios (40 Scenarios)

| ID | Specific Failure Mode | Detection Mechanism | Defensive Protocol | Fallback Action | Safe Final State |
|---|---|---|---|---|---|
| `FAIL-TOK-141` | Tamil Ayutha Ezhuthu standalone decoding error | Decode produces question mark | Inspect SentencePiece piece score for ஃ | Re-weight piece in seed vocab | **Clean Ayutha Ezhuthu** |
| `FAIL-TOK-142` | Tamil vowel elongation omission | Omission of elongated uyir ezhuthu | Round-trip test on classical poem | Byte fallback retains combining glyph | **Preserved poetic meter** |
| `FAIL-TOK-143` | Zero-width non-joiner (ZWNJ) corruption | ZWNJ (U+200C) alters Tamil script rendering | Pre-tokenization NFKC normalization | Normalize or preserve via byte fallback | **Correct script rendering** |
| `FAIL-TOK-144` | Zero-width joiner (ZWJ) corruption | ZWJ (U+200D) alters Tamil ligatures | Pre-tokenization NFKC normalization | Normalize or preserve via byte fallback | **Correct ligature rendering** |
| `FAIL-TOK-145` | Multiple sequential whitespace normalization divergence | Triple space collapsed to single space unexpectedly | SentencePiece dummy whitespace audit | Verify nmt_nfkc whitespace preservation | **Consistent whitespace tokenization** |
| `FAIL-TOK-146` | Punctuation adjacent token split error | Period merged with word into single piece | BPE split_by_punctuation rule check | Ensure split_by_whitespace=True and BPE subwords | **Punctuation decoupled from word** |
| `FAIL-MOD-147` | Multi-head attention projection weight shape mismatch | q_proj vs k_proj shape divergence | Assert in_proj_weight.shape == [3 * d, d] | Construct standard multi-head self-attention | **Symmetric projection matrices** |
| `FAIL-MOD-148` | Output linear projection bias dimension error | fc_out.bias shape != [vocab_size] | Check bias parameter length | Re-instantiate fc_out linear layer | **Correct output logits** |
| `FAIL-MOD-149` | Cross-entropy ignore_index collision with token 0 | Padding token ID 0 not ignored in loss | Inspect loss function constructor ignore_index | Enforce ignore_index=0 | **Zero gradient on pad tokens** |
| `FAIL-MOD-150` | Positional encoding sequence length ceiling breach | Absolute positional encoding clamped at 64 | Check max_len in positional embedding table | Set max_len >= 128 for Model v2 | **Supported 128-token context** |
| `FAIL-MOD-151` | LayerNorm forward pass numerical instability | Variance calculation negative due to float epsilon | Enforce eps >= 1e-5 | Stable LayerNorm computation | **Finite layer outputs** |
| `FAIL-MOD-152` | GELU vs ReLU activation discrepancy | Model uses non-standard activation | Assert standard activation in FFN | Preserve standard architectural activation | **Expected non-linearities** |
| `FAIL-MOD-153` | Gradient clipping norm set to zero | Grad clip norm == 0 | Assert grad_clip_norm > 0 | Set grad_clip_norm = 1.0 | **Active gradient updates** |
| `FAIL-MOD-154` | Dropout active during deterministic benchmark evaluation | Random logit jitter across identical runs | Assert model.training == False | Call model.eval() before evaluation | **100% deterministic inference** |
| `FAIL-DAT-155` | Corpus record missing 'domain' field | KeyError on record['domain'] | Schema validation hook | Default to 'general' domain tag | **Valid record schema** |
| `FAIL-DAT-156` | Corpus record missing 'split' field | KeyError on record['split'] | Schema validation hook | Default to 'train' split tag | **Valid record schema** |
| `FAIL-DAT-157` | Corpus record with empty 'source_id' | Record has no provenance identifier | Provenance integrity audit | Quarantine unprovenanced record | **100% provenance compliance** |
| `FAIL-DAT-158` | Corpus record with non-ASCII record_id | record_id contains invalid characters | ID regex validation | Sanitize record ID to canonical slug | **Standard record identifiers** |
| `FAIL-DAT-159` | Duplicate text content across distinct record IDs | Exact text duplicate in training set | Exact-match deduplication screen | Deduplicate on text SHA-256 | **Deduplicated corpus** |
| `FAIL-DAT-160` | High near-duplicate similarity (>90%) | MinHash LSH flags high text overlap | Near-deduplication screen | Filter out near-duplicates | **Diverse training corpus** |
| `FAIL-SEC-161` | Unsafe yaml.load() in config parsing | AST scan flags yaml.load() without SafeLoader | Security linting check | Enforce yaml.safe_load() | **Safe YAML parsing** |
| `FAIL-SEC-162` | Insecure temporary directory creation in /tmp | Writing code to shared /tmp | Filesystem path audit | Confine tempfiles to artifacts/scratch/ | **Confined storage** |
| `FAIL-SEC-163` | Dynamic module reloading via reload() | AST scan flags importlib.reload() | Static analysis check | Enforce static module lifecycle | **Predictable module state** |
| `FAIL-SEC-164` | Unsafe reflection via getattr() on untrusted strings | Dynamic dispatch on user input | Code inspection for getattr abuse | Use explicit dictionary dispatch | **Safe dispatch** |
| `FAIL-SEC-165` | World-readable sensitive configuration | chmod 777 on sensitive files | File permission audit | chmod 600 or 644 | **Protected configuration** |
| `FAIL-INF-166` | Virtual memory paging thrashing | Swap memory usage spikes | Monitor swap usage via psutil | Reduce batch size to 1 sequence | **Zero swap thrashing** |
| `FAIL-INF-167` | PyTorch thread over-subscription on 2-core CPU | Context switching overhead degrades throughput | Assert torch.get_num_threads() <= 2 | Set num_threads = 2 | **Optimal CPU core usage** |
| `FAIL-INF-168` | Corrupted SentencePiece shared library (.so) | ImportError on sentencepiece | Pre-flight import test | Reinstall binary wheel | **Operational SentencePiece** |
| `FAIL-INF-169` | Orphaned subagent process locking CPU resources | Zombie process consumes CPU | Check process table for stale pids | Kill orphan subagent processes | **Clean execution environment** |
| `FAIL-INF-170` | Corrupted stdout buffer in background task | Process hangs on unbuffered write | Flush stdout after every telemetry emission | Continuous unbuffered logging | **Live task logs** |
| `FAIL-GOV-171` | Silent quality gate suppression | Failing quality gate masked as PASS | Automated gate verifier assertion | Fail closed on any gate failure | **Uncompromised quality standard** |
| `FAIL-GOV-172` | Unauthorized modification of test assertion threshold | Relaxing threshold to force test pass | Audit test commit diffs | Block threshold relaxation | **Honest test suite** |
| `FAIL-GOV-173` | Premature declaration of capability improvement | Claiming capability without evaluation proof | Verify delta_ba against frozen manifest | Require empirical proof | **Zero fabrication** |
| `FAIL-GOV-174` | Unauthorized promotion to production chat | Candidate set to active in model_registry | Audit database model_registry rows | Rollback candidate promotion | **Isolated candidate** |
| `FAIL-GOV-175` | Stale checkpoint promoted over candidate | Legacy checkpoint promoted mistakenly | Verify checkpoint SHA and phase metadata | Reject stale checkpoint | **Governed release boundary** |
| `FAIL-GOV-176` | Phase 58 launching Phase 59 without user authorization | Executing training script at end of Phase 58 | Enforce hard STOP condition at WS24 | Stop and report to user | **Strict command compliance** |
| `FAIL-GOV-177` | Corrupted telemetry event sequence | Telemetry JSONL missing step events | Monotonic step counter audit | Re-emit missing telemetry records | **Complete audit trail** |
| `FAIL-GOV-178` | Production database write during evaluation | DB mtime changes during eval run | Read-only SQLite connection flag (mode=ro) | Enforce read-only DB connection | **Unmodified production database** |
| `FAIL-GOV-179` | Phase 55 records JSONL modification during training | Corpus file mtime changes | Verify corpus SHA before and after run | Restore corpus from git if changed | **Immutable training corpus** |
| `FAIL-GOV-180` | Phase 53 manifest modification during evaluation | Evaluation JSON modified | Verify manifest SHA before and after run | Restore manifest from git if changed | **Immutable frozen evaluation** |