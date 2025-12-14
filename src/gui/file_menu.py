from silx.gui import qt
import imageio.v3 as iio
import imageio_ffmpeg
import h5py
import numpy as np

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
        for name in self.h5_file.keys():
            d = self.h5_file[name]
            if isinstance(d, h5py.Dataset) and (d.ndim == 3 or d.ndim == 4):
                self.image_dataset = d
                break

        if self.image_dataset is None:
            qt.QMessageBox.critical(None, "Error", "No 3D dataset found in file.")
            return

        self.frame_index = 0
        self.dataset_size = self.image_dataset.shape[0]
        self.on_resize = None  # for compatibility

    def capture_frame(self):
        frame = self.image_dataset[self.frame_index]
        return frame

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
    h5_path = video_path.rsplit('.', 1)[0] + '.h5'

    with h5py.File(h5_path, 'w') as h5_file:
        frame_iter = iio.imiter(video_path)

        try:
            first_frame = next(frame_iter)
        except StopIteration:
            raise ValueError("Video contains no frames")

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
            dataset.resize((count + 1,) + frame_shape)
            dataset[count] = frame
            count += 1

    return h5_path