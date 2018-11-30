
import pytest

from web3._utils.abi import (
    ABITypedData,
    abi_data_tree,
    data_tree_map,
    map_abi_data,
)
from web3._utils.normalizers import (
    BASE_RETURN_NORMALIZERS,
    addresses_checksummed,
)


@pytest.mark.parametrize(
    'types, data, expected',
    [
        (
            ["bool[2]", "bytes"],
            [[True, False], b'\x00\xFF'],
            [("bool[2]", [("bool", True), ("bool", False)]), ("bytes", b'\x00\xFF')],
        ),
        (
            ["uint256[]"],
            [[0, 2**256 - 1]],
            [("uint256[]", [("uint256", 0), ("uint256", 2**256 - 1)])],
        ),
    ],
)
def test_abi_data_tree(types, data, expected):
    assert abi_data_tree(types, data) == expected


@pytest.mark.parametrize(
    'func, data_tree, expected',
    [
        (
            addresses_checksummed,
            [
                ABITypedData(
                    [
                        'address',
                        b'\xf2\xe2F\xbbv\xdf\x87l\xef\x8b8\xae\x84\x13\x0fOU\xde9[',
                    ]
                ),
                ABITypedData([None, 'latest'])
            ],
            [
                ABITypedData(
                    [
                        'address',
                        '0xF2E246BB76DF876Cef8b38ae84130F4F55De395b',
                    ]
                ),
                ABITypedData([None, 'latest'])
            ]
        )
    ],
)
def test_data_tree_map(func, data_tree, expected):
    assert data_tree_map(func, data_tree) == expected


@pytest.mark.parametrize(
    'types, data, funcs, expected',
    [
        (  # like web3._utils.rpc_abi.RPC_ABIS['eth_getCode']
            ['address', None],
            [b'\xf2\xe2F\xbbv\xdf\x87l\xef\x8b8\xae\x84\x13\x0fOU\xde9[', 'latest'],
            BASE_RETURN_NORMALIZERS,
            ['0xF2E246BB76DF876Cef8b38ae84130F4F55De395b', 'latest'],
        ),
        (
            ["bool[2]", "int256"],
            [[True, False], 9876543210],
            [
                lambda typ, dat: (typ, 'Tru-dat') if typ == 'bool' and dat else (typ, dat),
                lambda typ, dat: (typ, hex(dat)) if typ == 'int256' else (typ, dat),
            ],
            [['Tru-dat', False], '0x24cb016ea'],
        ),
        (
            ["address"],
            ['0x5b2063246f2191f18f2675cedb8b28102e957458'],
            BASE_RETURN_NORMALIZERS,
            ['0x5B2063246F2191f18F2675ceDB8b28102e957458'],
        ),
        (
            ["address[]"],
            [['0x5b2063246f2191f18f2675cedb8b28102e957458'] * 2],
            BASE_RETURN_NORMALIZERS,
            [['0x5B2063246F2191f18F2675ceDB8b28102e957458'] * 2],
        ),
    ],
)
def test_map_abi_data(types, data, funcs, expected):
    assert map_abi_data(funcs, types, data) == expected
