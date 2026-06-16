from setuptools import setup, find_packages

setup(
    name="domain-flipper",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "httpx>=0.27.0",
        "beautifulsoup4>=4.12.0",
        "playwright>=1.40.0",
        "fake-useragent>=1.5.0",
        "tenacity>=8.2.0",
        "python-dotenv>=1.0.0",
        "rich>=13.7.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "aiohttp>=3.9.0",
        "aiosqlite>=0.20.0",
    ],
    entry_points={
        "console_scripts": [
            "domain-flipper=src.main:main",
        ],
    },
)
