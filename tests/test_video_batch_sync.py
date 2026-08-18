import unittest
from threading import Event
from unittest.mock import MagicMock, patch

import core.video_batch_sync as batch_sync
from core.opencli_videos import OpenCliCancelledError, fetch_user_videos
from core.utils.system.process import ProcessCancelledError, _run_managed


class BatchSyncCancellationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_state = batch_sync.batch_sync_progress()
        self.original_cancelled = batch_sync._cancel_event.is_set()
        batch_sync._cancel_event.clear()

    def tearDown(self) -> None:
        with batch_sync._state_lock:
            batch_sync._state.clear()
            batch_sync._state.update(self.original_state)
        if self.original_cancelled:
            batch_sync._cancel_event.set()
        else:
            batch_sync._cancel_event.clear()

    def test_cancel_request_marks_running_task_as_stopping(self) -> None:
        with batch_sync._state_lock:
            batch_sync._state.update(running=True, cancel_requested=False, cancelled=False)

        result = batch_sync.request_batch_sync_cancel()

        self.assertEqual(result["status"], "stopping")
        self.assertTrue(batch_sync._cancel_event.is_set())
        self.assertTrue(batch_sync.batch_sync_progress()["cancel_requested"])

    @patch("core.video_batch_sync.refresh_up_videos_with_stats")
    def test_cancelled_current_up_stops_remaining_queue(self, refresh) -> None:
        def cancel_current(*_args, **kwargs):
            kwargs["cancel_event"].set()
            raise OpenCliCancelledError("视频同步已停止")

        refresh.side_effect = cancel_current
        with batch_sync._state_lock:
            batch_sync._state.update(
                running=True,
                total=2,
                done=0,
                results=[],
                cancel_requested=False,
                cancelled=False,
            )

        batch_sync._run_batch(
            [
                {"up_id": "1", "nickname": "UP 1", "page": 1},
                {"up_id": "2", "nickname": "UP 2", "page": 1},
            ],
            5,
            20,
            50,
            False,
        )

        progress = batch_sync.batch_sync_progress()
        self.assertFalse(progress["running"])
        self.assertTrue(progress["cancelled"])
        self.assertEqual(progress["done"], 0)
        self.assertEqual(progress["results"][0]["status"], "cancelled")
        self.assertEqual(refresh.call_count, 1)

    @patch("core.opencli_videos.run_opencli", side_effect=ProcessCancelledError("cancelled"))
    def test_video_query_translates_process_cancellation(self, run) -> None:
        cancel_event = Event()
        with self.assertRaises(OpenCliCancelledError):
            fetch_user_videos("123", cancel_event=cancel_event)
        self.assertIs(run.call_args.kwargs["cancel_event"], cancel_event)

    @patch("core.utils.system.process._terminate_process")
    @patch("core.utils.system.process.subprocess.Popen")
    def test_managed_process_honors_cancel_event(self, popen, terminate) -> None:
        process = MagicMock()
        process.communicate.return_value = ("", "")
        popen.return_value = process
        cancel_event = Event()
        cancel_event.set()

        with self.assertRaises(ProcessCancelledError):
            _run_managed(["opencli"], timeout=5, text=True, cancel_event=cancel_event)

        terminate.assert_called_once_with(process)


if __name__ == "__main__":
    unittest.main()
