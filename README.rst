.. image:: https://zenodo.org/badge/23917/pv/fimport.svg
   :target: https://zenodo.org/badge/latestdoi/23917/pv/fimport

=======
fimport
=======

Python import hook for importing Fortran modules.

Usage::

    import fimport
    fimport.install(reload_support=True)

    import somefortrancode # <- builds and imports somefortrancode.f90

But why in the world would you want that? One reason is
interactive use, where being able to reload modules is often
very convenient.

This code is based on Cython's pyximport module.

.. note::

   Reloading modules doesn't work currently on Python 3. You'll
   have to do instead

       some_module = imp.reload(some_module)

Build customization
-------------------

A custom numpy.distutils.core.Extension instance and setup()
args (Distribution) for for the build can be defined by a
``<modulename>.fbld`` file, such as::

    import os
    from numpy.distutils.core import Extension

    def make_ext(modname, ffilename):
        cwd = os.path.dirname(__file__)
        return Extension(name=modname,
                         sources=[ffilename, 'other_file.f90'],
                         f2py_options=['only:', 'some_subroutine', ':'],
                         libraries=['lapack', 'blas'],
                         library_dirs=[cwd],
                         include_dirs=['/myinclude', cwd])

    def make_setup_args():
        return dict(script_args=["--fcompiler=gnu"])

Extra dependencies can be listed in a <modulename>.fdep::

    other_file.f90
    some_include.inc
    examplemodule.fbld

