from setuptools import setup

import fimport

with open('README.rst') as f:
    long_desc = f.read()

setup(
    name="fimport",
    version=fimport.__version__,
    url="https://github.com/pv/fimport",
    license="Apache",
    author="Pauli Virtanen",
    author_email="pav@iki.fi",
    description="Python Fortran import hook",
    long_description=long_desc,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Fortran',
    ],
    py_modules=['fimport'],
    platforms='any',
    install_requires=['numpy>=1.4'],
)
