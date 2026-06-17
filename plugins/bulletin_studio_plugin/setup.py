#!/usr/bin/env python
import os

from setuptools import find_packages, setup

PROJECT_DIR = os.path.dirname(__file__)
REQUIREMENTS_DIR = os.path.join(PROJECT_DIR, "requirements")
VERSION = "0.0.1"


def get_requirements(env):
    with open(os.path.join(REQUIREMENTS_DIR, f"{env}.txt")) as fp:
        return [
            x.strip()
            for x in fp.read().split("\n")
            if not x.strip().startswith("#") and not x.strip().startswith("-")
        ]


install_requires = get_requirements("base")

setup(
    name="bulletin-studio-plugin",
    version=VERSION,
    url="https://github.com/fgg-consultant/bulletin-studio-plugin",
    author="FGG Consultant",
    author_email="",
    license="MIT",
    description="A plugin to author and publish bulletins in Climweb.",
    long_description="A plugin to author and publish bulletins in Climweb.",
    platforms=["linux"],
    package_dir={"": "src"},
    packages=find_packages("src"),
    include_package_data=True,
    package_data={
        "bulletin_studio_plugin": [
            "templates/bulletin_studio_plugin/*.html",
            "templates/bulletin_studio_plugin/pdf/*",
            "static/bulletin_studio_plugin/**/*",
            "locale/*/LC_MESSAGES/*",
        ],
    },
    install_requires=install_requires
)
