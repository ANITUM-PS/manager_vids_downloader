#!/usr/bin/env python3
import os
import glob
import cv2
import numpy as np
import re
import csv
from datetime import datetime

# Global variables for click handling
click_coords = None
grid_info = {}
pending_classification = None
paused = False

def get_available_folders(base_path):
    """Get all available folders in the base path"""
    if not os.path.exists(base_path):
        raise FileNotFoundError(f"Base path does not exist: {base_path}")
    
    folders = [f for f in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, f))]
    if not folders:
        raise FileNotFoundError(f"No folders found in {base_path}")
    
    return sorted(folders, reverse=True)

def select_folder(base_path):
    """Interactive folder selection"""
    folders = get_available_folders(base_path)
    
    print(f"\nAvailable folders in {base_path}:")
    print("-" * 50)
    for i, folder in enumerate(folders, 1):
        print(f"{i:2d}. {folder}")
    print("-" * 50)
    
    while True:
        try:
            choice = input(f"Select folder (1-{len(folders)}) or 'q' to quit: ").strip()
            if choice.lower() == 'q':
                print("Exiting...")
                exit(0)
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(folders):
                selected_folder = folders[choice_num - 1]
                folder_path = os.path.join(base_path, selected_folder)
                print(f"Selected: {selected_folder}")
                return folder_path
            else:
                print(f"Please enter a number between 1 and {len(folders)}")
        except ValueError:
            print("Please enter a valid number or 'q' to quit")

def extract_label_and_info(filename):
    """
    Extract channel, status, and original name from filenames like:
    channel502_20250618T145831_found.mkv
    -> Returns: (display_label, original_name, model_status)
    """
    base = os.path.basename(filename)
    # Extract the parts using regex
    match = re.match(r'(channel\d+)_(\d+T\d+)_(\w+)', base)
    if match:
        channel = match.group(1)
        timestamp = match.group(2)
        status = match.group(3).upper()
        
        # Create display label
        display_label = f"{channel}_{status}"
        
        # Create original name (without status)
        original_name = f"{channel}_{timestamp}"
        
        # Map status to standardized format
        model_status = "FOUND" if status == "FOUND" else "NOT_FOUND"
        
        return display_label, original_name, model_status
    else:
        return base, base, "UNKNOWN"  # fallback

