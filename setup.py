from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="univapay",
    version="0.1.0",
    author="Nayeem Islam",
    author_email="islam.nayeem@outlook.com",
    description="Python SDK for Univapay payment platform - supports Flask, Django, FastAPI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/NoManNayeem/univapay-python",
    packages=find_packages(exclude=["tests", "tests.*", "examples", "examples.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Office/Business :: Financial :: Point-Of-Sale",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: Django",
        "Framework :: Flask",
        "Framework :: FastAPI",
    ],
    python_requires=">=3.10",
    install_requires=[
        "requests>=2.28.0",
        "pydantic>=2.0.0",
        "python-dateutil>=2.8.2",
        "cryptography>=38.0.0",
    ],
    extras_require={
        "django": ["django>=4.0", "djangorestframework>=3.14.0"],
        "flask": ["flask>=2.0.0"],
        "fastapi": ["fastapi>=0.100.0"],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=3.0.0",
            "pytest-mock>=3.6.1",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
            "responses>=0.20.0",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/NoManNayeem/univapay-python/issues",
        "Source": "https://github.com/NoManNayeem/univapay-python",
        "Documentation": "https://univapay-python.readthedocs.io/",
    },
    keywords="univapay payment gateway api sdk python django flask fastapi",
)