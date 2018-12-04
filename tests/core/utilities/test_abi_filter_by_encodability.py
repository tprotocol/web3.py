import pytest

from web3._utils.abi import (
    filter_by_encodability,
)

GET_ORDER_INFO_ABI = [
    {
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
            }
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
]

GET_ORDER_INFO_ARGS = (
    {
        'expirationTimeSeconds': 12345,
        'feeRecipientAddress': '0x0000000000000000000000000000000000000000',
        'makerAddress': '0x0000000000000000000000000000000000000000',
        'makerAssetAmount': 1000000000000000000,
        'makerAssetData': b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                          b'\x00\x00\x00\x00\x00\x00\x00\x00',
        'makerFee': 0,
        'salt': 12345,
        'senderAddress': '0x0000000000000000000000000000000000000000',
        'takerAddress': '0x0000000000000000000000000000000000000000',
        'takerAssetAmount': 1000000000000000000,
        'takerAssetData': b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                          b'\x00\x00\x00\x00\x00\x00\x00\x00',
        'takerFee': 0
    },
)


@pytest.mark.parametrize(
    'arguments,contract_abi',
    (
        (GET_ORDER_INFO_ARGS, GET_ORDER_INFO_ABI),
    )
)
def test_filter_by_encodability(arguments, contract_abi):
    assert filter_by_encodability(arguments, {}, contract_abi) == contract_abi
