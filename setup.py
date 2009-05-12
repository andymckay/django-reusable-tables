from setuptools import setup, find_packages

setup(
    name='django-reusable-table',
    version=__import__('reusable_table').__version__,
    description='A set of reusable tables that provide HTML, CSV and PDF views',
    long_description=open('README.rst').read(),
    author='Andy McKay',
    author_email='andy@clearwind.ca',
    license='BSD',
    packages=find_packages(exclude=['ez_setup']),
    include_package_data=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
