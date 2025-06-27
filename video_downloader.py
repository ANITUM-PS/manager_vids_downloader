import os
import boto3
import json
import re
import random
import numpy as np
import cv2
from docx import Document
from datetime import datetime, timedelta
from collections import defaultdict

# ====== CONFIGURATION ======
DOCX_FILE = "manager_matches_output.docx"
LOG_FILE = "downloaded_log.json"
S3_BUCKET = "a2bvideos"
AWS_REGION = "ap-south-1"
BASE_DIR = os.path.expanduser("~/Downloads/managerVids")
# ===========================

def parse_docx_group_by_HHMM(path):
    doc = Document(path)
    hhmm_map = defaultdict(list)
    pattern = r'channel(\d+)_([0-9]{8}T[0-9]{6})_manager_detections\.txt'

    for para in doc.paragraphs:
        text = para.text
        status = None
        if "'status': 'Found'" in text:
            status = 'found'
        elif "'status': 'Not Found'" in text:
            status = 'not_found'
        matches = re.findall(pattern, text)
        for channel, full_ts in matches:
            hhmmss = full_ts[-6:]
            hhmm = hhmmss[:4]
            date = full_ts[:8]
            hhmm_map[(date, hhmm)].append({
                "channel": f"channel{channel}",
                "full_ts": full_ts,
                "hhmmss": hhmmss,
                "status": status
            })
    return hhmm_map

def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_log(log_set):
    with open(LOG_FILE, 'w') as f:
        json.dump(list(log_set), f, indent=2)

def download_from_s3(s3_client, key, destination):
    try:
        s3_client.download_file(S3_BUCKET, key, destination)
        print(f"✅ Downloaded: {key}")
        return True
    except Exception as e:
        print(f"❌ Failed: {key} - {e}")
        return False

def pad_to_height(img, target_height):
    h, w = img.shape[:2]
    pad_top = (target_height - h) // 2
    pad_bottom = target_height - h - pad_top
    return cv2.copyMakeBorder(img, pad_top, pad_bottom, 0, 0, cv2.BORDER_CONSTANT, value=0)

def overlay_text(img, text):
    overlay = img.copy()
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness = 1
    text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
    text_x = (img.shape[1] - text_size[0]) // 2
    text_y = img.shape[0] - 10
    cv2.putText(overlay, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    return overlay

def download_videos_by_timestamps(selected_keys):
    hhmm_map = parse_docx_group_by_HHMM(DOCX_FILE)
    downloaded_log = load_log()
    s3 = boto3.client("s3", region_name=AWS_REGION)

    channel_list = ['channel502'] + [f'channel{i}' for i in range(602, 2403, 100)]

    for key in selected_keys:
        if key not in hhmm_map:
            print(f"⚠️ Skipping {key}: not found in document.")
            continue

        related_entries = hhmm_map[key]
        date, hhmm = key
        base_ts = f"{date}T{hhmm}"
        folder_path = os.path.join(BASE_DIR, base_ts)
        os.makedirs(folder_path, exist_ok=True)

        for channel in channel_list:
            entry_match = next((e for e in related_entries if e["channel"] == channel), None)

            if entry_match:
                full_ts = entry_match["full_ts"]
                status = entry_match["status"]
                filename = f"{channel}_{full_ts}.mkv"
                s3_key = filename
                new_filename = filename.replace(".mkv", f"_{status}.mkv")
                local_path = os.path.join(folder_path, new_filename)

                if s3_key in downloaded_log:
                    continue

                if download_from_s3(s3, s3_key, local_path):
                    downloaded_log.add(s3_key)
            else:
                print(f"ℹ️ No entry for {channel} at {date}{hhmm}")

    save_log(downloaded_log)
    print("🎉 All downloads complete.")

def main():
    try:
        target_count = int(input("Enter number of timestamps to process with at least one video: "))
        start_ts = input("Enter starting timestamp in <YYYYMMDD>THHMM format (e.g., 20250624T1921): ").strip()
        if not re.match(r'^\d{8}T\d{4}$', start_ts):
            print("❌ Invalid format. Please use YYYYMMDDTHHMM.")
            return

        found_count = 0
        current_time = datetime.strptime(start_ts, "%Y%m%dT%H%M")
        end_of_day = datetime.strptime(start_ts[:8] + "T2359", "%Y%m%dT%H%M")
        selected_keys = []

        hhmm_map = parse_docx_group_by_HHMM(DOCX_FILE)
        downloaded_log = load_log()

        while found_count < target_count and current_time <= end_of_day:
            date_str = current_time.strftime("%Y%m%d")
            hhmm_str = current_time.strftime("%H%M")
            key = (date_str, hhmm_str)

            if key in hhmm_map:
                temp_log = set(downloaded_log)  # Snapshot before
                download_videos_by_timestamps([key])
                downloaded_log = load_log()  # Reload after
                if len(downloaded_log) > len(temp_log):
                    found_count += 1
                    print(f"✅ Count {found_count}/{target_count} fulfilled at {key}")
                else:
                    print(f"ℹ️ No videos downloaded for {key}, skipping count.")
            else:
                print(f"⚠️ {key} not in DOCX entries, skipping.")

            current_time += timedelta(minutes=1)

        if found_count < target_count:
            print(f"⏹️ Stopped at end of day. Only {found_count}/{target_count} timestamps fulfilled.")
        else:
            print("🎉 Target timestamps processed with videos downloaded.")

    except Exception as e:
        print(f"⚠️ Error: {e}")

if __name__ == "__main__":
    main()
