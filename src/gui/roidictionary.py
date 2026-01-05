from silx.gui import qt
import numpy as np
import json
import h5py
from silx.io import dictdump
from silx.gui.plot.items.roi import (
    PointROI, CrossROI, LineROI, HorizontalLineROI, VerticalLineROI,
    RectangleROI, CircleROI, EllipseROI, PolygonROI, HorizontalRangeROI
)

# Mapping ROI class names to classes.
_ROI_CLASS_MAP = {
    "PointROI": PointROI,
    "CrossROI": CrossROI,
    "LineROI": LineROI,
    "HorizontalLineROI": HorizontalLineROI,
    "VerticalLineROI": VerticalLineROI,
    "RectangleROI": RectangleROI,
    "CircleROI": CircleROI,
    "EllipseROI": EllipseROI,
    "PolygonROI": PolygonROI,
    "HorizontalRangeROI": HorizontalRangeROI,
}


def roi_to_dict(roi):
    """Convert a 2D ROI into a dictionary with numpy arrays for HDF5 storage."""
    d = {
        "class": roi.__class__.__name__,
        "name": roi.getName() if hasattr(roi, "getName") else "",
    }
    # Use the type of ROI to decide what properties to save:
    if hasattr(roi, "_color"):
        d["color"] = roi.getColor().name()
    if isinstance(roi, (PointROI, CrossROI)):
        d["position"] = np.array(roi.getPosition())
    elif isinstance(roi, LineROI):
        start, end = roi.getEndPoints()
        d["start"] = np.array(start)
        d["end"] = np.array(end)
    elif isinstance(roi, (HorizontalLineROI, VerticalLineROI)):
        d["position"] = np.array([roi.getPosition()])
    elif isinstance(roi, RectangleROI):
        d["origin"] = np.array(roi.getOrigin())
        d["size"] = np.array(roi.getSize())
    elif isinstance(roi, CircleROI):
        d["center"] = np.array(roi.getCenter())
        d["radius"] = np.array([roi.getRadius()])
    elif isinstance(roi, EllipseROI):
        d["center"] = np.array(roi.getCenter())
        d["major_radius"] = np.array([roi.getMajorRadius()])
        d["minor_radius"] = np.array([roi.getMinorRadius()])
        d["orientation"] = np.array([roi.getOrientation()])
    elif isinstance(roi, PolygonROI):
        d["points"] = roi.getPoints()  # Already numpy array
    elif isinstance(roi, HorizontalRangeROI):
        d["range"] = np.array(roi.getRange())
    return d


def roi_from_dict(d, plot=None):
    """
    Create an ROI from its dictionary representation.
    
    :param d: Dictionary with ROI properties.
    :param plot: Unused (kept for backwards compatibility). ROIs are created without parent.
    :return: An ROI instance.
    """
    cls_name = d.get("class")
    cls = _ROI_CLASS_MAP.get(cls_name)
    if cls is None:
        raise ValueError("Unknown ROI class: %s" % cls_name)
    # Create ROI without parent - it will be added to the manager later
    roi = cls(parent=None)
    # Restore common property if available.
    if "name" in d and hasattr(roi, "setName"):
        roi.setName(d["name"])
    # Set ROI-specific geometry.
    if "color" in d and hasattr(roi, "_color"):
        roi.setColor(qt.QColor(d["color"]))
    if cls_name in ("PointROI", "CrossROI"):
        roi.setPosition(tuple(np.array(d["position"]).flatten()))
    elif cls_name == "LineROI":
        start = np.array(d["start"]).flatten()
        end = np.array(d["end"]).flatten()
        roi.setEndPoints(start, end)
    elif cls_name in ("HorizontalLineROI", "VerticalLineROI"):
        pos = d["position"]
        # Handle both scalar and array
        if isinstance(pos, np.ndarray):
            pos = float(pos.flatten()[0])
        roi.setPosition(pos)
    elif cls_name == "RectangleROI":
        origin = np.array(d["origin"]).flatten()
        size = np.array(d["size"]).flatten()
        roi.setGeometry(origin=origin, size=size)
    elif cls_name == "CircleROI":
        center = np.array(d["center"]).flatten()
        radius = d["radius"]
        if isinstance(radius, np.ndarray):
            radius = float(radius.flatten()[0])
        roi.setGeometry(center=center, radius=radius)
    elif cls_name == "EllipseROI":
        center = np.array(d["center"]).flatten()
        major = d["major_radius"]
        minor = d["minor_radius"]
        orient = d["orientation"]
        if isinstance(major, np.ndarray):
            major = float(major.flatten()[0])
        if isinstance(minor, np.ndarray):
            minor = float(minor.flatten()[0])
        if isinstance(orient, np.ndarray):
            orient = float(orient.flatten()[0])
        roi.setGeometry(center=center,
                        radius=(major, minor),
                        orientation=orient)
    elif cls_name == "PolygonROI":
        points = np.array(d["points"])
        roi.setPoints(points)
    elif cls_name == "HorizontalRangeROI":
        rng = np.array(d["range"]).flatten()
        roi.setRange(float(rng[0]), float(rng[1]))
    return roi


# Example functions to save and load ROIs to/from a JSON file.

def save_rois_to_file(rois, filename):
    """
    Save a list of ROI objects to a file.
    
    :param rois: List of ROI objects.
    :param filename: Path to the output file.
    """
    rois_data = [roi_to_dict(roi) for roi in rois]
    with open(filename, "w") as f:
        json.dump({"rois": rois_data}, f, indent=4)