def draw_label_below(frame, text, width=320, height=240, highlight=False):
    label_height = 30
    # Use different color for highlighted video
    bg_color = (0, 100, 0) if highlight else (0, 0, 0)
    label = np.full((label_height, width, 3), bg_color, dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_color = (255, 255, 255)
    cv2.putText(label, text, (5, 20), font, 0.6, text_color, 1)
    return np.vstack((frame, label))

def draw_instruction_overlay(frame, video_name, model_status):
    """Draw instruction overlay on the frame"""
    overlay = frame.copy()
    height, width = frame.shape[:2]
    
    # Semi-transparent background
    cv2.rectangle(overlay, (50, height//2 - 80), (width - 50, height//2 + 80), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
    
    # Instructions with better formatting
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(frame, f"CLASSIFYING:", (60, height//2 - 50), font, 0.8, (255, 255, 0), 2)
    cv2.putText(frame, f"{video_name}", (60, height//2 - 20), font, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, f"Model prediction: {model_status}", (60, height//2 + 10), font, 0.6, (200, 200, 200), 2)
    cv2.putText(frame, "Press 'T' for FOUND, 'F' for NOT_FOUND", (60, height//2 + 40), font, 0.6, (0, 255, 0), 2)
    cv2.putText(frame, "Press 'ESC' to cancel", (60, height//2 + 65), font, 0.5, (0, 255, 255), 1)
    
    return frame

def draw_status_bar(frame):
    """Draw a status bar at the top"""
    height, width = frame.shape[:2]
    # Create status bar
    status_bar = np.zeros((40, width, 3), dtype=np.uint8)
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # Show pause status
    pause_text = "[PAUSED]" if paused else "[PLAYING]"
    pause_color = (0, 255, 255) if paused else (0, 255, 0)
    
    if pending_classification is None:
        cv2.putText(status_bar, f"{pause_text} Click video to classify | SPACE=Pause/Play | R=Rewind | Q=Quit", 
                   (10, 25), font, 0.5, pause_color, 1)
    else:
        cv2.putText(status_bar, f"{pause_text} Classification mode: Press T/F or ESC to cancel", 
                   (10, 25), font, 0.5, (0, 255, 255), 1)
    
    return np.vstack((status_bar, frame))

def mouse_callback(event, x, y, flags, param):
    global click_coords
    if event == cv2.EVENT_LBUTTONDOWN:
        # Adjust for status bar height
        click_coords = (x, y - 40)

def get_clicked_video_index(x, y, cols, rows, frame_width, frame_height, total_videos):
    """Determine which video was clicked based on coordinates"""
    # Return None if click is above the video area (in status bar)
    if y < 0:
        return None
    
    label_height = 30
    video_height_with_label = frame_height + label_height
    
    col = x // frame_width
    row = y // video_height_with_label
    
    if col >= cols or row >= rows:
        return None
    
    index = row * cols + col
    return index if index < total_videos else None

def rewind_all_videos(caps, video_done):
    """Rewind all videos to the beginning"""
    for i, cap in enumerate(caps):
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        video_done[i] = False
    print("All videos rewound to beginning")

def save_to_csv(original_name, model_status, manual_status, csv_filename="video_classifications.csv"):
    """Save the classification data to CSV file"""
    file_exists = os.path.isfile(csv_filename)
    
    with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['video_name', 'model_status', 'manual_status']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Write header if file is new
        if not file_exists:
            writer.writeheader()
        
        # Write the data
        writer.writerow({
            'video_name': original_name,
            'model_status': model_status,
            'manual_status': manual_status
        })
    
    print(f"✓ Saved: {original_name} | Model: {model_status} | Manual: {manual_status}")

def print_summary(csv_filename="video_classifications.csv"):
    """Print a summary of classifications when quitting"""
    if os.path.exists(csv_filename):
        try:
            with open(csv_filename, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                data = list(reader)
                
            if data:
                print("\n" + "="*60)
                print("CLASSIFICATION SUMMARY")
                print("="*60)
                print(f"Total classifications: {len(data)}")
                
                # Count agreements/disagreements
                agreements = sum(1 for row in data if row['model_status'] == row['manual_status'])
                disagreements = len(data) - agreements
                
                print(f"Model-Manual agreements: {agreements}")
                print(f"Model-Manual disagreements: {disagreements}")
                
                if len(data) > 0:
                    accuracy = (agreements / len(data)) * 100
                    print(f"Agreement rate: {accuracy:.1f}%")
                
                print(f"\nData saved to: {csv_filename}")
                print("="*60)
        except Exception as e:
            print(f"Could not read summary from {csv_filename}: {e}")

def main():
    global click_coords, grid_info, pending_classification, paused
    
    base_path = os.path.expanduser("~/Downloads/managerVids")
    
    # Interactive folder selection
    try:
        folder = select_folder(base_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    print("="*60)
    print("VIDEO CLASSIFICATION TOOL")
    print("="*60)
    print(f"Working with folder: {os.path.basename(folder)}")
    print("\nInstructions:")
    print("• SPACEBAR to pause/resume video playback")
    print("• R to rewind all videos to the beginning")
    print("• Click on any video to classify it manually")
    print("• When a video is selected, press:")
    print("  - 'T' for FOUND (manager is present)")
    print("  - 'F' for NOT_FOUND (manager is not present)")
    print("  - 'ESC' to cancel selection")
    print("• Press 'Q' to quit and see summary")
    print("• Results are automatically saved to 'video_classifications.csv'")
    print("-" * 60)

    video_files = sorted(glob.glob(os.path.join(folder, "*.*")))
    video_files = [f for f in video_files if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))]

    if not video_files:
        print("No video files found.")
        return

    print(f"Found {len(video_files)} video files")
    
    caps = [cv2.VideoCapture(f) for f in video_files]
    
    # Extract labels and info for each video
    video_info = []
    for f in video_files:
        label, original_name, model_status = extract_label_and_info(f)
        video_info.append({
            'file': f,
            'label': label,
            'original_name': original_name,
            'model_status': model_status
        })

    frame_width, frame_height = 320, 240
    video_done = [False] * len(caps)
    
    # Calculate grid dimensions
    total = len(video_files)
    cols = int(np.ceil(np.sqrt(total)))
    rows = (total + cols - 1) // cols
    
    print(f"Display grid: {rows}x{cols}")
    print("=" * 60)
    
    # Store grid info globally for click handling
    grid_info = {
        'cols': cols,
        'rows': rows,
        'frame_width': frame_width,
        'frame_height': frame_height,
        'total_videos': total,
        'video_info': video_info
    }

    # Set up the window and mouse callback
    cv2.namedWindow("Video Classification Tool", cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback("Video Classification Tool", mouse_callback)

    try:
        while True:
            frames = []
            for i, (cap, info) in enumerate(zip(caps, video_info)):
                if not video_done[i] and not paused:
                    ret, frame = cap.read()
                    if ret:
                        frame = cv2.resize(frame, (frame_width, frame_height))
                    else:
                        video_done[i] = True
                        frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
                elif not video_done[i] and paused:
                    # When paused, get current frame without advancing
                    current_pos = cap.get(cv2.CAP_PROP_POS_FRAMES)
                    ret, frame = cap.read()
                    if ret:
                        frame = cv2.resize(frame, (frame_width, frame_height))
                        # Go back one frame to stay on current frame
                        cap.set(cv2.CAP_PROP_POS_FRAMES, current_pos)
                    else:
                        video_done[i] = True
                        frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)
                else:
                    frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)

                # Highlight if this video is being classified
                highlight = (pending_classification is not None and 
                            pending_classification['index'] == i)
                
                labeled_frame = draw_label_below(frame, info['label'], 
                                               width=frame_width, height=frame_height,
                                               highlight=highlight)
                frames.append(labeled_frame)

            if all(video_done) and not paused:
                # Reset videos to loop
                for i, cap in enumerate(caps):
                    if video_done[i]:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        video_done[i] = False

            # Pad with empty frames if needed
            while len(frames) < rows * cols:
                empty = np.zeros_like(frames[0])
                frames.append(empty)

            # Create grid
            grid = []
            for r in range(rows):
                row = frames[r * cols:(r + 1) * cols]
                grid.append(np.hstack(row))
            final_img = np.vstack(grid)

            # Add status bar
            final_img = draw_status_bar(final_img)

            # If we're in classification mode, add overlay
            if pending_classification is not None:
                final_img = draw_instruction_overlay(
                    final_img, 
                    pending_classification['original_name'],
                    pending_classification['model_status']
                )

            cv2.imshow("Video Classification Tool", final_img)
            
            # Handle key presses
            key = cv2.waitKey(30) & 0xFF
            
            if key == ord('q') or key == ord('Q'):
                break
            elif key == ord(' '):  # Spacebar to pause/unpause
                paused = not paused
                status = "PAUSED" if paused else "RESUMED"
                print(f"Video playback {status}")
            elif key == ord('r') or key == ord('R'):  # R to rewind
                rewind_all_videos(caps, video_done)
            elif pending_classification is not None:
                # We're in classification mode
                if key == ord('t') or key == ord('T'):
                    # User says FOUND
                    save_to_csv(
                        pending_classification['original_name'],
                        pending_classification['model_status'],
                        'FOUND'
                    )
                    pending_classification = None
                elif key == ord('f') or key == ord('F'):
                    # User says NOT_FOUND
                    save_to_csv(
                        pending_classification['original_name'],
                        pending_classification['model_status'],
                        'NOT_FOUND'
                    )
                    pending_classification = None
                elif key == 27:  # ESC key
                    print("Classification cancelled")
                    pending_classification = None
            
            # Check for mouse clicks (only when not in classification mode)
            if click_coords is not None and pending_classification is None:
                x, y = click_coords
                clicked_index = get_clicked_video_index(
                    x, y, cols, rows, frame_width, frame_height, total
                )
                
                if clicked_index is not None and clicked_index < len(video_info):
                    info = video_info[clicked_index]
                    print(f"Selected: {info['original_name']} (Model: {info['model_status']}) -> Press T/F to classify...")
                    
                    # Enter classification mode
                    pending_classification = {
                        'index': clicked_index,
                        'original_name': info['original_name'],
                        'model_status': info['model_status']
                    }
                
                click_coords = None  # Reset click coordinates

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        for cap in caps:
            cap.release()
        cv2.destroyAllWindows()
        print_summary()

if __name__ == "__main__":
    main()