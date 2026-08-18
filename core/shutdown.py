"""Coordinate graceful shutdown for background work owned by this process."""

from core.single_video_download import shutdown_single_downloads
from core.utils.system.process import terminate_managed_processes
from core.video_batch_sync import request_batch_sync_cancel
from core.video_batch_track_download import request_batch_track_cancel
from core.video_download import shutdown_downloads


def shutdown_background_work() -> None:
    request_batch_sync_cancel()
    request_batch_track_cancel()
    shutdown_downloads()
    shutdown_single_downloads()
    terminate_managed_processes()
