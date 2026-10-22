# ReelFlow Auto

Bulk-video workflow dashboard for media owned by or licensed to the user.

## Planned workflow
1. Import a TXT or CSV list of up to 500 video URLs and remove duplicates.
2. Process one authorized video at a time using a persistent queue.
3. Send finished media to temporary cloud storage and schedule publication using supported APIs.
4. Confirm publication before removing the temporary cloud copy and processing the next job.

**Status:** Repository initialized; application code and deployment setup are not yet implemented.

Secrets must be stored in server environment variables, never committed to GitHub.
