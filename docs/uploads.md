# Upload speed tuning

## Server chunk uploads (fallback mode)

These settings control the browser → Django chunked upload flow (`/upload/chunk/`).

- `UPLOAD_CHUNK_SIZE` (bytes)
  - Default: `5242880` (5MB)
  - Larger chunks = fewer HTTP requests (usually faster), but each request is bigger.
- `UPLOAD_PARALLEL_CHUNKS`
  - Default: `3` (capped to `4` in settings)
  - More parallelism can improve speed on fast networks, but increases load on the server/proxy.

## Direct-to-Cloudinary uploads (fast path)

When Cloudinary is configured, the upload page can upload directly to Cloudinary (skips proxying the file through Django).

Required environment variables:

- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

Optional:

- `ALLOW_UNSIGNED_UPLOAD=1` and `CLOUDINARY_UPLOAD_PRESET=<preset>` (needed for very large direct uploads that use Cloudinary’s chunked upload API)

