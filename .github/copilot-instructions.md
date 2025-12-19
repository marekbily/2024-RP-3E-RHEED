# AI Coding Agent Instructions for 2024-RP-3E-RHEED

## Project Overview
RHEED (Reflection High-Energy Electron Diffraction) Analysis application built in Python with PyQt5/silx for processing video/image data from MBE (Molecular Beam Epitaxy) growth and material characterization. The app provides live camera capture, video file playback, ROI (Region of Interest) analysis, and statistical visualization.

## Architecture & Key Components

### Entry Point
- **[src/__main__.py](src/__main__.py)** - Application entry point (`python src/__main__.py`)
- **[src/gui/plotROIStats.py](src/gui/plotROIStats.py)** - Main GUI window (`_RoiStatsDisplayExWindow`), integrates StackView, ROI manager, and statistics display

### Core Modules

#### Camera System (`src/camera/`)
- **[opencv_capture.py](src/camera/opencv_capture.py)** - `CameraInit` class handles camera initialization, frame capture, and HDF5 recording
  - Supports multiple backends (DSHOW on Windows, v4l2 on Linux)
  - Frame storage: single-frame buffer (`latest_frame`) for live display, expandable HDF5 dataset for recording
  - Dataset auto-resizes in 1000-frame chunks when recording exceeds current size
- **pyPOACamera.py** - PlayerOne camera driver (advanced feature, rarely used)

#### GUI Components (`src/gui/`)
- **roiwidget.py** - `roiManagerWidget` - ROI creation/editing toolbar, uses silx's `RegionOfInterestManager`
- **roidictionary.py** - ROI serialization (save/load), maps ROI types to JSON structures
- **statswindow.py** - `roiStatsWindow` - Real-time statistics display (mean intensity, time-series plots)
- **camera_connect_dialog.py** - Camera backend selection and port enumeration
- **camera_settings_dialog.py** - Per-camera property controls (FPS, exposure, gain, etc.)
- **file_dialog.py** - Video/H5 file loading, `H5Playback` class for HDF5 playback

## Critical Workflows

### Launching Application
```bash
pip install -r requirements.txt
python src/__main__.py
```

### Camera Connection Flow
1. User clicks "Camera" → "Connect camera" in menu
2. `CameraConnectWindow` enumerates available cameras via `cv2_enumerate_cameras`
3. User selects backend (DSHOW/v4l2/etc) and port number, sets FPS
4. Emits `backendValuePicked` signal → `_camera_init()` in main window
5. `CameraInit` opens camera with `cv2.VideoCapture(port, backend)`, captures initial frame
6. Main window starts `_camera_loop` timer (100ms) to continuously call `camera.capture_frame()`

### Recording Workflow
- Camera → Live frame in `latest_frame[0]` (circular buffer, ~1-5 MB)
- **Enable recording** → Creates HDF5 dataset with initial size of 2000 frames
- Frames written to HDF5 as they arrive; dataset auto-resizes when full
- **Disable recording** → Closes HDF5 file, retains latest frame in buffer

### ROI Management
- ROI Manager integrates with silx `StackView` (displays image stack, allows drawing)
- ROI types: Point, Circle, Rectangle, Polygon, Line, etc.
- **Save ROI state** → Serialized to INI files (e.g., `roi_save_04-03-2025_18-15-57.ini`)
- **Statistics** → Computed over selected ROIs on current frame/video frame

## Project-Specific Patterns

### Qt Signal/Slot Communication
- Window dialogs emit custom signals instead of blocking: `camera_connect_dialog` emits `backendValuePicked(port, backend, name, fps)` → connected to `_camera_init()`
- Avoid modal dialogs; use signal/slot to decouple UI components

### Configuration Persistence
- **camera_config.txt** - Simple text file with 23 numeric camera parameters (one per line)
  - Loaded/saved by `CameraSettingsWindow.load_config_values()` / `.save_config_values()`
  - Avoid JSON; maintain line-based format for compatibility

### Data Storage
- **HDF5** - Primary format for large frame sequences, resizable datasets with auto-grow logic
- **INI** - ROI configurations (via silx's `dictdump`)
- **PNG/JPEG** - Individual frame caching in `cacheimg/` folder

### Frame Data Format
- Frames stored as **float32** arrays, shape `(1, H, W)` for single frames, `(N, H, W)` for stacks
- Conversion: OpenCV captures BGR → convert to grayscale with `cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)`

## Key Dependencies & Integration Points

- **silx** - `StackView`, ROI manager, colormap utilities (v2.2.2)
- **PyQt5** - Entire GUI framework (via `silx.gui.qt` abstraction)
- **OpenCV** - Camera capture and backend enumeration (v4.12.0)
- **h5py** - HDF5 file I/O (v3.15.1)
- **numpy** - Array operations (v2.3.5)

## Common Pitfalls & Conventions

1. **Camera port numbering**: Integrated webcam = 0, external/virtual = 1+, -1 reserved for auto-detect
2. **Thread safety**: All Qt operations must run on main thread; camera loop uses Qt timer (100ms), not background thread
3. **Dataset resizing**: Always check `frame_index >= dataset_size` before writing; resize in 1000-frame increments
4. **Window cleanup**: Use `try/except` when stopping camera (may fail if already closed), always call `cleanup()` to release resources
5. **Naming**: Camera dialogs use `Window` suffix (e.g., `CameraConnectWindow`), helpers use lowercase (e.g., `roiManagerWidget`)

## Testing & Debugging

- No automated tests present; focus on manual testing of camera/file workflows
- Enable debug output with `print()` statements in `_camera_loop()`, `capture_frame()`, and `_open_file()`
- Profiling data: `cprofile_out.txt` and `pstats_parse.py` exist for performance analysis
- Check for stale `.h5` files in `cacheimg/` that may consume disk space

## File Organization Notes

- Backup/archived files use `_` prefix (`_opencv_capture copy.py`, `_rheed.py`)
- ROI state files timestamped as `roi_save_DD-MM-YYYY_HH-MM-SS.ini`
- Documentation in `docs/` (Czech language TeX source, presentation files)
