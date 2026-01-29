from setuptools import setup, find_packages

setup(
    name="yt-azure",
    version="1.0.0",
    description="Download videos with yt-dlp and upload to Azure Blob Storage",
    author="Aylin, Claude (Anthropic)",
    py_modules=["yt_azure"],
    python_requires=">=3.7",
    install_requires=[
        "yt-dlp",
        "azure-storage-blob",
        "gradio",
        "pytz",  # Required by gradio but missing from its dependencies
    ],
    entry_points={
        "console_scripts": [
            "yt-azure=yt_azure:main",
        ],
    },
)
