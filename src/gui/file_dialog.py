from silx.gui import qt
import imageio.v3 as iio
import imageio_ffmpeg
import h5py
import numpy as np
import os
import time

def get_cache_dir():
    """Return path to cacheimg folder under current working directory and ensure it exists."""
    cache_dir = os.path.join(os.getcwd(), 'cacheimg')
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except Exception:
        pass
    return cache_dir


class VideoConversionWorker(qt.QThread):
    """Background worker for video to H5 conversion."""
    progress = qt.Signal(int, int)  # current_frame, total_frames
    finished = qt.Signal(str)  # result path or empty on error
    error = qt.Signal(str)  # error message
    
    def __init__(self, video_path, h5_path, total_frames):
        super().__init__()
        self.video_path = video_path
        self.h5_path = h5_path
        self.total_frames = total_frames
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        try:
            with h5py.File(self.h5_path, 'w') as h5_file:
                frame_iter = iio.imiter(self.video_path)
                
                try:
                    first_frame = next(frame_iter)
                except StopIteration:
                    self.error.emit("Video contains no frames")
                    return
                
                # Convert to grayscale if color
                first_frame = self._to_grayscale(first_frame)
                frame_shape = first_frame.shape
                dtype = first_frame.dtype
                
                # Pre-allocate dataset if we know total frames, otherwise use resizable
                if self.total_frames > 0:
                    dataset = h5_file.create_dataset(
                        'video_frames',
                        shape=(self.total_frames,) + frame_shape,
                        chunks=(1,) + frame_shape,
                        dtype=dtype,
                        compression='lzf'  # lzf is ~2-3x faster than gzip
                    )
                else:
                    # Fallback to resizable dataset if frame count unknown
                    dataset = h5_file.create_dataset(
                        'video_frames',
                        shape=(0,) + frame_shape,
                        maxshape=(None,) + frame_shape,
                        chunks=(1,) + frame_shape,
                        dtype=dtype,
                        compression='lzf'
                    )
                
                # Write first frame
                if self.total_frames > 0:
                    dataset[0] = first_frame
                else:
                    dataset.resize((1,) + frame_shape)
                    dataset[0] = first_frame
                    
                count = 1
                self.progress.emit(count, self.total_frames)
                
                # Process remaining frames
                for frame in frame_iter:
                    if self._cancelled:
                        self.error.emit("Conversion cancelled")
                        return
                    
                    frame = self._to_grayscale(frame, dtype)
                    
                    if self.total_frames > 0:
                        # Pre-allocated: direct write
                        if count < self.total_frames:
                            dataset[count] = frame
                    else:
                        # Resizable: need to grow
                        dataset.resize((count + 1,) + frame_shape)
                        dataset[count] = frame
                    
                    count += 1
                    self.progress.emit(count, self.total_frames)
                
                # Trim dataset if we got fewer frames than expected
                if self.total_frames > 0 and count < self.total_frames:
                    dataset.resize((count,) + frame_shape)
            
            self.finished.emit(self.h5_path)
            
        except Exception as e:
            self.error.emit(str(e))
    
    def _to_grayscale(self, frame, dtype=None):
        """Convert frame to grayscale if it has color channels."""
        if dtype is None:
            dtype = frame.dtype
        if frame.ndim == 3 and frame.shape[2] in [3, 4]:
            return np.dot(frame[..., :3], [0.299, 0.587, 0.114]).astype(dtype)
        elif frame.ndim == 3 and frame.shape[0] in [3, 4]:
            return np.dot(frame[:3].transpose(1, 2, 0), [0.299, 0.587, 0.114]).astype(dtype)
        return frame


