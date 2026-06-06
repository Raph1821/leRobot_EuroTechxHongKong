from glob import glob

from setuptools import find_packages, setup

package_name = "so101_patrol"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Myron Sydorov",
    maintainer_email="sydorov.myron@gmail.com",
    description="CareAI autonomous patrol mode for the SO-101 follower arm.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "patrol_node = so101_patrol.patrol_node:main",
        ],
    },
)
