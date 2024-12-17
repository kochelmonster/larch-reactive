#include "Python.h"

struct PyRef {
  PyObject *ref;

  PyRef(): ref(NULL) { }

  PyRef(PyObject *ref_) {
    ref = ref_;
    Py_INCREF(ref);
  }

  PyRef(const PyRef& src) {
    ref = src.ref;
    Py_INCREF(ref);
  }

  ~PyRef() {
    Py_XDECREF(ref);
  }
};