class ConversionProgressDialog(qt.QDialog):
    """Progress dialog for video conversion with cancel support."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Converting Video")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() & ~qt.Qt.WindowContextHelpButtonHint)
        
        layout = qt.QVBoxLayout(self)
        
        self.label = qt.QLabel("Converting video to HDF5 format...")
        layout.addWidget(self.label)
        
        self.progressBar = qt.QProgressBar()
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        layout.addWidget(self.progressBar)
        
        self.frameLabel = qt.QLabel("Frame 0 / 0")
        layout.addWidget(self.frameLabel)
        
        self.etaLabel = qt.QLabel("Estimated time remaining: calculating...")
        layout.addWidget(self.etaLabel)
        
        self.cancelButton = qt.QPushButton("Cancel")
        self.cancelButton.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancelButton)
        
        self.worker = None
        self.result_path = None
        self._was_cancelled = False
        self._start_time = None
    
    def start_conversion(self, video_path, h5_path, total_frames):
        """Start the background conversion."""
        self.progressBar.setMaximum(total_frames if total_frames > 0 else 0)
        self.frameLabel.setText(f"Frame 0 / {total_frames}")
        self._start_time = time.time()
        
        self.worker = VideoConversionWorker(video_path, h5_path, total_frames)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()
    
    def _format_time(self, seconds):
        """Format seconds into human-readable time string."""
        if seconds < 0:
            return "calculating..."
        seconds = int(seconds)
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            mins, secs = divmod(seconds, 60)
            return f"{mins}m {secs}s"
        else:
            hours, remainder = divmod(seconds, 3600)
            mins, secs = divmod(remainder, 60)
            return f"{hours}h {mins}m {secs}s"
    
    def _on_progress(self, current, total):
        self.progressBar.setValue(current)
        self.frameLabel.setText(f"Frame {current} / {total}")
        
        # Calculate ETA (wait 8 seconds for rate to stabilize)
        if self._start_time and current > 0 and total > 0:
            elapsed = time.time() - self._start_time
            if elapsed < 8:
                self.etaLabel.setText("Estimated time remaining: calculating...")
            else:
                rate = current / elapsed  # frames per second
                remaining_frames = total - current
                if rate > 0:
                    eta_seconds = remaining_frames / rate
                    self.etaLabel.setText(f"Estimated time remaining: {self._format_time(eta_seconds)}")
                else:
                    self.etaLabel.setText("Estimated time remaining: calculating...")
        else:
            self.etaLabel.setText("Estimated time remaining: calculating...")
    
    def _on_finished(self, path):
        self.result_path = path
        self.accept()
    
    def _on_error(self, message):
        if not self._was_cancelled:
            qt.QMessageBox.critical(self, "Conversion Error", message)
        self.reject()
    
    def _on_cancel(self):
        self._was_cancelled = True
        if self.worker:
            self.worker.cancel()
        self.cancelButton.setEnabled(False)
        self.cancelButton.setText("Cancelling...")
    
    def wait_for_worker(self):
        """Wait for the worker thread to finish (call after dialog closes)."""
        if self.worker and self.worker.isRunning():
            self.worker.wait(5000)  # Wait up to 5 seconds
    
    def closeEvent(self, event):
        """Handle window close as cancel."""
        if self.worker and self.worker.isRunning():
            self._on_cancel()
            self.worker.wait(2000)  # Wait up to 2 seconds
        super().closeEvent(event)


def get_video_frame_count(video_path):
    """Get the total frame count from a video file using metadata."""
    try:
        # Try to get frame count from metadata
        meta = iio.immeta(video_path)
        if 'fps' in meta and 'duration' in meta:
            return int(meta['fps'] * meta['duration'])
        # Fallback: count frames (slower but accurate)
        count = 0
        for _ in iio.imiter(video_path):
            count += 1
        return count
    except Exception:
        return 0  # Unknown

# Removed lazy wrapper to simplify behavior and avoid StackView issues

class H5Playback:
    """Class for reading and playing back 3D datasets from an H5 file."""
    def __init__(self, file_path, file_type):

        self.h5_file = None
        self.image_dataset = None
        self.cancelled = False  # True if user cancelled conversion

        if file_type == "vid":  
            # Convert video to H5 and update path to the generated file
            file_path = convert_video_to_h5(file_path)
            if file_path is None:
                # Conversion was cancelled
                self.cancelled = True
                return
        elif file_type != "h5":
            qt.QMessageBox.critical(None, "Error", "Unsupported file type.")
            return

        self.h5_file = h5py.File(file_path, "r")

        # Try to find a 3D dataset (image stack, video)
        chosen_name = None
        for name in self.h5_file.keys():
            d = self.h5_file[name]
            if isinstance(d, h5py.Dataset) and (d.ndim == 3 or d.ndim == 4):
                if d.ndim == 3:
                    self.image_dataset = d
                    chosen_name = name
                    break
                else:
                    # 4D dataset found: stream-convert to 3D grayscale in cache and reopen
                    try:
                        new_path = convert_h5_4d_to_3d(file_path, name)
                        try:
                            self.h5_file.close()
                        except Exception:
                            pass
                        self.h5_file = h5py.File(new_path, "r")
                        self.image_dataset = self.h5_file['video_frames']
                        chosen_name = 'video_frames'
                        break
                    except Exception as e:
                        qt.QMessageBox.critical(None, "Error", f"Failed to convert 4D dataset to 3D: {e}")
                        return

        if self.image_dataset is None:
            qt.QMessageBox.critical(None, "Error", "No 3D dataset found in file.")
            return

        self.frame_index = 0
        self.dataset_size = self.image_dataset.shape[0]
        self.on_resize = None  # for compatibility

    def capture_frame(self):
        frame = self.image_dataset[self.frame_index]
        return frame
    
    def close(self):
        """Close the H5 file if open."""
        if self.h5_file is not None:
            self.h5_file.close()
            self.h5_file = None

"""Open a file dialog to select a file and return the path."""
def open_file_path(type: str):
    dialog = qt.QFileDialog()
    dialog.setFileMode(qt.QFileDialog.ExistingFile)
    dialog.setViewMode(qt.QFileDialog.Detail)
    if type == "h5": 
        dialog.setNameFilter("H5 3D Datasets (*.h5)")
    elif type == "vid":
        dialog.setNameFilter("Video Files (*.mp4 *.avi *.mov)")

    if dialog.exec():
        selected_files = dialog.selectedFiles()
        if selected_files:
            return selected_files[0]
        
    return None

"""Convert any video file to H5 format and return the H5 file path."""
def convert_video_to_h5(video_path, parent=None):
    cache_dir = get_cache_dir()
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    h5_path = os.path.join(cache_dir, base_name + '.h5')
    
    # Validate existing H5; if corrupted, delete and reconvert
    if os.path.exists(h5_path):
        try:
            with h5py.File(h5_path, 'r') as f:
                # Quick validation: check if we can read it
                if len(f.keys()) > 0:
                    return h5_path
        except (OSError, Exception):
            # Corrupted file; remove it and reconvert
            os.remove(h5_path)

    # Get frame count for progress bar
    total_frames = get_video_frame_count(video_path)
    
    # Show progress dialog
    dialog = ConversionProgressDialog(parent)
    dialog.start_conversion(video_path, h5_path, total_frames)
    
    result = dialog.exec()
    
    # Wait for worker to fully terminate before any cleanup
    dialog.wait_for_worker()
    
    if result == qt.QDialog.Accepted and dialog.result_path:
        return dialog.result_path
    else:
        # Conversion cancelled or failed - clean up partial file
        if os.path.exists(h5_path):
            try:
                os.remove(h5_path)
            except Exception as e:
                print(f"Warning: Could not remove partial H5 file: {e}")
        return None

def convert_h5_4d_to_3d(input_h5_path, dataset_name):
    """Stream-convert a 4D HDF5 dataset to a 3D grayscale dataset on disk.

    Detect channel axis (1 or 3). If channels in [3,4], compute luminance grayscale per frame.
    If channels==1, extract that channel. Writes to cacheimg/<basename>_mono.h5.
    """
    cache_dir = get_cache_dir()
    base_name = os.path.splitext(os.path.basename(input_h5_path))[0]
    out_path = os.path.join(cache_dir, base_name + '_mono.h5')

    # If already converted and valid, reuse
    if os.path.exists(out_path):
        try:
            with h5py.File(out_path, 'r') as fh:
                if 'video_frames' in fh and fh['video_frames'].ndim == 3:
                    return out_path
        except Exception:
            pass
        try:
            os.remove(out_path)
        except Exception:
            pass

    with h5py.File(input_h5_path, 'r') as src:
        d = src[dataset_name]
        if d.ndim != 4:
            raise ValueError('convert_h5_4d_to_3d expects a 4D dataset')

        # Determine channel axis and size
        if d.shape[1] in [1, 3, 4] and d.shape[1] < min(d.shape[2], d.shape[3]):
            ch_axis = 1
            ch_size = d.shape[1]
            H, W = d.shape[2], d.shape[3]
        else:
            ch_axis = 3
            ch_size = d.shape[3]
            H, W = d.shape[1], d.shape[2]

        N = d.shape[0]
        dtype = d.dtype

        with h5py.File(out_path, 'w') as dst:
            out = dst.create_dataset(
                'video_frames',
                shape=(0, H, W),
                maxshape=(None, H, W),
                chunks=(1, H, W),
                dtype=dtype,
                compression='gzip'
            )

            for i in range(N):
                if ch_axis == 1:
                    frame = d[i, :, :, :]  # (C,H,W)
                    if ch_size in [3, 4]:
                        rgb = frame[:3].transpose(1, 2, 0)
                        gray = np.dot(rgb, [0.299, 0.587, 0.114]).astype(dtype)
                    else:
                        gray = frame[0]
                else:
                    frame = d[i, :, :, :]  # (H,W,C)
                    if ch_size in [3, 4]:
                        gray = np.dot(frame[..., :3], [0.299, 0.587, 0.114]).astype(dtype)
                    else:
                        gray = frame[..., 0]

                out.resize((i + 1, H, W))
                out[i] = gray

    return out_path