def load_rois_from_file(filename, plot=None):
    """
    Load ROIs from a file.
    
    :param filename: Path to the file.
    :param plot: Parent plot widget to pass to each ROI.
    :return: List of ROI objects.
    """
    with open(filename, "r") as f:
        data = json.load(f)
    rois_data = data.get("rois", [])
    rois = [roi_from_dict(d, plot=plot) for d in rois_data]
    return rois


# HDF5 functions for embedding ROIs in datasets

ROI_GROUP_NAME = "roi_metadata"
ROI_DATASET_NAME = "roi_data"
EMBED_FLAG_NAME = "embed_enabled"


def save_rois_to_h5(rois, h5_file_path, embed_enabled=True):
    """
    Save ROIs to an HDF5 file using silx dictdump for proper HDF5 structure.
    
    Creates a hierarchy like:
      /roi_metadata/
        embed_enabled (attribute)
        roi_count (attribute)
        ROI_0/
          class = "RectangleROI"
          name = "ROI 1"
          color = "#00ff00"
          origin = [x, y]
          size = [w, h]
        ROI_1/
          ...
    
    :param rois: List of ROI objects.
    :param h5_file_path: Path to the HDF5 file.
    :param embed_enabled: Whether to save the embed checkbox state.
    :return: True if successful, False otherwise.
    """
    try:
        with h5py.File(h5_file_path, "r+") as f:
            # Remove existing ROI metadata if present
            if ROI_GROUP_NAME in f:
                del f[ROI_GROUP_NAME]
            
            # Create ROI metadata group
            roi_group = f.create_group(ROI_GROUP_NAME)
            roi_group.attrs[EMBED_FLAG_NAME] = embed_enabled
            roi_group.attrs["roi_count"] = len(rois)
            
            # Save each ROI as a subgroup
            for i, roi in enumerate(rois):
                roi_dict = roi_to_dict(roi)
                roi_subgroup = roi_group.create_group(f"ROI_{i}")
                
                # Store string values as attributes, arrays as datasets
                for key, value in roi_dict.items():
                    if isinstance(value, str):
                        roi_subgroup.attrs[key] = value
                    elif isinstance(value, np.ndarray):
                        roi_subgroup.create_dataset(key, data=value)
                    else:
                        # Scalar values
                        roi_subgroup.attrs[key] = value
            
        return True
    except Exception as e:
        print(f"Failed to save ROIs to HDF5: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_rois_from_h5(h5_file_path, plot=None):
    """
    Load ROIs from an HDF5 file.
    
    Reads the hierarchy created by save_rois_to_h5.
    
    :param h5_file_path: Path to the HDF5 file.
    :param plot: Unused (kept for backwards compatibility).
    :return: Tuple of (list of ROI objects, embed_enabled flag) or (None, False) if not found.
    """
    try:
        with h5py.File(h5_file_path, "r") as f:
            if ROI_GROUP_NAME not in f:
                print(f"No ROI group '{ROI_GROUP_NAME}' found in {h5_file_path}")
                return None, False
            
            roi_group = f[ROI_GROUP_NAME]
            
            # Get embed flag
            embed_enabled = roi_group.attrs.get(EMBED_FLAG_NAME, True)
            roi_count = roi_group.attrs.get("roi_count", 0)
            
            print(f"Found {roi_count} ROIs in {h5_file_path}")
            
            rois = []
            for i in range(roi_count):
                roi_name = f"ROI_{i}"
                if roi_name not in roi_group:
                    print(f"Warning: {roi_name} not found, skipping")
                    continue
                
                roi_subgroup = roi_group[roi_name]
                
                # Reconstruct dict from attributes and datasets
                roi_dict = {}
                
                # Read attributes (strings and scalars)
                for key, value in roi_subgroup.attrs.items():
                    roi_dict[key] = value
                
                # Read datasets (arrays)
                for key in roi_subgroup.keys():
                    roi_dict[key] = roi_subgroup[key][()]
                
                try:
                    roi = roi_from_dict(roi_dict, plot=plot)
                    rois.append(roi)
                    print(f"  Loaded {roi_dict.get('class', 'unknown')}: {roi_dict.get('name', '')}")
                except Exception as e:
                    import traceback
                    print(f"Failed to create ROI {i} ({roi_dict.get('class', 'unknown')}):")
                    traceback.print_exc()
            
            print(f"Successfully created {len(rois)} ROI objects")
            return rois, embed_enabled
    except Exception as e:
        import traceback
        print(f"Failed to load ROIs from HDF5: {e}")
        traceback.print_exc()
        return None, False


def h5_has_rois(h5_file_path):
    """
    Check if an HDF5 file contains saved ROIs.
    
    :param h5_file_path: Path to the HDF5 file.
    :return: True if ROIs are present, False otherwise.
    """
    try:
        with h5py.File(h5_file_path, "r") as f:
            if ROI_GROUP_NAME not in f:
                return False
            roi_group = f[ROI_GROUP_NAME]
            roi_count = roi_group.attrs.get("roi_count", 0)
            return roi_count > 0
    except Exception:
        return False


def h5_is_writable(h5_file_path):
    """
    Check if an HDF5 file can be opened for writing.
    
    :param h5_file_path: Path to the HDF5 file.
    :return: True if writable, False otherwise.
    """
    try:
        with h5py.File(h5_file_path, "r+") as f:
            pass
        return True
    except Exception:
        return False
