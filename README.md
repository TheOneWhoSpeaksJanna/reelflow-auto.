# ReelFlow Auto

Mobile-friendly 500-link queue for **owned or licensed** video files, built for a free Wispbyte Python server.

## Deploy

1. Clone this GitHub repository on Wispbyte (branch: main).
2. Choose Python as the runtime.
3. Startup command: **python app.py**
4. Additional Python packages: **Flask requests**
5. Set environment variables on Wispbyte: **APP_PASSWORD**, **SECRET_KEY**, **BUFFER_API_KEY**.
6. Optional Cloudinary storage: **CLOUDINARY_CLOUD_NAME**, **CLOUDINARY_API_KEY**, **CLOUDINARY_API_SECRET**.
7. Start the server and open the assigned website. Check /healthz for a health response.
8. Sign in, refresh Buffer channels, select YouTube and TikTok and save settings.
9. Import direct HTTPS MP4 files and click Start Queue.

The repository's name ends in a period: **reelflow-auto.**. The clone URL therefore ends in **reelflow-auto..git**. Rename in GitHub Settings if needed.

## Upload format

One direct video file URL per line, or:

    source-reference-url | authorized-direct-video-url

A normal YouTube watch page is accepted into the queue as **Needs source**, but is not downloaded or republished automatically.

## How it works

One job is scheduled at a time through the official Buffer API. Temporary Cloudinary media stays available until all Buffer posts report sent. Afterwards the remote temporary file is deleted and the next job starts. If the publishing result is uncertain, the queue pauses for manual review.

## Limitations

This first version does not cut clips, generate burned-in subtitles or transcribe speech. Videos should already be prepared for Shorts and Reels. Buffer, Cloudinary and Wispbyte quotas apply; 500 URLs will not publish instantly. Live integration requires your accounts and real hosting tests.

Run local checks with:

    python -m pip install -r requirements.txt
    python -m unittest discover -s tests -v

API references: https://developers.buffer.com/ and https://wispbyte.com/kb/startup-settings

## Automatic captions

For authorized video files, leave the optional caption template blank. ReelFlow automatically creates a title from the video file name and adds platform-specific hashtags. To customize copy, set a template containing {title}. This is a free rule-based caption generator, not speech transcription or scene analysis.

**YouTube watch pages are not video files.** Importing a YouTube watch URL cannot automatically retrieve, edit, or republish third-party copyrighted uploads. For a completely unattended workflow, provide a direct hosted video file that you own or have permission to republish.
