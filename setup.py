import setuptools
import json

def load_long_description():
    with open("README.md", "r") as fh:
        long_description = fh.read()
    return long_description

def get_version():
    # get semver version [major.minor.patch]
    json_version = {}
    with open('.version.json', 'r') as f:
        json_version = json.load(f)
    return '.'.join(str(w) for w in [json_version['major'],json_version['minor'],json_version['patch']])

setuptools.setup(
    name='compressed_dictionary',
    version=get_version(),
    description='A dictionary which values are automatically compressed to save memory.',
    long_description=load_long_description(),
    long_description_content_type="text/markdown",
    url='https://github.com/lucadiliello/compressed-dictionary.git',
    author='Luca Di Liello',
    author_email='luca.diliello@unitn.it',
    license='GNU v2',
    packages=setuptools.find_packages(),
    install_requires=['tqdm'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Natural Language :: English"
    ]
)

