# Phase 29 Recovery Architecture Debt Registry

This registry tracks technical findings, gaps, and architectural observations regarding disaster recovery, database backup integrity, restore governance, and business continuity across **Phases 13 through 29**.

> [!IMPORTANT]
> **READ-ONLY FINDINGS REGISTRY**:
> This document records architectural observations and recovery debt only. **NO SOURCE CODE MODIFICATIONS ARE ALLOWED DURING PHASE 29**.

---

## Disaster Recovery Debt Items

### Debt Item 1: Absence of Formal Database Backup / Snapshot Abstraction
- **ID**: DEBT-29-01
- **Category**: Database Recovery & Backup Integrity
- **Phase**: Phase 29 Audit Finding
- **File**: `backend/database/` & `core_model/capabilities/`
- **Finding**: While Phase 24, 25, and 26 manage pointer-based rollbacks and runtime recovery, the repository lacks a dedicated, structured database backup/snapshot management abstraction (no backup metadata tables, SHA-256 integrity verification tables, or backup provenance records).
- **Evidence**: Production DB `data/database/brud_ai.db` relies on static file copy or external file system tools; no programmatic `BackupMetadataRecord` or `BackupRepository` exists in code.
- **Severity**: MEDIUM
- **Impact**: In the event of catastrophic physical database corruption or host failure, recovery relies on external file backups without built-in integrity verification or provenance tracking.
- **Recommendation**: Design and implement an additive `DisasterRecoveryService` and `BackupRepository` with SHA-256 checksum verification and human-governed restore execution in Phase 30.
- **Implementation Required**: Additive domain, repository, service, and admin API components in future engineering phase.
- **Priority**: P2 (High Priority for Disaster Preparedness)

---

### Debt Item 2: Undefined Recovery Point Objective (RPO) & Recovery Time Objective (RTO)
- **ID**: DEBT-29-02
- **Category**: Business Continuity & Operational Policy
- **Phase**: Phase 29 Audit Finding
- **File**: System Architecture Specifications & Operational Docs
- **Finding**: RPO (acceptable data-loss window) and RTO (expected recovery time) are NOT explicitly defined or measured in existing system code or operational specifications.
- **Evidence**: No configuration parameters or health metrics exist to monitor backup age (`backup_freshness_seconds`) or verify RTO targets.
- **Severity**: LOW
- **Impact**: Operational teams cannot benchmark or alert on stale backup states or restore duration targets.
- **Recommendation**: Define explicit RPO targets (e.g., RPO = 1 hour / 3600 seconds) and RTO targets (e.g., RTO = 15 minutes / 900 seconds) and expose backup freshness in Phase 29/30 metrics endpoints.
- **Implementation Required**: Metadata and metric specification in future phase.
- **Priority**: P3 (Medium Priority)

---

### Debt Item 3: Lack of Automated SQLite Corruption Preflight Inspection
- **ID**: DEBT-29-03
- **Category**: Database Integrity & Corruption Detection
- **Phase**: Phase 29 Audit Finding
- **File**: `backend/database/repositories/`
- **Finding**: Existing repositories execute standard queries but do not provide a dedicated, non-destructive SQLite `PRAGMA quick_check` or `PRAGMA integrity_check` wrapper service for operational health inspection.
- **Evidence**: Phase 26 health check category `database` checks connection pool accessibility, but does not run deep SQLite page integrity verification.
- **Severity**: LOW
- **Impact**: Silent SQLite page corruption may remain undetected until a query hits a corrupted B-tree page.
- **Recommendation**: Include a non-destructive SQLite corruption preflight check in `DisasterRecoveryService` inspection capabilities.
- **Implementation Required**: Non-destructive query method in future repository.
- **Priority**: P3 (Medium Priority)

---

## Summary Scorecard

| Category | Debt Level | Risk Assessment | Action Priority |
| :--- | :---: | :--- | :--- |
| **Release & Deployment Rollback** | ZERO DEBT | Phase 24 and Phase 25 rollbacks verified intact | None |
| **Runtime Incident Recovery** | ZERO DEBT | Phase 26 state machine and human approval verified intact | None |
| **Stale Lock Governance** | ZERO DEBT | Phase 28 safe stale-lock maintenance verified intact | None |
| **Backup Metadata & SHA-256 Integrity** | MEDIUM DEBT | Programmatic backup metadata & SHA-256 checksums missing | P2 |
| **Restore Governance State Machine** | MEDIUM DEBT | Programmatic human-governed restore execution missing | P2 |
| **RPO / RTO Specifications** | LOW DEBT | RPO/RTO parameters currently NOT DEFINED in code | P3 |
| **SQLite Corruption Detection** | LOW DEBT | Deep SQLite `integrity_check` probe missing from runtime health | P3 |
