# Paged closed-position journal

The Journal's closed-position history no longer depends on the workspace's
recent-50 snapshot. A dedicated owner-scoped API returns newest-first pages of 20,
with a `(closed_at, id)` cursor. Invalid, open, missing or foreign-account cursor
positions are rejected. The UI appends pages without duplicates and retains the
loaded page when an older-page request fails. Entry/exit order history remains
available from each position card.

The workspace response no longer loads an unused 50-row closed-position list on
every refresh. CSV export now streams all closed positions in batches rather than
stopping at 10,000. Spreadsheet formula-leading instrument strings remain escaped.

Historical marked-equity snapshots, journal filters, and funding/reset workflows
remain open under D15. Journal pages are request snapshots, not one frozen history
snapshot across all cursor requests; refresh to see later corrections. No tests or
build checks were run. Local API/web were restarted on loopback; the background
worker is stopped to keep offline use from making provider calls.
