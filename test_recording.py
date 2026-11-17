"""No microphone/speaker hardware is used in these recording regression tests."""
import heapq
import threading
import time
import unittest

import numpy as np

from recording import RecordingController, suggested_trim_end


class Scheduler:
    def __init__(self):
        self.now = 0
        self.tasks = []
        self.counter = 0
        self.cancelled = set()

    def after(self, ms, callback):
        self.counter += 1
        heapq.heappush(self.tasks, (self.now + ms, self.counter, callback))
        return self.counter

    def after_cancel(self, token):
        self.cancelled.add(token)

    def advance(self, ms):
        end = self.now + ms
        while self.tasks and self.tasks[0][0] <= end:
            when, token, callback = heapq.heappop(self.tasks)
            self.now = when
            if token not in self.cancelled:
                callback()
        self.now = end


class FakeStream:
    def __init__(self, factory, **options):
        self.factory = factory
        self.options = options
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self):
        if self.factory.block_open:
            self.factory.opening.set()
            self.factory.block_open.wait(1)
        if self.factory.fail_start:
            raise RuntimeError('microphone unavailable')
        self.started = True

    def stop(self):
        self.stopped = True
        if self.factory.fail_stop:
            raise RuntimeError('stop failed')

    def close(self):
        self.closed = True

    def audio(self, samples, status=''):
        data = np.asarray(samples, dtype=np.float32).reshape(-1, 1)
        self.options['callback'](data, len(data), None, status)


class Factory:
    def __init__(self):
        self.streams = []
        self.fail_start = False
        self.fail_stop = False
        self.block_open = None
        self.opening = threading.Event()

    def __call__(self, **options):
        stream = FakeStream(self, **options)
        self.streams.append(stream)
        return stream


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = Scheduler()
        self.factory = Factory()
        self.beeps = []
        self.states = []
        self.takes = []
        self.errors = []
        self.warnings = []
        self.levels = []
        self.controller = RecordingController(
            self.scheduler, self.factory,
            beep=lambda: self.beeps.append(self.scheduler.now),
            on_state=lambda code, value: self.states.append((code, value)),
            on_take=lambda *args: self.takes.append(args),
            on_error=self.errors.append, on_warning=self.warnings.append,
            on_level=lambda peak, seconds: self.levels.append((peak, seconds)))

    def tearDown(self):
        self.controller.close()

    def wait_for(self, predicate):
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            self.controller.poll()
            if predicate():
                return
            time.sleep(.001)
        self.fail('worker did not complete in time')

    def test_three_beeps_before_microphone_and_cancel(self):
        self.assertTrue(self.controller.start(2, 1000, context='holy:start'))
        self.assertEqual(self.beeps, [0])
        self.assertFalse(self.controller.start(2, 1000))
        self.scheduler.advance(2999)
        self.assertEqual(self.beeps, [0, 1000, 2000])
        self.assertEqual(self.factory.streams, [])
        self.assertTrue(self.controller.stop())
        self.scheduler.advance(5000)
        self.assertEqual(self.factory.streams, [])
        self.assertEqual(self.takes, [])
        self.assertEqual(self.controller.state, 'idle')

    def test_full_take_preserved_and_click_tail_excluded_by_marker(self):
        self.controller.start(2, 1000, context='fireball:start', trim_tail_ms=150)
        self.scheduler.advance(3000)
        self.wait_for(lambda: self.controller.state == 'recording')
        stream = self.factory.streams[0]
        source = np.zeros(1000, dtype=np.float32)
        source[400:600] = .3
        source[950:] = 1.  # Mechanical click immediately before Stop.
        stream.audio(source, 'input overflow')
        self.controller.poll()
        self.controller.stop()
        self.wait_for(lambda: len(self.takes) == 1)
        data, rate, context, end = self.takes[0]
        self.assertEqual(context, 'fireball:start')
        self.assertEqual(rate, 1000)
        np.testing.assert_array_equal(data, source)
        self.assertAlmostEqual(end, .85)
        self.assertEqual(float(np.max(data[:round(end*rate)])), float(np.float32(.3)))
        self.assertTrue(stream.stopped and stream.closed)
        self.assertIn('input overflow', self.warnings)
        self.assertEqual(self.errors, [])

    def test_limit_stop_keeps_tail_because_no_mouse_click(self):
        self.controller.max_seconds = 1
        self.controller.start(2, 1000, countdown=False, trim_tail_ms=150)
        self.wait_for(lambda: self.controller.state == 'recording')
        self.factory.streams[0].audio(np.ones(1000) * .2)
        self.wait_for(lambda: len(self.takes) == 1)
        self.assertEqual(self.takes[0][3], 1.)

    def test_start_error_closes_partial_stream(self):
        self.factory.fail_start = True
        self.controller.start(2, 1000, countdown=False)
        self.wait_for(lambda: bool(self.errors))
        self.assertEqual(self.controller.state, 'idle')
        self.assertTrue(self.factory.streams[0].closed)
        self.assertEqual(self.takes, [])

    def test_stop_error_still_closes_and_retains_recording(self):
        self.controller.start(2, 1000, countdown=False)
        self.wait_for(lambda: self.controller.state == 'recording')
        self.factory.streams[0].audio(np.zeros(500))
        self.factory.fail_stop = True
        self.controller.stop()
        self.wait_for(lambda: bool(self.takes))
        self.assertTrue(self.factory.streams[0].closed)
        self.assertEqual(len(self.errors), 1)

    def test_cancel_during_async_open_cannot_leak_stream(self):
        self.factory.block_open = threading.Event()
        self.controller.start(2, 1000, countdown=False)
        self.assertTrue(self.factory.opening.wait(1))
        self.controller.stop()
        self.factory.block_open.set()
        self.wait_for(lambda: self.factory.streams[0].closed)
        self.assertEqual(self.controller.state, 'idle')
        self.assertEqual(self.takes, [])

    def test_close_pending_open_cannot_call_ui_or_deliver_take(self):
        self.factory.block_open = threading.Event()
        self.controller.start(2, 1000, countdown=False)
        self.assertTrue(self.factory.opening.wait(1))
        self.controller.close()
        states = list(self.states)
        levels = list(self.levels)
        self.factory.block_open.set()
        self.wait_for(lambda: self.factory.streams[0].closed)
        self.assertEqual(self.states, states)
        self.assertEqual(self.levels, levels)
        self.assertEqual(self.takes, [])

    def test_short_takes_and_guard_validation(self):
        self.assertEqual(suggested_trim_end(100, 1000, 150), .1)
        self.assertEqual(suggested_trim_end(300, 1000, 0), .3)
        with self.assertRaises(ValueError):suggested_trim_end(10, 0)
        with self.assertRaises(ValueError):suggested_trim_end(100, 1000, float('nan'))
        self.controller.start(2, 1000, countdown=False)
        self.wait_for(lambda: self.controller.state == 'recording')
        self.factory.streams[0].audio(np.zeros(20))
        self.controller.stop()
        self.wait_for(lambda: bool(self.errors))
        self.assertEqual(str(self.errors[0]), 'recording_too_short')
        self.assertEqual(self.takes, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
