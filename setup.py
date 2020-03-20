import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="magiconfig",
    version="2.1.0",
    author="Kevin Pedro",
    author_email="kpedro88@gmail.com",
    description="An extension of argparse to configure Python with Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kpedro88/magiconfig",
    py_modules=["magiconfig"],
    classifiers=[
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, !=3.5.*',
    license="MIT",
    keywords="config, configuration, argparse, parameters, magiconfig",
    install_requires=[
        "six",
    ],
    include_package_data=True,
)
