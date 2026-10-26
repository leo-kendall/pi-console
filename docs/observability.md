# Logs and monitoring

Open a granted service or container's logs to follow its most recent tail. The app checks every two seconds while that dialog is open. Pause keeps the fetched rows available for search, level filtering, copy, and export. Search and export cover only the retained rows; they do not download an entire journal. Levels use keywords in the text rather than a structured journal severity field. Export opens Android's document picker, and copied/exported text can include private application data.

The server limits a response to 256 rows and 64 KiB of UTF-8 data. The app retains up to 1,000 rows and about 64 Ki UTF-16 characters. A reset replaces the window after rotation, truncation, restart, expiration, or loss of overlap. The underlying snapshot command does not supply stable record IDs, so a byte-identical replacement is indistinguishable from an unchanged tail. No continuous subprocess is started. Older backends fall back to a single snapshot with an upgrade message.

Select temperature, CPU, memory, receive rate, or send rate above the overview chart. Network history uses the selected interface and bytes per second. Missing or delayed samples leave gaps. Tap, drag, or use the chart's arrow keys to inspect a sample. History is held in memory by the server; a restart clears it. The overview retains about one hour at three-second intervals.

Process details provide CPU and resident-memory history for the exact PID and process start counter. A reused PID cannot inherit the old process's history. History starts when a process is opened, retains up to fifteen minutes and 301 samples, and expires after fifteen minutes without access. The server tracks at most 64 opened process identities. CPU is expressed with one core equal to 100%; RSS includes shared pages and is not an estimate of releasable memory. Opening process history is read-only.

Alert rules accept one to twenty consecutive abnormal samples before activation and one to twenty normal samples before recovery. Defaults remain three and two. Metrics are checked every fifteen seconds; services every sixty seconds. Recovery also applies the existing temperature/memory/disk hysteresis. An unavailable measurement breaks the consecutive count and cannot recover the corresponding incident. Unknown readings have their own incidents. Removing a watched object creates a resolution event with `recovered:false`; it does not claim the service recovered.

Phone notification preferences apply to that device: enable notifications, recovery notifications, and a quiet interval in the phone's local time. A quiet interval may cross midnight; equal start/end times disable it. Suppressed events remain in the server's history and are not replayed later. Incident transition IDs are tracked separately per server profile. The native Android service handles delivery and permissions; the web page does not deliver background notifications.

Existing four-field alert rules and stored files remain accepted. Saving rules from an older client preserves current debounce/recovery settings. Restoring a legacy schema-1 threshold/watch backup preserves those behavior settings; new native backups can preserve the optional fields. No phone notification preferences or credentials are placed in server alert rules.

## Integration interfaces

`LiveLogs(control).tail(owner,resource,cursor=None)` invokes `control.logs(resource)` on every accepted poll. The shared router must authenticate the owner, enforce device/resource grants, and expose it as read-only `POST /api/logs/tail`. The body contains `resource` and optionally `cursor`. Responses contain `lines`, opaque `cursor`, `reset`, `sampled_at`, `poll_after_ms`, and `bounded`. A cursor belongs to one owner/resource and expires after five minutes; unknown expired cursors reset. Polls faster than 1.5 seconds return HTTP 429. Cursor state is bounded to 128 snapshots and rate state to 256 device/resource pairs.

`Processes.history(pid,start)` is exposed as read-only `POST /api/processes/history` with exactly those integer fields. It returns numeric-only `points`, `pid`, `start`, `ended`, `interval_seconds`, `retention_seconds`, and `sampled_at`. PID reuse returns 409 and an untracked exited PID returns 404.

`observability_api.dispatch(path,data,owner,logs,processes)` implements both request contracts. It assumes the shared router authenticates and enforces roles before calling it.

Load `observability-ui.js` after `process-ui.js` and `tools-ui.js`, and include `observability.css`. Call `stopObservability()` when changing pages, pausing the app, or switching profiles; call `observabilityConnectionChanged(url,paired)` when the active connection changes. The module also checks endpoint, dialog, page, and foreground identity before applying replies or issuing another poll.

Native actions are `logsCopy` with `{text}`, `logsExport` with `{name,text}` (UTF-8 text, bounded to 256 KiB, Android SAF destination), and `notificationSettings` to read or save `{schema:1,enabled,recovery,quiet_start,quiet_end}`. Time fields use `HH:mm`. Unsupported native clients may return `{available:false}`. Log export accepts data only, never a backend filesystem path.
