"""
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

"""

# pyximport authors:
#
# Paul Prescod 
# Alexey Borzenkov 
# Lisandro Dalcin 
# Mark Florisson 
# Robert Bradshaw 
# sbyrnes321 
# Stefan Behnel 
#
# fimport adaptation:
#
# Pauli Virtanen

import sys
import os
import glob
import imp

from StringIO import StringIO

from numpy.distutils.core import Extension, numpy_cmdclass, NumpyDistribution
from distutils.dist import Distribution
from distutils.errors import DistutilsArgError, DistutilsError, CCompilerError
from distutils.util import grok_environment_error

assert sys.hexversion >= 0x2030000, "need Python 2.3 or later"

__version__ = "0.1"

F_EXT = ".f"
F90_EXT = ".f90"
FDEP_EXT = ".fdep"
FBLD_EXT = ".fbld"

DEBUG = False

def _print(message, args):
    if args:
        message = message % args
    print(message)

def _debug(message, *args):
    if DEBUG:
        _print(message, args)

def _info(message, *args):
    _print(message, args)

_reloads = {}

def f_to_dll(filename, ext = None, force_rebuild = 0,
             fbuild_dir=None, setup_args={}, reload_support=False):
    """Compile a F file to a DLL and return the name of the generated .so
       or .dll ."""
    assert os.path.exists(filename), "Could not find %s" % os.path.abspath(filename)

    path, name = os.path.split(filename)

    if not ext:
        modname, extension = os.path.splitext(name)
        assert extension in (F_EXT, F90_EXT), extension
        ext = Extension(name=modname, sources=[filename])

    if not fbuild_dir:
        fbuild_dir = os.path.join(path, "_fbld")

    script_args=setup_args.get("script_args",[])
    if DEBUG or "--verbose" in script_args:
        quiet = "--verbose"
    else:
        quiet = "--quiet"
    args = [quiet, "build_ext"]
    if force_rebuild:
        args.append("--force")
    sargs = setup_args.copy()
    sargs.update(
        {"script_name": None,
         "script_args": args + script_args} )
    dist = NumpyDistribution(sargs)
    import distutils.core
    distutils.core._setup_distribution = dist
    if not dist.ext_modules:
        dist.ext_modules = []
    dist.ext_modules.append(ext)
    dist.cmdclass = numpy_cmdclass.copy()
    build = dist.get_command_obj('build')
    build.build_base = fbuild_dir

    config_files = dist.find_config_files()
    try: config_files.remove('setup.cfg')
    except ValueError: pass
    dist.parse_config_files(config_files)

    cfgfiles = dist.find_config_files()
    try: cfgfiles.remove('setup.cfg')
    except ValueError: pass
    dist.parse_config_files(cfgfiles)
    try:
        ok = dist.parse_command_line()
    except DistutilsArgError:
        raise

    if DEBUG:
        print("options (after parsing command line):")
        dist.dump_option_dicts()
    assert ok

    _old_stderr = sys.stderr
    _old_stdout = sys.stdout
    sys.stderr = StringIO()
    sys.stdout = StringIO()

    try:
        dist.run_commands()
        obj_build_ext = dist.get_command_obj("build_ext")
        so_path = obj_build_ext.get_outputs()[0]
        if obj_build_ext.inplace:
            # Python distutils get_outputs()[ returns a wrong so_path
            # when --inplace ; see http://bugs.python.org/issue5977
            # workaround:
            so_path = os.path.join(os.path.dirname(filename),
                                   os.path.basename(so_path))
        if reload_support:
            org_path = so_path
            timestamp = os.path.getmtime(org_path)
            global _reloads
            last_timestamp, last_path, count = _reloads.get(org_path, (None,None,0) )
            if last_timestamp == timestamp:
                so_path = last_path
            else:
                basename = os.path.basename(org_path)
                while count < 1000:
                    count += 1
                    r_path = os.path.join(obj_build_ext.build_lib,
                                          basename + '.reload%s'%count)
                    try:
                        import shutil # late import / reload_support is: debugging
                        shutil.copy2(org_path, r_path)
                        so_path = r_path
                    except IOError:
                        continue
                    break
                else:
                    # used up all 1000 slots
                    raise ImportError("reload count for %s reached maximum"%org_path)
                _reloads[org_path]=(timestamp, so_path, count)
        return so_path
    except KeyboardInterrupt:
        msg = sys.stdout.getvalue() + sys.stderr.getvalue()
        sys.stdout = _old_stdout
        sys.stderr = _old_stderr
        sys.stderr.write(msg)
        sys.exit(1)
    except (IOError, os.error):
        msg = sys.stdout.getvalue() + sys.stderr.getvalue()
        sys.stdout = _old_stdout
        sys.stderr = _old_stderr
        sys.stderr.write(msg)
        exc = sys.exc_info()[1]
        error = grok_environment_error(exc)

        if DEBUG:
            sys.stderr.write(error + "\n")
        raise
    finally:
        sys.stderr = _old_stderr
        sys.stdout = _old_stdout


