import os
import sys
import tempfile
import shutil
import time
import imp

from nose.tools import assert_equal, assert_true

def test_run():
    old_path = list(sys.path)
    tmpdir = tempfile.mkdtemp()
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

        import fimport
        fimport.install(reload_support=True,
                        build_dir=os.path.join(tmpdir, "_fbld"))

        sys.path.insert(0, tmpdir)

        test_f90 = os.path.join(tmpdir, 'fimport_test_123.f90')
        test_inc = os.path.join(tmpdir, 'fimport_test_123.inc')
        test_fbld = os.path.join(tmpdir, 'fimport_test_123.fbld')
        test_fdep = os.path.join(tmpdir, 'fimport_test_123.fdep')

        with open(test_f90, 'wb') as f:
            f.write(b"subroutine ham(a)\n"
                    b"double precision, intent(out) :: a\n"
                    b"include 'fimport_test_123.inc'\n"
                    b"end subroutine\n"
                    b"subroutine spam(a)\n"
                    b"double precision, intent(out) :: a\n"
                    b"a = 9.99d0\n"
                    b"end subroutine\n")

        with open(test_inc, 'wb') as f:
            f.write(b"a = 3.14d0\n")

        with open(test_fbld, 'wb') as f:
            f.write(b"from numpy.distutils.core import Extension\n"
                    b"def make_ext(modname, ffilename):\n"
                    b"    return Extension(name=modname, sources=[ffilename],\n"
                    b"                     f2py_options=['only:', 'ham', ':'])")

        with open(test_fdep, 'wb') as f:
            f.write(b"fimport_test_123.inc")

        # import!
        import fimport_test_123
        assert_equal(fimport_test_123.ham(), 3.14)
        assert_true('spam' not in dir(fimport_test_123))

        # sleep over timestamp granularity
        time.sleep(1.01)

        # rewrite and reload
        with open(test_inc, 'wb') as f:
            f.write(b"a = 1.23d0\n")

        newmod = imp.reload(fimport_test_123)
        assert_equal(newmod.ham(), 1.23)
        if sys.version_info[0] >= 3:
            raise AssertionError("Reloading doesn't work currently on Python 3")
        else:
            assert_equal(fimport_test_123.ham(), 1.23)
    finally:
        sys.path = old_path
        shutil.rmtree(tmpdir)

if __name__ == "__main__":
    import nose
    nose.main()
