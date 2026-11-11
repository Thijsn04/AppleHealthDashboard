# Privacy and deletion

The analyzer runs on loopback and keeps imported data in `health.duckdb` in the server's working directory. ZIP extraction and pending previews use `.tmp/api-imports/`. DuckDB can create a write-ahead log and a spill directory beside the profile. The normal application uses local HTTP requests, has no account, and sends no health observations to external services.

Previews expire after 30 minutes, with periodic cleanup. Cancellation and graceful shutdown remove staged copies. An unexpected process termination can leave temporary files on disk. Original exports, downloaded CSVs, backups and synced copies are separate from the app's files.

To remove application-managed files, stop the server and run the following from the server's working directory.

```sh
python -m apple_health_dashboard.cli clear --yes
```

This is normal file deletion. Use a working directory outside cloud-synchronized storage and operating-system permissions appropriate for sensitive files. Keep backups in a location you control.