def get_distutils_extension(modname, ffilename):
#    try:
#        import hashlib
#    except ImportError:
#        import md5 as hashlib
#    extra = "_" + hashlib.md5(open(ffilename).read()).hexdigest()
#    modname = modname + extra
    extension_mod,setup_args = handle_special_build(modname, ffilename)
    if not extension_mod:
        extension_mod = Extension(name = modname, sources=[ffilename])
    return extension_mod,setup_args

def handle_special_build(modname, ffilename):
    special_build = os.path.abspath(os.path.splitext(ffilename)[0] + FBLD_EXT)
    ext = None
    setup_args={}
    if os.path.exists(special_build):
        # globls = {}
        # locs = {}
        # execfile(special_build, globls, locs)
        # ext = locs["make_ext"](modname, ffilename)
        with open(special_build, 'rb') as f:
            mod = imp.load_source("XXXX", special_build, f)
        make_ext = getattr(mod,'make_ext',None)
        if make_ext:
            ext = make_ext(modname, ffilename)
            assert ext and ext.sources, ("make_ext in %s did not return Extension"
                                         % special_build)
        make_setup_args = getattr(mod,'make_setup_args',None)
        if make_setup_args:
            setup_args = make_setup_args()
            assert isinstance(setup_args,dict), ("make_setup_args in %s did not return a dict"
                                         % special_build)
        assert set or setup_args, ("neither make_ext nor make_setup_args %s"
                                         % special_build)
        ext.sources = [os.path.join(os.path.dirname(special_build), source)
                       for source in ext.sources]
    return ext, setup_args

def handle_dependencies(ffilename):
    testing = '_test_files' in globals()
    dependfile = os.path.splitext(ffilename)[0] + FDEP_EXT
    buildfile =  os.path.splitext(ffilename)[0] + FBLD_EXT

    # by default let distutils decide whether to rebuild on its own
    # (it has a better idea of what the output file will be)
    files = []

    # but we know more about dependencies so force a rebuild if
    # some of the dependencies are newer than the ffile.
    if os.path.exists(dependfile):
        with open(dependfile, 'rb') as f:
            depends = f.readlines()
        depends = [depend.strip() for depend in depends]

        # gather dependencies
        for depend in depends:
            fullpath = os.path.join(os.path.dirname(dependfile),
                                    depend)
            files.extend(glob.glob(fullpath))

        # the dependency file is also itself a dependency
        files.append(dependfile)

    # build file is an automatic dependency, if it exists
    if os.path.exists(buildfile):
        files.append(buildfile)

    # only for unit testing to see we did the right thing
    if testing:
        _test_files[:] = []  #$pycheck_no

    # if any file that the ffile depends upon is newer than
    # the f file, 'touch' the f file so that distutils will
    # be tricked into rebuilding it.
    for file in files:
        from distutils.dep_util import newer
        if newer(file, ffilename):
            _debug("Rebuilding %s because of %s", ffilename, file)
            filetime = os.path.getmtime(file)
            os.utime(ffilename, (filetime, filetime))
            if testing:
                _test_files.append(file)

def build_module(name, ffilename, fbuild_dir=None):
    assert os.path.exists(ffilename), (
        "Path does not exist: %s" % ffilename)
    handle_dependencies(ffilename)

    extension_mod,setup_args = get_distutils_extension(name, ffilename)
    sargs=fargs.setup_args.copy()
    sargs.update(setup_args)

    so_path = f_to_dll(ffilename, extension_mod,
                       fbuild_dir=fbuild_dir,
                       setup_args=sargs,
                       reload_support=fargs.reload_support)
    assert os.path.exists(so_path), "Cannot find: %s" % so_path

    junkpath = os.path.join(os.path.dirname(so_path), name+"_*") #very dangerous with --inplace ?
    junkstuff = glob.glob(junkpath)
    for path in junkstuff:
        if path!=so_path:
            try:
                os.remove(path)
            except IOError:
                _info("Couldn't remove %s", path)

    return so_path

