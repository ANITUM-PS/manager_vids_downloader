# Video Classification Tools

A comprehensive toolkit for downloading, organizing, and manually classifying videos with manager detection results from AWS S3 storage.

## Overview

This repository contains two Python scripts designed to work together for video analysis and classification workflows:

1. **Video Downloader** (`video_downloader.py`) - Downloads videos from S3 based on manager detection timestamps
2. **Video Classification Tool** (`video_classifier.py`) - Interactive GUI for manually reviewing and classifying downloaded videos

## Features

### Video Downloader
- Downloads videos from AWS S3 based on DOCX analysis results
- Organizes videos by timestamp folders
- Tracks download history to avoid duplicates
- Supports multiple camera channels (channel502, channel602-2302)
- Automatically renames files based on detection status (found/not_found)

### Video Classification Tool
- Interactive multi-video grid display with synchronized playback
- Click-to-classify interface for manual review
- Automatic status tracking (classified videos marked in blue)
- CSV export of classification results
- Model vs manual classification comparison
- Pause/resume, rewind, and navigation controls

## Prerequisites

### Python Dependencies
```bash
pip install opencv-python numpy boto3 python-docx
```

### System Requirements
- Python 3.6+
- OpenCV with video codec support
- AWS credentials configured
- Sufficient disk space for video storage

### AWS Configuration
Ensure your AWS credentials are configured with access to the S3 bucket:
```bash
aws configure
```

## Usage

### Step 1: Download Videos

1. Prepare a DOCX file named `manager_matches_output.docx` containing manager detection results
2. Run the downloader:
```bash
python video_downloader.py
```
3. Enter the number of timestamps to process
4. Provide timestamps in `YYYYMMDDTHHMM` format (e.g., `20250624T1921`)

The script will:
- Parse the DOCX file for detection results
- Download relevant videos from S3
- Organize them in `~/Downloads/managerVids/YYYYMMDDTHHMM/` folders
- Rename files with detection status (`_found.mkv` or `_not_found.mkv`)

### Step 2: Classify Videos

1. Run the classification tool:
```bash
python video_classifier.py
```
2. Select a timestamp folder from the interactive menu
3. Use the GUI to review and classify videos:

#### Controls
- **Click any video** → Select for classification
- **T** → Mark as "FOUND" (manager present)
- **F** → Mark as "NOT_FOUND" (manager absent)
- **SPACEBAR** → Pause/resume playback
- **R** → Rewind all videos to beginning
- **ESC** → Cancel current selection
- **Q** → Quit and auto-classify remaining videos

#### Visual Indicators
- **Green border** → Currently selected video
- **Blue border** → Already classified video
- **Black border** → Unclassified video

## Output

### Classification Results
Results are saved to `video_classifications.csv` with columns:
- `video_name` - Original video identifier
- `model_status` - AI model prediction (FOUND/NOT_FOUND)
- `manual_status` - Manual classification result

### Summary Statistics
Upon exit, the tool displays:
- Total classifications performed
- Manual vs automatic classification counts
- Agreement rate between model and manual classifications

## File Structure

```
~/Downloads/managerVids/
├── 20250624T1921/
│   ├── channel502_20250624T192145_found.mkv
│   ├── channel602_20250624T192134_not_found.mkv
│   └── ...
├── 20250625T1415/
│   └── ...
└── video_classifications.csv
```

## Configuration

### Video Downloader Settings
Edit the configuration section in `video_downloader.py`:
```python
DOCX_FILE = "manager_matches_output.docx"
S3_BUCKET = "a2bvideos"
AWS_REGION = "ap-south-1"
BASE_DIR = os.path.expanduser("~/Downloads/managerVids")
```

### Video Classifier Settings
The classifier automatically detects folders in the base directory and provides interactive selection.

## Error Handling

- **Missing DOCX file**: Ensure `manager_matches_output.docx` exists in the script directory
- **AWS access denied**: Verify S3 bucket permissions and AWS credentials
- **No video files found**: Check folder selection and file extensions
- **OpenCV errors**: Ensure video codecs are properly installed

## Troubleshooting

### Common Issues

1. **Videos won't play**
   - Install additional video codecs
   - Check file integrity after download

2. **S3 download failures**
   - Verify AWS credentials and permissions
   - Check network connectivity
   - Confirm bucket name and region

3. **Classification tool crashes**
   - Ensure sufficient system memory
   - Close other applications using video resources
   - Check file permissions in output directory

## Contributing

When contributing to this project:
1. Test both scripts with sample data
2. Ensure CSV output format consistency
3. Maintain backward compatibility with existing classification files
4. Document any new configuration options

## License

This project is intended for internal video analysis workflows. Ensure compliance with your organization's data handling policies when processing video content.