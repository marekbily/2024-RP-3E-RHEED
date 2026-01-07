"""
ROI Computation Engine
Background thread for non-blocking ROI statistics computation.
Uses thread pool for parallel ROI computation.
"""
import numpy as np
from silx.gui import qt
import queue
import time
from gui.roi_mask_utils import ROIMaskUtils


class ROIComputationWorker(qt.QRunnable):
    """Worker for computing a single ROI on a frame in thread pool."""
    
    class Signals(qt.QObject):
        """Signals for the worker (QRunnable can't have signals directly)."""
        finished = qt.Signal(str, int, float)  # roi_name, frame_index, mean_value
        error = qt.Signal(str, str)  # roi_name, error_message
    
    def __init__(self, roi_name, roi, frame_index, frame_data, cache):
        """
        Initialize worker for single ROI computation.
        
        Args:
            roi_name: String identifier for the ROI
            roi: ROI object
            frame_index: Frame number
            frame_data: 2D numpy array
            cache: ROIDataCache instance
        """
        super().__init__()
        self.roi_name = roi_name
        self.roi = roi
        self.frame_index = frame_index
        self.frame_data = frame_data
        self.cache = cache
        self.signals = ROIComputationWorker.Signals()
        self.setAutoDelete(True)
    
    def run(self):
        """Execute the computation."""
        try:
            mean_value = ROIMaskUtils.compute_mean_for_roi(self.roi, self.frame_data)
            
            # Store in cache
            self.cache.set_mean(self.roi_name, self.frame_index, mean_value)
            
            # Emit success signal
            self.signals.finished.emit(self.roi_name, self.frame_index, mean_value)
            
        except Exception as e:
            error_msg = f"Error computing frame {self.frame_index} for {self.roi_name}: {e}"
            print(error_msg)
            self.signals.error.emit(self.roi_name, error_msg)


