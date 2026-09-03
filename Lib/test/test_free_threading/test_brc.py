import gc
import threading
import time
import unittest
from threading import Thread
from unittest import TestCase

from test.support import threading_helper


@threading_helper.requires_working_threading()
class TestBRC(TestCase):
    def test_merge_refcount_of_blocked_owner(self):
        destroyed = threading.Event()

        class Obj:
            def __del__(self):
                destroyed.set()

        box = []
        created = threading.Event()
        release = threading.Event()

        def producer():
            box.append(Obj())  # owned by this thread
            created.set()
            release.wait()     # block without running any bytecode

        thread = Thread(target=producer)
        thread.start()
        try:
            created.wait()
            # Give the producer time to actually park in release.wait().
            time.sleep(0.1)

            # Make sure GC won't help
            gc.disable()
            try:
                box.clear()  # last decref, from a non-owner thread
                self.assertTrue(destroyed.wait(5.0))
            finally:
                gc.enable()
        finally:
            release.set()
            thread.join()

    def test_stress(self):
        # Same shape as above, but with many threads handing objects
        # while repeatedly blocking and waking up
        NUM_THREADS = 8
        NUM_ITERS = 200

        # list.append() is atomic, so it's safe to share between threads
        created = []
        destroyed = []

        class Tracked:
            def __init__(self):
                created.append(None)

            def __del__(self):
                destroyed.append(None)

        boxes = [[] for _ in range(NUM_THREADS)]
        barrier = threading.Barrier(NUM_THREADS)

        def worker(index):
            box = boxes[index]
            other = boxes[(index + 1) % NUM_THREADS]
            barrier.wait()
            for _ in range(NUM_ITERS):
                # publish objects owned by this thread
                box.append(Tracked())
                box.append(Tracked())
                # drop objects owned by the previous thread
                del other[:]
                # block to switch thread state, so that the next thread's
                # decrefs have a chance to merge our refcounts.
                time.sleep(0)

        threads = [Thread(target=worker, args=(i,))
                   for i in range(NUM_THREADS)]
        with threading_helper.start_threads(threads):
            pass

        for box in boxes:
            del box[:]
        gc.collect()
        self.assertEqual(len(destroyed), len(created))


if __name__ == "__main__":
    unittest.main()
