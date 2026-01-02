import setuptools
from magiconfig import __version__

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="magiconfig",
    version=__version__,
    author="Kevin Pedro",
    author_email="kpedro88@gmail.com",
    description="An extension of argparse to configure Python with Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kpedro88/magiconfig",
    py_modules=["magiconfig"],
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.9',
    license="MIT",
    keywords="config, configuration, argparse, parameters, magiconfig",
    include_package_data=True,
)