class ROIComputationEngine(qt.QThread):
    """Background worker thread for ROI statistics computation."""
    
    # Signals for communication with GUI
    currentFrameReady = qt.Signal(str, float)  # roi_name, mean_value
    bulkProgressUpdated = qt.Signal(str, int, int)  # roi_name, frames_done, total_frames
    bulkAnalysisComplete = qt.Signal(str)  # roi_name
    errorOccurred = qt.Signal(str, str)  # roi_name, error_message
    
    def __init__(self, data_cache):
        """
        Initialize the computation engine.
        
        Args:
            data_cache: ROIDataCache instance for storing results
        """
        super().__init__()
        self.cache = data_cache
        self.task_queue = queue.Queue()
        self._running = True
        self._paused = False
        
        # Thread pool for parallel ROI computation
        # Use CPU count for optimal parallelism (default behavior)
        self.thread_pool = qt.QThreadPool.globalInstance()
        # Can adjust max thread count if needed
        # self.thread_pool.setMaxThreadCount(4)  # or os.cpu_count()
        
        # Dataset reference
        self.dataset = None
        self.dataset_shape = None
        
        # Priority tasks (current frame updates)
        self.priority_queue = queue.Queue()
        
        # Chunk size for bulk processing (frames per iteration)
        self.chunk_size = 100
        
        # Track pending workers for current frame
        self._pending_workers = 0
        self._pending_lock = qt.QMutex()
    
    def set_dataset(self, dataset):
        """
        Set the dataset for computation.
        
        Args:
            dataset: Numpy array or h5py dataset with shape (N, H, W)
        """
        self.dataset = dataset
        if dataset is not None and len(dataset.shape) >= 2:
            self.dataset_shape = dataset.shape
        else:
            self.dataset_shape = None
    
    def queue_bulk_analysis(self, roi_name, roi, total_frames):
        """
        Queue a bulk analysis task for all frames.
        
        Args:
            roi_name: String identifier for the ROI
            roi: ROI object
            total_frames: Total number of frames to compute
        """
        self.task_queue.put(('bulk', roi_name, roi, total_frames))
    
    def queue_current_frame(self, frame_index, frame_data, roi_list):
        """
        Queue a high-priority current frame update.
        
        Args:
            frame_index: Current frame number
            frame_data: 2D numpy array of current frame
            roi_list: List of (roi_name, roi) tuples to compute
        """
        self.priority_queue.put(('current', frame_index, frame_data, roi_list))
    
    def pause(self):
        """Pause bulk computation (priority tasks still process)."""
        self._paused = True
    
    def resume(self):
        """Resume bulk computation."""
        self._paused = False
    
    def stop(self):
        """Stop the computation engine thread."""
        self._running = False
        
        # Wait for thread pool to finish current tasks
        self.thread_pool.waitForDone(1000)  # 1 second timeout
        
        # Clear queues
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
            except queue.Empty:
                break
        while not self.priority_queue.empty():
            try:
                self.priority_queue.get_nowait()
            except queue.Empty:
                break
        self.quit()
        self.wait()
    
    def run(self):
        """Main thread loop - processes tasks from queue."""
        while self._running:
            # Check priority queue first (current frame updates)
            try:
                task = self.priority_queue.get(timeout=0.01)
                self._process_priority_task(task)
                continue
            except queue.Empty:
                pass
            
            # Process bulk tasks if not paused
            if not self._paused:
                try:
                    task = self.task_queue.get(timeout=0.1)
                    self._process_bulk_task(task)
                except queue.Empty:
                    # No tasks, sleep briefly
                    time.sleep(0.05)
            else:
                # Paused, just sleep
                time.sleep(0.1)
    
    def _process_priority_task(self, task):
        """Process a high-priority current frame update - uses thread pool for parallel computation."""
        task_type, frame_index, frame_data, roi_list = task
        
        if task_type != 'current':
            return
        
        # Compute all ROIs in parallel using thread pool
        self._pending_lock.lock()
        self._pending_workers = len(roi_list)
        self._pending_lock.unlock()
        
        for roi_name, roi in roi_list:
            # Create worker for this ROI
            worker = ROIComputationWorker(roi_name, roi, frame_index, frame_data, self.cache)
            
            # Connect signals
            worker.signals.finished.connect(self._on_worker_finished)
            worker.signals.error.connect(self._on_worker_error)
            
            # Submit to thread pool for parallel execution
            self.thread_pool.start(worker)
    
    def _on_worker_finished(self, roi_name, frame_index, mean_value):
        """Handle worker completion - called from worker thread."""
        # Emit signal for GUI update (thread-safe Qt signal)
        self.currentFrameReady.emit(roi_name, mean_value)
        
        # Decrement pending counter
        self._pending_lock.lock()
        self._pending_workers -= 1
        self._pending_lock.unlock()
    
    def _on_worker_error(self, roi_name, error_msg):
        """Handle worker error - called from worker thread."""
        self.errorOccurred.emit(roi_name, error_msg)
        
        # Decrement pending counter
        self._pending_lock.lock()
        self._pending_workers -= 1
        self._pending_lock.unlock()
    
    def _process_bulk_task(self, task):
        """Process a bulk analysis task in chunks - uses thread pool for parallel frame processing."""
        task_type, roi_name, roi, total_frames = task
        
        if task_type != 'bulk':
            return
        
        if self.dataset is None:
            self.errorOccurred.emit(roi_name, "No dataset available for bulk computation")
            return
        
        try:
            # Get frames that need computation
            frames_to_compute = []
            for frame_idx in range(total_frames):
                if self.cache.get_mean(roi_name, frame_idx) is None:
                    frames_to_compute.append(frame_idx)
            
            if len(frames_to_compute) == 0:
                # Already fully computed
                self.bulkAnalysisComplete.emit(roi_name)
                return
            
            # Process in chunks - submit chunk to thread pool for parallel processing
            for i in range(0, len(frames_to_compute), self.chunk_size):
                if not self._running:
                    break
                
                # Check for priority tasks - they take precedence
                if not self.priority_queue.empty():
                    # Re-queue this bulk task and handle priority
                    self.task_queue.put(task)
                    return
                
                chunk = frames_to_compute[i:i + self.chunk_size]
                
                # Submit chunk frames to thread pool for parallel computation
                # Track workers for this chunk
                chunk_workers = []
                
                for frame_idx in chunk:
                    if not self._running:
                        break
                    
                    try:
                        # Get frame data
                        if self.dataset.ndim == 3:
                            frame_data = self.dataset[frame_idx]
                        elif self.dataset.ndim == 2:
                            frame_data = self.dataset
                        else:
                            continue
                        
                        # Create worker for this frame
                        worker = ROIComputationWorker(roi_name, roi, frame_idx, frame_data, self.cache)
                        # Don't connect signals for bulk processing (too many emissions)
                        # Results are stored in cache directly
                        chunk_workers.append(worker)
                        
                        # Submit to thread pool
                        self.thread_pool.start(worker)
                        
                    except Exception as e:
                        error_msg = f"Error at frame {frame_idx}: {e}"
                        print(error_msg)
                        # Continue with other frames
                
                # Wait for chunk to complete before emitting progress
                # Use active count to avoid blocking the main thread too long
                wait_count = 0
                while self.thread_pool.activeThreadCount() > 0 and wait_count < 100:
                    time.sleep(0.01)  # 10ms
                    wait_count += 1
                
                # Emit progress update
                computed, total = self.cache.get_progress(roi_name)
                self.bulkProgressUpdated.emit(roi_name, computed, total)
                
                # Small yield to prevent blocking
                time.sleep(0.001)
            
            # Analysis complete
            if self._running:
                self.bulkAnalysisComplete.emit(roi_name)
                
        except Exception as e:
            error_msg = f"Bulk computation error for {roi_name}: {e}"
            print(error_msg)
            self.errorOccurred.emit(roi_name, error_msg)
    
    def clear_queue(self):
        """Clear all pending bulk tasks (keep priority queue)."""
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
            except queue.Empty:
                break
    
    def get_queue_size(self):
        """Get number of pending bulk tasks."""
        return self.task_queue.qsize()
