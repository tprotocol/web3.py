
import pytest

from web3._utils.abi import (
    ABITypedData,
    abi_data_tree,
    collapse_if_tuple,
    data_tree_map,
    get_abi_inputs,
    get_tuple_component_types,
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


GET_ORDER_INFO_FN_ABI = {
    'constant': True,
    'inputs': [
        {
            'components': [
                {'name': 'makerAddress', 'type': 'address'},
                {'name': 'takerAddress', 'type': 'address'},
                {'name': 'feeRecipientAddress', 'type': 'address'},
                {'name': 'senderAddress', 'type': 'address'},
                {'name': 'makerAssetAmount', 'type': 'uint256'},
                {'name': 'takerAssetAmount', 'type': 'uint256'},
                {'name': 'makerFee', 'type': 'uint256'},
                {'name': 'takerFee', 'type': 'uint256'},
                {'name': 'expirationTimeSeconds', 'type': 'uint256'},
                {'name': 'salt', 'type': 'uint256'},
                {'name': 'makerAssetData', 'type': 'bytes'},
                {'name': 'takerAssetData', 'type': 'bytes'}
            ],
            'name': 'order',
            'type': 'tuple'
        },
    ],
    'name': 'getOrderInfo',
    'outputs': [
        {
            'components': [
                {'name': 'orderStatus', 'type': 'uint8'},
                {'name': 'orderHash', 'type': 'bytes32'},
                {'name': 'orderTakerAssetFilledAmount', 'type': 'uint256'}
            ],
            'name': 'orderInfo',
            'type': 'tuple'
        }
    ],
    'payable': False,
    'stateMutability': 'view',
    'type': 'function'
}

GET_ORDER_INFO_FN_ARGS_DICT = (
    {
        'expirationTimeSeconds': 12345,
        'feeRecipientAddress': '0x0000000000000000000000000000000000000000',
        'makerAddress': '0x0000000000000000000000000000000000000000',
        'makerAssetAmount': 1000000000000000000,
        'makerAssetData': b'00' * 20,
        'makerFee': 0,
        'salt': 12345,
        'senderAddress': '0x0000000000000000000000000000000000000000',
        'takerAddress': '0x0000000000000000000000000000000000000000',
        'takerAssetAmount': 1000000000000000000,
        'takerAssetData': b'00' * 20,
        'takerFee': 0
    },
)

GET_ORDER_INFO_FN_ARGS_TUPLE = (
    (
        '0x0000000000000000000000000000000000000000',
        '0x0000000000000000000000000000000000000000',
        '0x0000000000000000000000000000000000000000',
        '0x0000000000000000000000000000000000000000',
        1000000000000000000,
        1000000000000000000,
        0,
        0,
        12345,
        12345,
        b'0000000000000000000000000000000000000000',
        b'0000000000000000000000000000000000000000'
    ),
)


@pytest.mark.parametrize(
    'function_abi, arg_values, expected',
    [
        (
            GET_ORDER_INFO_FN_ABI,
            GET_ORDER_INFO_FN_ARGS_DICT,
            (
                [
                    '(address,address,address,address,uint256,uint256,uint256,uint256,uint256,' +
                    'uint256,bytes,bytes)'
                ],
                GET_ORDER_INFO_FN_ARGS_TUPLE,
            ),
        ),
        (
            GET_ORDER_INFO_FN_ABI,
            GET_ORDER_INFO_FN_ARGS_TUPLE,
            (
                [
                    '(address,address,address,address,uint256,uint256,uint256,uint256,uint256,' +
                    'uint256,bytes,bytes)'
                ],
                GET_ORDER_INFO_FN_ARGS_TUPLE,
            ),
        ),
        (
            {'payable': False, 'stateMutability': 'nonpayable', 'type': 'fallback'},
            (),
            ([], ()),
        )
    ]
)
def test_get_abi_inputs(function_abi, arg_values, expected):
    assert get_abi_inputs(function_abi, arg_values) == expected


@pytest.mark.parametrize(
    'abi_type, expected',
    [
        (
            {
                'components': [
                    {'name': 'anAddress', 'type': 'address'},
                    {'name': 'anInt', 'type': 'uint256'},
                    {'name': 'someBytes', 'type': 'bytes'},
                ],
                'name': 'order',
                'type': 'tuple',
            },
            '(address,uint256,bytes)'
        ),
        (
            {
                'components': [
                    {'name': 'anAddress', 'type': 'address'},
                    {'name': 'anInt', 'type': 'uint256'},
                    {'name': 'someBytes', 'type': 'bytes'},
                    {
                        'name': 'aNestedTuple',
                        'type': 'tuple',
                        'components': [
                            {'name': 'anotherInt', 'type': 'uint256'},
                        ]
                    }
                ],
                'name': 'order',
                'type': 'tuple',
            },
            '(address,uint256,bytes,(uint256))'
        ),
    ]
)
def test_collapse_if_tuple(abi_type, expected):
    assert collapse_if_tuple(abi_type) == expected


@pytest.mark.parametrize(
    'tuple_type, expected',
    [
        ('(uint256,uint256)', ['uint256', 'uint256']),
        ('(uint256,(uint256,uint256),uint256)', ['uint256', '(uint256,uint256)', 'uint256']),
        ('((uint256,uint256),uint256)', ['(uint256,uint256)', 'uint256']),
        ('(uint256,(uint256,uint256))', ['uint256', '(uint256,uint256)']),
        ('(((uint256)))', ['((uint256))']),
    ]
)
def test_get_tuple_component_types(tuple_type, expected):
    assert get_tuple_component_types(tuple_type) == expected
