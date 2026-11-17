"""Cancelable pre-roll and recording lifecycle, independent of UI language.

All on_* callbacks run in the caller's poll()/Tk thread. Audio hardware is opened
only after countdown completion. Call poll every ~60 ms while the app is alive.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Any

import numpy as np


def countdown_beep():
    """Short independent cue. Never open the microphone or block the Tk thread."""
    def play():
        try:
            import winsound
            winsound.Beep(880, 75)
        except (ImportError, RuntimeError):
            pass  # A visual countdown remains usable when the sound device fails.
    threading.Thread(target=play, daemon=True).start()


def suggested_trim_end(frames: int, rate: int, tail_ms: float = 150) -> float:
    """A reversible initial end marker, not destructive click removal.

    The source take remains complete. Very short takes are never reduced below
    30 ms; if there is insufficient room for the whole guard, keep the full take.
    """
    if rate <= 0 or frames < 0:
        raise ValueError('invalid_audio_length')
    if not np.isfinite(tail_ms) or not 0 <= tail_ms <= 1000:
        raise ValueError('invalid_tail_guard')
    duration = frames / rate
    guard = tail_ms / 1000
    return duration - guard if duration >= guard + .03 else duration


class RecordingController:
    """Safe recording engine with an injectable scheduler and audio stream.

    scheduler must expose after(ms, callback) and after_cancel(token).
    on_state(code, value): countdown value=3/2/1, otherwise value is reason/None.
    on_level(peak, elapsed): peak is 0..1, elapsed seconds.
    on_take(data, rate, context, suggested_end): full original float32 mono array.
    on_error(exc): hardware or too-short errors; stream is always closed first.
    on_warning(text): capture overflow/underflow notifications.
    """
    def __init__(self, scheduler, stream_factory=None, beep=countdown_beep,
                 on_state=None, on_level=None, on_take=None, on_error=None,
                 on_warning=None, max_seconds=120):
        if stream_factory is None:
            import sounddevice as sd
            stream_factory = sd.InputStream
        self.scheduler = scheduler
        self.stream_factory = stream_factory
        self.beep = beep
        self.on_state = on_state or (lambda code, value: None)
        self.on_level = on_level or (lambda peak, elapsed: None)
        self.on_take = on_take or (lambda data, rate, context, end: None)
        self.on_error = on_error or (lambda error: None)
        self.on_warning = on_warning or (lambda text: None)
        self.max_seconds = float(max_seconds)
        self.state = 'idle'
        self.rate = 44100
        self.context = None
        self.frames = 0
        self.chunks = []
        self._stream = None
        self._scheduled = None
        self._generation = 0
        self._audio = queue.Queue()
        self._results = queue.Queue()
        self._closed = False
        self._tail_ms = 150
        self._stop_reason = None

    @property
    def busy(self):
        return self.state != 'idle'

    def _set_state(self, state, value=None):
        self.state = state
        self.on_state(state, value)

    def start(self, device, rate, context=None, countdown=True, trim_tail_ms=150):
        """Return False if another start is in progress; never duplicate streams."""
        if self._closed or self.busy:
            return False
        if int(rate) <= 0:
            raise ValueError('invalid_sample_rate')
        suggested_trim_end(0, int(rate), trim_tail_ms)  # Validate before countdown.
        self._generation += 1
        generation = self._generation
        self.rate = int(rate)
        self.context = context
        self.device = device
        self._tail_ms = float(trim_tail_ms)
        self.chunks = []
        self.frames = 0
        self._stop_reason = None
        self._drain_stale_audio()
        if countdown:
            self._countdown(generation, 3)
        else:
            self._open(generation)
        return True

    def _countdown(self, generation, remaining):
        self._scheduled = None
        if generation != self._generation or self._closed:
            return
        if remaining == 0:
            self._open(generation)
            return
        self._set_state('countdown', remaining)
        self.beep()
        self._scheduled = self.scheduler.after(1000, lambda: self._countdown(generation, remaining - 1))

    @staticmethod
    def _release(stream):
        try:
            stream.stop()
        finally:
            stream.close()

    def _open(self, generation):
        self._set_state('starting')
        rate, device = self.rate, self.device
        def callback(indata, frames, timing, status):
            if generation == self._generation and not self._closed:
                self._audio.put((generation, indata[:, 0].copy(), str(status) if status else ''))
        def worker():
            stream = None
            try:
                stream = self.stream_factory(device=device, samplerate=rate, channels=1,
                                             dtype='float32', callback=callback, blocksize=1024)
                stream.start()
                if generation != self._generation or self._closed:
                    self._release(stream)
                    return
                self._results.put(('opened', generation, stream))
            except Exception as error:
                if stream is not None:
                    try:
                        self._release(stream)
                    except Exception:
                        pass
                self._results.put(('error', generation, error))
        threading.Thread(target=worker, daemon=True).start()

    def _drain_stale_audio(self):
        while True:
            try:
                self._audio.get_nowait()
            except queue.Empty:
                return

    def _drain_audio(self):
        peak = 0.
        while True:
            try:
                generation, chunk, warning = self._audio.get_nowait()
            except queue.Empty:
                break
            if generation != self._generation:
                continue
            if len(chunk):
                self.chunks.append(chunk)
                self.frames += len(chunk)
                peak = max(peak, float(np.max(np.abs(chunk))))
            if warning:
                self.on_warning(warning)
        self.on_level(min(1., peak), self.frames / self.rate)

    def poll(self):
        """Drain worker/audio messages. Must be called from the GUI thread."""
        if self._closed:
            # close may race a worker enqueuing an opened stream. Reuse its quiet
            # cleanup, never update Tk controls after the window was destroyed.
            self.close()
            return
        self._drain_audio()
        while True:
            try:
                action, generation, value = self._results.get_nowait()
            except queue.Empty:
                break
            if generation != self._generation or self._closed:
                if action == 'opened':
                    # A start was cancelled just as the worker enqueued its result.
                    threading.Thread(target=lambda s=value: self._release_quietly(s), daemon=True).start()
                continue
            if action == 'opened':
                self._stream = value
                self._set_state('recording')
            elif action == 'error':
                self._stream = None
                self._set_state('idle', 'error')
                self.on_level(0., 0.)
                self.on_error(value)
            elif action == 'stopped':
                self._drain_audio()
                self._stream = None
                data = np.concatenate(self.chunks) if self.chunks else np.empty(0, dtype=np.float32)
                self._set_state('idle', self._stop_reason)
                self.on_level(0., 0.)
                if value is not None:
                    self.on_error(value)
                if len(data) / self.rate >= .03:
                    tail = self._tail_ms if self._stop_reason == 'manual' else 0
                    end = suggested_trim_end(len(data), self.rate, tail)
                    self.on_take(data, self.rate, self.context, end)
                elif value is None:
                    self.on_error(ValueError('recording_too_short'))
        if self.state == 'recording' and self.frames / self.rate >= self.max_seconds:
            self.stop(reason='limit')

    @classmethod
    def _release_quietly(cls, stream):
        try:
            cls._release(stream)
        except Exception:
            pass

    def stop(self, reason='manual'):
        if self.state == 'idle' or self.state == 'stopping':
            return False
        if self._scheduled is not None:
            self.scheduler.after_cancel(self._scheduled)
            self._scheduled = None
        if self.state in ('countdown', 'starting'):
            self._generation += 1  # Any in-flight start worker closes its own stream.
            self._set_state('idle', 'cancelled')
            self.on_level(0., 0.)
            return True
        stream, generation = self._stream, self._generation
        self._stream = None
        self._stop_reason = reason
        self._set_state('stopping')
        def worker():
            error = None
            try:
                self._release(stream)
            except Exception as exc:
                error = exc
            self._results.put(('stopped', generation, error))
        threading.Thread(target=worker, daemon=True).start()
        return True

    def close(self):
        """Cancel shutdown work. Discard the take; never call on_take after close."""
        self._closed = True
        self._generation += 1
        if self._scheduled is not None:
            self.scheduler.after_cancel(self._scheduled)
            self._scheduled = None
        stream, self._stream = self._stream, None
        if stream is not None:
            threading.Thread(target=lambda: self._release_quietly(stream), daemon=True).start()
        self.state = 'idle'
        self._drain_stale_audio()
        # Clean a stream already queued by an opening worker at the close boundary.
        while True:
            try:
                action, _, value = self._results.get_nowait()
            except queue.Empty:
                break
            if action == 'opened':
                threading.Thread(target=lambda s=value: self._release_quietly(s), daemon=True).start()
