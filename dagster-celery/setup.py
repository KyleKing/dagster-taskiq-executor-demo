from pathlib import Path

from setuptools import find_packages, setup


def get_version() -> str:
    version: dict[str, str] = {}
    with open(Path(__file__).parent / "dagster_taskiq/version.py", encoding="utf8") as fp:
        exec(fp.read(), version)

    return version["__version__"]


ver = get_version()
# dont pin dev installs to avoid pip dep resolver issues
pin = "" if ver == "1!0+dev" else f"=={ver}"
setup(
    name="dagster-taskiq",
    version=ver,
    author="Dagster Labs",
    author_email="hello@dagsterlabs.com",
    license="Apache-2.0",
    description="Package for using Taskiq as Dagster's execution engine.",
    url="https://github.com/dagster-io/dagster/tree/master/python_modules/libraries/dagster-taskiq",
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    packages=find_packages(exclude=["dagster_taskiq_tests*"]),
    entry_points={"console_scripts": ["dagster-taskiq = dagster_taskiq.cli:main"]},
    python_requires=">=3.9,<3.14",
    install_requires=[
        f"dagster{pin}",
        "taskiq>=0.11.12,<1.0.0",
        "aioboto3>=13.0.0",
        "aiobotocore>=2.23.1,<3.0.0",
        "click>=5.0,<9.0",
        "pydantic>=1.0,<3.0",
    ],
    extras_require={
        "kubernetes": ["kubernetes"],
        "test": ["docker", "pytest-asyncio"],
    },
    zip_safe=False,
)
