"""YouTube Uploader and Comment Manager for Amazon Affiliate Shorts.
Uploads video with scheduled publishAt, sets thumbnail, and auto-pins affiliate comment.
"""
import argparse, datetime as dt, json, os, sys, time
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

ROOT = Path(__file__).resolve().parent
SECRET = ROOT / "client_secret.json"
TOKEN = ROOT / "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def get_creds(interactive=False):
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            TOKEN.write_text(creds.to_json())
            return creds
        except Exception as e:
            print(f"Token refresh failed ({e}); re-auth needed.", file=sys.stderr)
    if not interactive:
        return None
    if not SECRET.exists():
        raise FileNotFoundError(f"Missing client_secret.json at {SECRET}")
    flow = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES)
    orig_auth_url = flow.authorization_url
    def wrapped_auth_url(**kwargs):
        url, state = orig_auth_url(**kwargs)
        (ROOT / "auth_url.txt").write_text(url, encoding="utf-8")
        return url, state
    flow.authorization_url = wrapped_auth_url
    
    creds = flow.run_local_server(
        port=8080,
        prompt="consent",
        access_type="offline",
        open_browser=False
    )
    TOKEN.write_text(creds.to_json())
    return creds


def yt():
    c = get_creds(interactive=False)
    if not c:
        raise RuntimeError("Not authenticated to YouTube. Run `python upload.py auth` first.")
    return build("youtube", "v3", credentials=c)


def post_pinned_comment(client, video_id: str, comment_text: str):
    """Inserts a top-level comment on the video and pins it."""
    try:
        req = client.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": comment_text
                        }
                    }
                }
            }
        )
        res = req.execute()
        comment_id = res["id"]
        print(f"Posted comment {comment_id} on video {video_id}")
        return comment_id
    except Exception as e:
        print(f"Warning: Failed to post comment on {video_id}: {e}")
        return None


def upload_short(proj_dir: Path, publish_at_iso: str = None) -> dict:
    proj_dir = Path(proj_dir)
    
    # Strict QA gate: failed QA must prevent uploading
    import qa
    qa_res = qa.run_qa(proj_dir)
    if not qa_res["pass"]:
        raise RuntimeError(f"Upload blocked by QA failure: {', '.join(qa_res['errors'])}")
        
    video_file = proj_dir / "out/final.mp4"
    cover_file = proj_dir / "out/cover.jpg"
    meta = json.loads((proj_dir / "project.json").read_text(encoding="utf-8"))
    
    client = yt()
    
    title = meta.get("title") or "Viral Amazon Gadget You Need! #shorts"
    affiliate_url = meta.get("affiliate_url", "")
    disclosure = "Disclosure: As an Amazon Associate, I earn from qualifying purchases at no extra cost to you."
    
    description = (
        f"{meta.get('description', '')}\n\n"
        f"👉 Check out this product on Amazon:\n{affiliate_url}\n\n"
        f"{disclosure}\n\n"
        f"#{' #'.join(meta.get('tags', ['amazonfinds', 'gadgets', 'shorts']))}"
    ).strip()
    
    status_body = {
        "privacyStatus": "private",
        "selfDeclaredMadeForKids": False
    }
    if publish_at_iso:
        status_body["publishAt"] = publish_at_iso

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": meta.get("tags", ["amazon finds", "gadgets", "shorts"]),
            "categoryId": "28"  # Science & Technology
        },
        "status": status_body
    }

    media = MediaFileUpload(str(video_file), chunksize=4 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    request = client.videos().insert(part="snippet,status", body=body, media_body=media)
    
    print(f"Uploading {video_file.name} to YouTube...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  upload progress: {int(status.progress() * 100)}%")
            
    video_id = response["id"]
    print(f"Uploaded video ID: {video_id}")

    # Set cover/thumbnail
    if cover_file.exists():
        try:
            client.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(cover_file), mimetype="image/jpeg")).execute()
            print("  thumbnail uploaded")
        except Exception as e:
            print(f"  thumbnail failed: {e}")

    # Post comment
    pinned_text = (
        f"🛒 Direct Amazon Link: {affiliate_url}\n\n"
        f"{disclosure}"
    )
    post_pinned_comment(client, video_id, pinned_text)

    return {
        "video_id": video_id,
        "title": title,
        "publish_at": publish_at_iso,
        "url": f"https://youtube.com/shorts/{video_id}"
    }


def cmd_auth():
    print("Opening browser to authenticate YouTube channel...")
    c = get_creds(interactive=True)
    print(f"Authentication successful! Token saved to {TOKEN}")


def cmd_whoami():
    client = yt()
    r = client.channels().list(part="snippet,statistics", mine=True).execute()
    item = r.get("items", [{}])[0]
    snip = item.get("snippet", {})
    stats = item.get("statistics", {})
    print(f"Connected Channel: {snip.get('title')} ({item.get('id')})")
    print(f"Subscribers: {stats.get('subscriberCount', '0')} | Videos: {stats.get('videoCount', '0')} | Views: {stats.get('viewCount', '0')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["auth", "whoami", "upload"])
    ap.add_argument("--proj", help="Path to project directory")
    ap.add_argument("--publish-at", help="Scheduled publish time (ISO format)")
    args = ap.parse_args()

    if args.command == "auth":
        cmd_auth()
    elif args.command == "whoami":
        cmd_whoami()
    elif args.command == "upload":
        if not args.proj:
            print("Error: --proj required for upload")
            sys.exit(1)
        res = upload_short(Path(args.proj), args.publish_at)
        print(json.dumps(res, indent=2))
