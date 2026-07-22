# Database backup and recovery

## Safe commands

```bash
make db-status
make db-verify
make db-backup
make db-upgrade
```

`db-verify` runs SQLite integrity and foreign-key checks. `db-backup` uses SQLite's online backup API, opens and verifies the result, and records SHA-256 checksums. `db-upgrade` refuses an existing-schema upgrade unless verification and automatic backup succeed.

Backups are timestamped beneath `data/database/backups/` and are never overwritten. The directory is ignored by Git because backups may eventually contain private application data.

## Restore procedure

1. Stop every backend and SQLite client.
2. Run integrity and foreign-key verification against the selected backup.
3. Record checksums for both the active database and backup.
4. Move the active database plus any `-wal` and `-shm` companions to a separate recovery directory.
5. Copy the verified backup to the configured database filename without changing the backup itself.
6. Run `make db-verify` and `make db-status` before starting the backend.

Never restore over a running database, never overwrite the only backup, and never mix WAL/SHM files from different database snapshots. A restore intentionally requires operator review; Phase 2 provides no automated destructive restore command.
