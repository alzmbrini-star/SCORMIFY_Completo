# Optional HeyGem / Duix.Avatar GPU bridge (proof of concept)

This is an adapter for the official self-hosted `/easy/submit` and `/easy/query`
video API. It is **not** the commercial Duix conversational API. It is not
installed or activated by deploying SCORMIFY to Render.

## GPU operator prerequisites

1. Provision and secure an NVIDIA GPU server compatible with the official
   [Duix.Avatar deployment](https://github.com/duixcom/Duix-Avatar).
   Review the code/model licenses and obtain avatar/voice permission.
2. Run the official video service with persistent data mounted at `/code/data`.
   Place authorized MP4 base videos in `/code/data/avatars/`.
3. Build this directory's Dockerfile. Mount the **same** volume at `/code/data`
   and join the internal Docker network of the video service. Run **one** bridge
   process/replica; its idempotency lock is process-local.
4. Set `HEYGEM_NATIVE_URL` to the internal video API base, normally
   `http://duix-avatar-gen-video:8383/easy`. Do not expose this native port publicly.
5. Set `HEYGEM_BRIDGE_KEY` to a separately generated secret of at least 24
   characters; never put it in frontend configuration or a course export.
6. Set `HEYGEM_AVATARS_JSON`, for example:

   ```json
   [{"id":"instructor","name":"Authorized instructor","path":"avatars/instructor.mp4"}]
   ```

7. Put the bridge behind authenticated HTTPS, a firewall allowing only the
   SCORMIFY backend, and a reverse proxy with a 12 MB request-body limit.
   Do not mount unrelated host directories. Configure GPU concurrency and monitor
   disk usage/retention of job audio, base videos and results on this server.

## SCORMIFY backend configuration

- `HEYGEM_BRIDGE_URL`: HTTPS base of **this bridge**, not `app.duix.ai` or the
  native GPU `/easy` endpoint.
- `HEYGEM_BRIDGE_KEY`: same bridge secret.
- `ELEVENLABS_API_KEY`: existing PT-BR TTS integration. Voice IDs must belong to
  that account and support multilingual generation.

The UI reports disabled until these settings are available. Avatar choices are
read from the bridge; no fabricated stock-avatar list is shown. Render only
orchestrates jobs; GPU inference runs on the separate machine. No infrastructure
is automatically purchased or configured.

Generation requires an editor/admin role and the company's existing avatar
(`heygen`) and ElevenLabs permissions. These permissions authorize access only;
the HeyGen API key, jobs and credits are never used by HeyGem.

## Workflow and limits

Editor: Create avatar → HeyGem → choose avatar, ElevenLabs voice ID and PT-BR
script (max 1000 characters), confirm permission, generate and review. Generated
videos have a separate HeyGem library. In Agent → Media → Avatar HeyGem, generate
and review **before** confirming media; only a completed video is used in the
course. This first phase does not batch-generate HeyGem videos after course
creation and does not automatically align quiz pauses. Use Editor's Video with
Questions and review timestamps manually.

Generation uses ElevenLabs credits and GPU resources, not HeyGen credits.
Polling/recovering an existing UUID never submits a new video. If the backend
restarts during TTS preparation, the request may remain pending; inspect it before
starting another paid generation. The bridge reserves UUIDs before GPU submit;
an ambiguous submission is never automatically retried.

Completed MP4s (max 256 MB) are streamed into MongoDB GridFS before being marked
completed, with Range support for playback. A random asset URL is publicly
readable, like existing course assets: do not use this to publish confidential
recordings. Videos are private in the library by author. No expiring provider URL
is saved in slides. Exported files must actually embed the completed asset for
offline use. This phase does not promise transparency, instant results, or native
PT-BR voice cloning. Perform a 20–30 second authorized quality test before rollout.
