from glob import glob
import os

from setuptools import find_packages
from setuptools import setup

package_name = 'so_arm_100_isaac_sim'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'scripts'), glob('scripts/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Bruk Gebregziabher',
    maintainer_email='bruk@signalbotics.com',
    description='Isaac Sim integration for the SO-100 5-DOF robot arm.',
    license='Apache 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [],
    },
)
