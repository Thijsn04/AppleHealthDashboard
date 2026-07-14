# Privacy and data handling

## Default data flow

```text
Your Apple Health export
        |
        v
Local validation and import
        |
        v
Local DuckDB database
        |
        v
Local API at 127.0.0.1
        |
        v
Local browser frontend
```

No account, cloud database, telemetry service, or remote analytics service is required by the target architecture.

## Sensitive data

An export can reveal health conditions, fertility and cycle information, medication patterns, sleep schedules, exercise habits, location, source-device details, and timestamps. Treat the export and the generated database as sensitive files.

## Network policy

- The local API binds to loopback by default.
- The target frontend ships without remote fonts, trackers, or analytics.
- Any future network feature must name the destination, data categories, reason, retention policy, and consent control.
- AI features require deliberate opt-in, a data preview, and a way to revoke or delete local conversation history.

## Data retention and deletion

The importer must show the storage location and provide a clear local-data deletion flow. Deletion should remove application-managed databases, temporary import files, derived datasets, and logs when the user requests it. Documentation must distinguish normal file deletion from secure erasure guarantees.

## Local deployment warning

The API is not intended to be exposed to a LAN or the public internet. If a developer changes the bind address, they are responsible for authentication, TLS, authorization, and operating-system hardening.
