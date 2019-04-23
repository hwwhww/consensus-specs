from distutils.core import setup


deps = {
    'gen_base': [
        "ruamel.yaml==0.15.87",
        "eth-utils==1.4.1",
    ],
}

deps['dev'] = (
    deps['gen_base']
)

install_requires = deps['gen_base']

setup(
    name='gen_helpers',
    packages=['gen_base'],
    install_requires=install_requires,
)
