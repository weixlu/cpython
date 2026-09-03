On the free-threaded build, an object is now deallocated as soon as its last
reference is dropped, even when the thread that owns its reference count is
blocked. Previously the deallocation was deferred until the owning thread
next executed bytecode, which could keep large amounts of memory alive
indefinitely.
