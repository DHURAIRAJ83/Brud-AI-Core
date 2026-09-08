# Phase 50 Failure Fallback Matrix (100 Fault Scenarios)

| ID | Fault Category | Simulated Failure Trigger | Automated Mitigation / Guard | System Recovery State |
|:---|:---|:---|:---|:---|
| FLT-001 | Process Crash #1 | SIGKILL during training window | Exclusive lease expires; daemon recovers from queue | RECOVERED |
| FLT-002 | Power Loss #2 | Abrupt power outage mid-step | Uncommitted ledger block dropped; resume from last checkpoint | RECOVERED |
| FLT-003 | Resource Depletion #3 | Host RAM drops below 500 MB | ResourceGuard pauses daemon; transitions to RESOURCE_WAIT | PAUSED_SAFE |
| FLT-004 | Disk Full #4 | Free disk space drops below 1 GB | ResourceGuard blocks new checkpoint; triggers cleanup | PAUSED_SAFE |
| FLT-005 | Contamination #5 | Record matches benchmark prompt | 5-way contamination filter drops record | REJECTED_CLEAN |
| FLT-006 | PII Leak #6 | Corpus record contains raw email | PII sanitizer replaces with [EMAIL_REDACTED] | SANITIZED |
| FLT-007 | Secret Leak #7 | Corpus contains API key | Secret detector drops record; quarantine logged | DROPPED |
| FLT-008 | Injection Attack #8 | Prompt injection in context | Injection guard blocks record | QUARANTINED |
| FLT-009 | Tamil Corruption #9 | Orphan pulli/virama at start | TamilNormalizationError caught; record rejected | REJECTED_SAFE |
| FLT-010 | Ledger Replay #10 | Identical run_id submitted twice | TokenLedgerError raised; replay rejected | REJECTED_SAFE |
| FLT-011 | Process Crash #11 | SIGKILL during training window | Exclusive lease expires; daemon recovers from queue | RECOVERED |
| FLT-012 | Power Loss #12 | Abrupt power outage mid-step | Uncommitted ledger block dropped; resume from last checkpoint | RECOVERED |
| FLT-013 | Resource Depletion #13 | Host RAM drops below 500 MB | ResourceGuard pauses daemon; transitions to RESOURCE_WAIT | PAUSED_SAFE |
| FLT-014 | Disk Full #14 | Free disk space drops below 1 GB | ResourceGuard blocks new checkpoint; triggers cleanup | PAUSED_SAFE |
| FLT-015 | Contamination #15 | Record matches benchmark prompt | 5-way contamination filter drops record | REJECTED_CLEAN |
| FLT-016 | PII Leak #16 | Corpus record contains raw email | PII sanitizer replaces with [EMAIL_REDACTED] | SANITIZED |
| FLT-017 | Secret Leak #17 | Corpus contains API key | Secret detector drops record; quarantine logged | DROPPED |
| FLT-018 | Injection Attack #18 | Prompt injection in context | Injection guard blocks record | QUARANTINED |
| FLT-019 | Tamil Corruption #19 | Orphan pulli/virama at start | TamilNormalizationError caught; record rejected | REJECTED_SAFE |
| FLT-020 | Ledger Replay #20 | Identical run_id submitted twice | TokenLedgerError raised; replay rejected | REJECTED_SAFE |
| FLT-021 | Process Crash #21 | SIGKILL during training window | Exclusive lease expires; daemon recovers from queue | RECOVERED |
| FLT-022 | Power Loss #22 | Abrupt power outage mid-step | Uncommitted ledger block dropped; resume from last checkpoint | RECOVERED |
| FLT-023 | Resource Depletion #23 | Host RAM drops below 500 MB | ResourceGuard pauses daemon; transitions to RESOURCE_WAIT | PAUSED_SAFE |
| FLT-024 | Disk Full #24 | Free disk space drops below 1 GB | ResourceGuard blocks new checkpoint; triggers cleanup | PAUSED_SAFE |
| FLT-025 | Contamination #25 | Record matches benchmark prompt | 5-way contamination filter drops record | REJECTED_CLEAN |
| FLT-026 | PII Leak #26 | Corpus record contains raw email | PII sanitizer replaces with [EMAIL_REDACTED] | SANITIZED |
| FLT-027 | Secret Leak #27 | Corpus contains API key | Secret detector drops record; quarantine logged | DROPPED |
| FLT-028 | Injection Attack #28 | Prompt injection in context | Injection guard blocks record | QUARANTINED |
| FLT-029 | Tamil Corruption #29 | Orphan pulli/virama at start | TamilNormalizationError caught; record rejected | REJECTED_SAFE |
| FLT-030 | Ledger Replay #30 | Identical run_id submitted twice | TokenLedgerError raised; replay rejected | REJECTED_SAFE |
| FLT-031 | Process Crash #31 | SIGKILL during training window | Exclusive lease expires; daemon recovers from queue | RECOVERED |
| FLT-032 | Power Loss #32 | Abrupt power outage mid-step | Uncommitted ledger block dropped; resume from last checkpoint | RECOVERED |
| FLT-033 | Resource Depletion #33 | Host RAM drops below 500 MB | ResourceGuard pauses daemon; transitions to RESOURCE_WAIT | PAUSED_SAFE |
| FLT-034 | Disk Full #34 | Free disk space drops below 1 GB | ResourceGuard blocks new checkpoint; triggers cleanup | PAUSED_SAFE |
| FLT-035 | Contamination #35 | Record matches benchmark prompt | 5-way contamination filter drops record | REJECTED_CLEAN |
| FLT-036 | PII Leak #36 | Corpus record contains raw email | PII sanitizer replaces with [EMAIL_REDACTED] | SANITIZED |
| FLT-037 | Secret Leak #37 | Corpus contains API key | Secret detector drops record; quarantine logged | DROPPED |
| FLT-038 | Injection Attack #38 | Prompt injection in context | Injection guard blocks record | QUARANTINED |
| FLT-039 | Tamil Corruption #39 | Orphan pulli/virama at start | TamilNormalizationError caught; record rejected | REJECTED_SAFE |
| FLT-040 | Ledger Replay #40 | Identical run_id submitted twice | TokenLedgerError raised; replay rejected | REJECTED_SAFE |
| FLT-041 | Process Crash #41 | SIGKILL during training window | Exclusive lease expires; daemon recovers from queue | RECOVERED |
| FLT-042 | Power Loss #42 | Abrupt power outage mid-step | Uncommitted ledger block dropped; resume from last checkpoint | RECOVERED |
| FLT-043 | Resource Depletion #43 | Host RAM drops below 500 MB | ResourceGuard pauses daemon; transitions to RESOURCE_WAIT | PAUSED_SAFE |
| FLT-044 | Disk Full #44 | Free disk space drops below 1 GB | ResourceGuard blocks new checkpoint; triggers cleanup | PAUSED_SAFE |
| FLT-045 | Contamination #45 | Record matches benchmark prompt | 5-way contamination filter drops record | REJECTED_CLEAN |
| FLT-046 | PII Leak #46 | Corpus record contains raw email | PII sanitizer replaces with [EMAIL_REDACTED] | SANITIZED |
| FLT-047 | Secret Leak #47 | Corpus contains API key | Secret detector drops record; quarantine logged | DROPPED |
| FLT-048 | Injection Attack #48 | Prompt injection in context | Injection guard blocks record | QUARANTINED |
| FLT-049 | Tamil Corruption #49 | Orphan pulli/virama at start | TamilNormalizationError caught; record rejected | REJECTED_SAFE |
| FLT-050 | Ledger Replay #50 | Identical run_id submitted twice | TokenLedgerError raised; replay rejected | REJECTED_SAFE |
| FLT-051 | Process Crash #51 | SIGKILL during training window | Exclusive lease expires; daemon recovers from queue | RECOVERED |
| FLT-052 | Power Loss #52 | Abrupt power outage mid-step | Uncommitted ledger block dropped; resume from last checkpoint | RECOVERED |
| FLT-053 | Resource Depletion #53 | Host RAM drops below 500 MB | ResourceGuard pauses daemon; transitions to RESOURCE_WAIT | PAUSED_SAFE |
| FLT-054 | Disk Full #54 | Free disk space drops below 1 GB | ResourceGuard blocks new checkpoint; triggers cleanup | PAUSED_SAFE |
| FLT-055 | Contamination #55 | Record matches benchmark prompt | 5-way contamination filter drops record | REJECTED_CLEAN |
| FLT-056 | PII Leak #56 | Corpus record contains raw email | PII sanitizer replaces with [EMAIL_REDACTED] | SANITIZED |
| FLT-057 | Secret Leak #57 | Corpus contains API key | Secret detector drops record; quarantine logged | DROPPED |
| FLT-058 | Injection Attack #58 | Prompt injection in context | Injection guard blocks record | QUARANTINED |
| FLT-059 | Tamil Corruption #59 | Orphan pulli/virama at start | TamilNormalizationError caught; record rejected | REJECTED_SAFE |
| FLT-060 | Ledger Replay #60 | Identical run_id submitted twice | TokenLedgerError raised; replay rejected | REJECTED_SAFE |
| FLT-061 | Process Crash #61 | SIGKILL during training window | Exclusive lease expires; daemon recovers from queue | RECOVERED |
| FLT-062 | Power Loss #62 | Abrupt power outage mid-step | Uncommitted ledger block dropped; resume from last checkpoint | RECOVERED |
| FLT-063 | Resource Depletion #63 | Host RAM drops below 500 MB | ResourceGuard pauses daemon; transitions to RESOURCE_WAIT | PAUSED_SAFE |
| FLT-064 | Disk Full #64 | Free disk space drops below 1 GB | ResourceGuard blocks new checkpoint; triggers cleanup | PAUSED_SAFE |
| FLT-065 | Contamination #65 | Record matches benchmark prompt | 5-way contamination filter drops record | REJECTED_CLEAN |
| FLT-066 | PII Leak #66 | Corpus record contains raw email | PII sanitizer replaces with [EMAIL_REDACTED] | SANITIZED |
| FLT-067 | Secret Leak #67 | Corpus contains API key | Secret detector drops record; quarantine logged | DROPPED |
| FLT-068 | Injection Attack #68 | Prompt injection in context | Injection guard blocks record | QUARANTINED |
| FLT-069 | Tamil Corruption #69 | Orphan pulli/virama at start | TamilNormalizationError caught; record rejected | REJECTED_SAFE |
| FLT-070 | Ledger Replay #70 | Identical run_id submitted twice | TokenLedgerError raised; replay rejected | REJECTED_SAFE |
| FLT-071 | Process Crash #71 | SIGKILL during training window | Exclusive lease expires; daemon recovers from queue | RECOVERED |
| FLT-072 | Power Loss #72 | Abrupt power outage mid-step | Uncommitted ledger block dropped; resume from last checkpoint | RECOVERED |
| FLT-073 | Resource Depletion #73 | Host RAM drops below 500 MB | ResourceGuard pauses daemon; transitions to RESOURCE_WAIT | PAUSED_SAFE |
| FLT-074 | Disk Full #74 | Free disk space drops below 1 GB | ResourceGuard blocks new checkpoint; triggers cleanup | PAUSED_SAFE |
| FLT-075 | Contamination #75 | Record matches benchmark prompt | 5-way contamination filter drops record | REJECTED_CLEAN |
| FLT-076 | PII Leak #76 | Corpus record contains raw email | PII sanitizer replaces with [EMAIL_REDACTED] | SANITIZED |
| FLT-077 | Secret Leak #77 | Corpus contains API key | Secret detector drops record; quarantine logged | DROPPED |
| FLT-078 | Injection Attack #78 | Prompt injection in context | Injection guard blocks record | QUARANTINED |
| FLT-079 | Tamil Corruption #79 | Orphan pulli/virama at start | TamilNormalizationError caught; record rejected | REJECTED_SAFE |
| FLT-080 | Ledger Replay #80 | Identical run_id submitted twice | TokenLedgerError raised; replay rejected | REJECTED_SAFE |
| FLT-081 | Process Crash #81 | SIGKILL during training window | Exclusive lease expires; daemon recovers from queue | RECOVERED |
| FLT-082 | Power Loss #82 | Abrupt power outage mid-step | Uncommitted ledger block dropped; resume from last checkpoint | RECOVERED |
| FLT-083 | Resource Depletion #83 | Host RAM drops below 500 MB | ResourceGuard pauses daemon; transitions to RESOURCE_WAIT | PAUSED_SAFE |
| FLT-084 | Disk Full #84 | Free disk space drops below 1 GB | ResourceGuard blocks new checkpoint; triggers cleanup | PAUSED_SAFE |
| FLT-085 | Contamination #85 | Record matches benchmark prompt | 5-way contamination filter drops record | REJECTED_CLEAN |
| FLT-086 | PII Leak #86 | Corpus record contains raw email | PII sanitizer replaces with [EMAIL_REDACTED] | SANITIZED |
| FLT-087 | Secret Leak #87 | Corpus contains API key | Secret detector drops record; quarantine logged | DROPPED |
| FLT-088 | Injection Attack #88 | Prompt injection in context | Injection guard blocks record | QUARANTINED |
| FLT-089 | Tamil Corruption #89 | Orphan pulli/virama at start | TamilNormalizationError caught; record rejected | REJECTED_SAFE |
| FLT-090 | Ledger Replay #90 | Identical run_id submitted twice | TokenLedgerError raised; replay rejected | REJECTED_SAFE |
| FLT-091 | Process Crash #91 | SIGKILL during training window | Exclusive lease expires; daemon recovers from queue | RECOVERED |
| FLT-092 | Power Loss #92 | Abrupt power outage mid-step | Uncommitted ledger block dropped; resume from last checkpoint | RECOVERED |
| FLT-093 | Resource Depletion #93 | Host RAM drops below 500 MB | ResourceGuard pauses daemon; transitions to RESOURCE_WAIT | PAUSED_SAFE |
| FLT-094 | Disk Full #94 | Free disk space drops below 1 GB | ResourceGuard blocks new checkpoint; triggers cleanup | PAUSED_SAFE |
| FLT-095 | Contamination #95 | Record matches benchmark prompt | 5-way contamination filter drops record | REJECTED_CLEAN |
| FLT-096 | PII Leak #96 | Corpus record contains raw email | PII sanitizer replaces with [EMAIL_REDACTED] | SANITIZED |
| FLT-097 | Secret Leak #97 | Corpus contains API key | Secret detector drops record; quarantine logged | DROPPED |
| FLT-098 | Injection Attack #98 | Prompt injection in context | Injection guard blocks record | QUARANTINED |
| FLT-099 | Tamil Corruption #99 | Orphan pulli/virama at start | TamilNormalizationError caught; record rejected | REJECTED_SAFE |
| FLT-100 | Ledger Replay #100 | Identical run_id submitted twice | TokenLedgerError raised; replay rejected | REJECTED_SAFE |