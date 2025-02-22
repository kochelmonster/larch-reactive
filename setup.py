# !!! sdist does not add the needed c-headers
# don't blame me this is a bug of setuptools:
# https://github.com/pypa/setuptools/issues/1162
import os
from setuptools import setup, find_namespace_packages
from distutils.extension import Extension

debug = os.environ.get("LARCH_INSTALL_FOR_TEST")

try:
    from Cython.Distutils import build_ext

    try:
        # regenerate cython output file each time (see PY_VERSION_HEX)
        os.remove(os.path.join('larch', 'reactive', 'ccore.cpp'))
    except OSError:
        pass

    cdir = os.path.join('larch', 'reactive')
    path = os.path.join(cdir, 'ccore.pyx')
    ccore_extension = Extension('larch.reactive.ccore', [path])
    ccore_extension.language = "c++"
    ccore_extension.depends = [os.path.join(cdir, 'pyref.h'),
                               os.path.join(cdir, 'greenlet.h')]
    ccore_extension.cython_directives = {
        "boundscheck": False, "always_allow_keywords": False,
        "wraparound": False, "language_level": 3}

    if debug:
        ccore_extension.cython_directives.update({
            "linetrace": True, "profile": True})
        ccore_extension.define_macros.extend([
            ("CYTHON_TRACE_NOGIL", 1),
            ("CYTHON_TRACE", 1),
            ("DEBUG", None)])
        ccore_extension.extra_compile_args.extend(["-g"])

    # some setup tool bug changes ccore.pyx to ccore.c
    # update it again
    ccore_extension.sources = [path]
    ext_args = dict(
        cmdclass={'build_ext': build_ext}, ext_modules=[ccore_extension])

except ImportError:
    from distutils.command import build_ext
    path = os.path.join('larch', 'reactive', 'ccore.cpp')
    ccore_extension = Extension('larch.reactive.ccore', [path])
    ccore_extension.sources = [path]
    ext_args = dict(ext_modules=[ccore_extension])


setup(
    name='larch-reactive',
    version="4.0.12",
    packages=find_namespace_packages(where="./", include=["larch.reactive"]),
    zip_safe=False,
    extras_require={
        'documentation': ['sphinxcontrib-napoleon', 'sphinxcontrib-plantuml'],
        "build": ["cython"]
    },

    # metadata for upload to PyPI
    author='Michael Reithinger',
    description='reactive programming for python',
    license='BSD',
    keywords='library',
    url='https://github.com/kochelmonster/larch-reactive', 

    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules"],

    **ext_args
)