def load_module(name, ffilename, fbuild_dir=None):
    try:
        module_name = name
        so_path = build_module(module_name, ffilename, fbuild_dir)
        mod = imp.load_dynamic(name, so_path)
        assert mod.__file__ == so_path, (mod.__file__, so_path)
    except Exception:
        import traceback
        raise ImportError("Building module %s failed: %s" %
                          (name,
                           traceback.format_exception_only(*sys.exc_info()[:2]))), None, sys.exc_info()[2]
    return mod


# import hooks

class FImporter(object):
    """A meta-path importer for .f files.
    """
    def __init__(self, extensions=(F_EXT, F90_EXT), fbuild_dir=None):
        self.extensions = extensions
        self.fbuild_dir = fbuild_dir

    def find_module(self, fullname, package_path=None):
        if fullname in sys.modules  and  not fargs.reload_support:
            return None  # only here when reload()
        try:
            fp, pathname, (ext,mode,ty) = imp.find_module(fullname,package_path)
            if fp: fp.close()  # Python should offer a Default-Loader to avoid this double find/open!
            for extension in self.extensions:
                if pathname and pathname.endswith(extension):
                    return FLoader(fullname, pathname,
                                   fbuild_dir=self.fbuild_dir)
                if ty != imp.C_EXTENSION: # only when an extension, check if we have a .f next!
                    return None

                # find .f fast, when .so/.pyd exist --inplace
                fpath = os.path.splitext(pathname)[0]+extension
                if os.path.isfile(fpath):
                    return FLoader(fullname, fpath,
                                     fbuild_dir=self.fbuild_dir)

                # .so/.pyd's on PATH should not be remote from .f's
                # think no need to implement FArgs.importer_search_remote here?

        except ImportError:
            pass

        # searching sys.path ...

        #if DEBUG:  print "SEARCHING", fullname, package_path
        if '.' in fullname: # only when package_path anyway?
            mod_parts = fullname.split('.')
            module_name = mod_parts[-1]
        else:
            module_name = fullname

        for extension in self.extensions:
            f_module_name = module_name + extension
            # this may work, but it returns the file content, not its path
            #import pkgutil
            #f_source = pkgutil.get_data(package, f_module_name)

            if package_path:
                paths = package_path
            else:
                paths = sys.path
            join_path = os.path.join
            is_file = os.path.isfile
            #is_dir = os.path.isdir
            sep = os.path.sep
            for path in paths:
                if not path:
                    path = os.getcwd()
                if is_file(path+sep+f_module_name):
                    return FLoader(fullname, join_path(path, f_module_name),
                                     fbuild_dir=self.fbuild_dir)

        # not found, normal package, not a .f file, none of our business
        _debug("%s not found" % fullname)
        return None

class FLoader(object):
    def __init__(self, fullname, path, fbuild_dir=None):
        _debug("FLoader created for loading %s from %s", fullname, path)
        self.fullname = fullname
        self.path = path
        self.fbuild_dir = fbuild_dir

    def load_module(self, fullname):
        assert self.fullname == fullname, (
            "invalid module, expected %s, got %s" % (
            self.fullname, fullname))
        #print "MODULE", fullname
        module = load_module(fullname, self.path,
                             self.fbuild_dir)
        return module


#install args
class FArgs(object):
    build_dir=True
    reload_support=False
    setup_args={}

##fargs=None

def install(fimport=True, build_dir=None,
            setup_args={}, reload_support=False):
    """Main entry point. Call this to install the .f import hook in
    your meta-path for a single Python process.  If you want it to be
    installed whenever you use Python, add it to your sitecustomize
    (as described above).

    By default, compiled modules will end up in a ``.fbld``
    directory in the user's home directory.  Passing a different path
    as ``build_dir`` will override this.

    ``setup_args``: dict of arguments for Distribution - see
    distutils.core.setup() . They are extended/overriden by those of
    <modulename>.fbld/make_setup_args()

    ``reload_support``:  Enables support for dynamic
    reload(<fmodulename>), e.g. after a change in the Cython code.
    Additional files <so_path>.reloadNN may arise on that account, when
    the previously loaded module file cannot be overwritten.
    """
    if not build_dir:
        build_dir = os.path.expanduser('~/.fbld')

    global fargs
    fargs = FArgs()  #$pycheck_no
    fargs.build_dir = build_dir
    fargs.setup_args = (setup_args or {}).copy()
    fargs.reload_support = reload_support

    has_f_importer = False
    for importer in sys.meta_path:
        if isinstance(importer, FImporter):
            has_f_importer = True

    if fimport and not has_f_importer:
        importer = FImporter(fbuild_dir=build_dir)
        sys.meta_path.append(importer)


# MAIN

def show_docs():
    print __doc__

if __name__ == '__main__':
    show_docs()
