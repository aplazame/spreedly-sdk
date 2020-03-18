from setuptools import setup

setup(
    name='spreedly-sdk',
    version='0.3.0',
    author='aplazame',
    author_email='dev@aplazame.com',
    packages=['spreedly_sdk'],
    scripts=[],
    test_suite='tests',
    tests_require=[],
    zip_safe=False,
    url='https://github.com/aplazame',
    license='BSD 3-clause "New" or "Revised License"',
    description='Python Interface to the Spreedly API',
    install_requires=['requests>=1.1.0', 'lxml', 'xmltodict', 'python-dateutil'],
    dependency_links=[
        'https://github.com/kennethreitz/requests',
        'https://github.com/lxml/lxml/',
        'https://github.com/martinblech/xmltodict'],
    classifiers=[
        'Programming Language :: Python',
        'Natural Language :: English',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    keywords='python spreedly rest sdk',
    python_requires='>=3',
)
