from silx.gui import qt
import imageio.v3 as iio
import imageio_ffmpeg
import h5py
import numpy as np
import os

def get_cache_dir():
    """Return path to cacheimg folder under current working directory and ensure it exists."""
    cache_dir = os.path.join(os.getcwd(), 'cacheimg')
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except Exception:
        pass
    return cache_dir

# Removed lazy wrapper to simplify behavior and avoid StackView issues

class H5Playback:
    """Class for reading and playing back 3D datasets from an H5 file."""
    def __init__(self, file_path, file_type):

        self.h5_file = None

        if file_type == "vid":  
            # Convert video to H5 and update path to the generated file
            file_path = convert_video_to_h5(file_path)
        elif file_type != "h5":
            qt.QMessageBox.critical(None, "Error", "Unsupported file type.")
            return

        self.h5_file = h5py.File(file_path, "r")

        # Try to find a 3D dataset (image stack, video)
        self.image_dataset = None
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
def convert_video_to_h5(video_path):
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

    with h5py.File(h5_path, 'w') as h5_file:
        frame_iter = iio.imiter(video_path)

        try:
            first_frame = next(frame_iter)
        except StopIteration:
            raise ValueError("Video contains no frames")

        # Convert to grayscale if color (reduces memory by 3-4x)
        if first_frame.ndim == 3 and first_frame.shape[2] in [3, 4]:
            # RGB/RGBA to grayscale: 0.299*R + 0.587*G + 0.114*B
            first_frame = np.dot(first_frame[..., :3], [0.299, 0.587, 0.114]).astype(first_frame.dtype)
        elif first_frame.ndim == 3 and first_frame.shape[0] in [3, 4]:
            # Channel-first format
            first_frame = np.dot(first_frame[:3].transpose(1, 2, 0), [0.299, 0.587, 0.114]).astype(first_frame.dtype)
        
        frame_shape = first_frame.shape
        dtype = first_frame.dtype

        dataset = h5_file.create_dataset(
            'video_frames',
            shape=(0,) + frame_shape,
            maxshape=(None,) + frame_shape,
            chunks=(1,) + frame_shape,
            dtype=dtype,
            compression='gzip'
        )

        # Write first frame
        dataset.resize((1,) + frame_shape)
        dataset[0] = first_frame

        # Append remaining frames one by one
        count = 1
        for frame in frame_iter:
            # Convert to grayscale if needed
            if frame.ndim == 3 and frame.shape[2] in [3, 4]:
                frame = np.dot(frame[..., :3], [0.299, 0.587, 0.114]).astype(dtype)
            elif frame.ndim == 3 and frame.shape[0] in [3, 4]:
                frame = np.dot(frame[:3].transpose(1, 2, 0), [0.299, 0.587, 0.114]).astype(dtype)
            
            dataset.resize((count + 1,) + frame_shape)
            dataset[count] = frame
            count += 1

    return h5_path

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