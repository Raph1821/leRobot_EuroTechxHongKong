from setuptools import setup, find_packages
from glob import glob

package_name = "so101_pick_place"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Myron Sydorov",
    maintainer_email="sydorov.myron@gmail.com",
    description="Wrist-camera guided pick-and-place for SO-101 follower arm",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "pick_place_node = so101_pick_place.pick_place_node:main",
            "overhead_pick_place_node = so101_pick_place.overhead_pick_place_node:main",
        ],
    },
)
