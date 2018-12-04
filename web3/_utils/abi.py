from collections import (
    namedtuple,
)
import itertools
import re

from eth_abi import (
    is_encodable as eth_abi_is_encodable,
)
from eth_utils import (
    is_hex,
    is_list_like,
    to_bytes,
    to_text,
    to_tuple,
)

from web3._utils.ens import (
    is_ens_name,
)
from web3._utils.formatters import (
    recursive_map,
)
from web3._utils.toolz import (
    curry,
    partial,
    pipe,
)
from web3.exceptions import (
    FallbackNotFound,
)


def filter_by_type(_type, contract_abi):
    return [abi for abi in contract_abi if abi['type'] == _type]


def filter_by_name(name, contract_abi):
    return [
        abi
        for abi
        in contract_abi
        if (
            abi['type'] not in ('fallback', 'constructor') and
            abi['name'] == name
        )
    ]


def get_abi_input_types(abi):
    if 'inputs' not in abi and abi['type'] == 'fallback':
        return []
    else:
        return [collapse_if_tuple(abi_input) for abi_input in abi['inputs']]


def collapse_if_tuple(abi_type):
    """Converts an ABI tuple type to the format expected by eth_abi.

    Returns the type Returns the parenthesized list of tuple component types,
    as expected by eth_abi.  If `abi_type` is not a tuple, just returns its
    type.

    >>> collapse_if_tuple(
    ...     {
    ...         'components': [
    ...             {'name': 'makerAddress', 'type': 'address'},
    ...             {'name': 'takerAddress', 'type': 'address'},
    ...             {'name': 'feeRecipientAddress', 'type': 'address'},
    ...             {'name': 'senderAddress', 'type': 'address'},
    ...             {'name': 'makerAssetAmount', 'type': 'uint256'},
    ...             {'name': 'takerAssetAmount', 'type': 'uint256'},
    ...             {'name': 'makerFee', 'type': 'uint256'},
    ...             {'name': 'takerFee', 'type': 'uint256'},
    ...             {'name': 'expirationTimeSeconds', 'type': 'uint256'},
    ...             {'name': 'salt', 'type': 'uint256'},
    ...             {'name': 'makerAssetData', 'type': 'bytes'},
    ...             {'name': 'takerAssetData', 'type': 'bytes'},
    ...         ],
    ...         'name': 'order',
    ...         'type': 'tuple',
    ...     }
    ... )
    '(address,address,address,address,uint256,uint256,uint256,uint256,uint256,uint256,bytes,bytes)'
    """
    if isinstance(abi_type["type"], str) and abi_type["type"] != 'tuple':
        return abi_type["type"]

    component_types = [
        collapse_if_tuple(component) for component in abi_type["components"]
    ]

    return "(" + ",".join(component_types) + ")"


def get_abi_output_types(abi):
    if abi['type'] == 'fallback':
        return []
    else:
        return [collapse_if_tuple(arg) for arg in abi['outputs']]


def get_abi_input_names(abi):
    if 'inputs' not in abi and abi['type'] == 'fallback':
        return []
    else:
        return [arg['name'] for arg in abi['inputs']]


def get_fallback_func_abi(contract_abi):
    fallback_abis = filter_by_type('fallback', contract_abi)
    if fallback_abis:
        return fallback_abis[0]
    else:
        raise FallbackNotFound("No fallback function was found in the contract ABI.")


def fallback_func_abi_exists(contract_abi):
    return filter_by_type('fallback', contract_abi)


def get_indexed_event_inputs(event_abi):
    return [arg for arg in event_abi['inputs'] if arg['indexed'] is True]


def exclude_indexed_event_inputs(event_abi):
    return [arg for arg in event_abi['inputs'] if arg['indexed'] is False]


def filter_by_argument_count(num_arguments, contract_abi):
    return [
        abi
        for abi
        in contract_abi
        if len(abi['inputs']) == num_arguments
    ]


def filter_by_argument_name(argument_names, contract_abi):
    return [
        abi
        for abi in contract_abi
        if set(argument_names).intersection(
            get_abi_input_names(abi)
        ) == set(argument_names)
    ]


try:
    from eth_abi.abi import (
        process_type,
        collapse_type,
    )
except ImportError:
    from eth_abi.grammar import (
        parse as parse_type_string,
        normalize as normalize_type_string,
        TupleType,
    )

    def process_type(type_str):
        normalized_type_str = normalize_type_string(type_str)
        abi_type = parse_type_string(normalized_type_str)

        if isinstance(abi_type, TupleType):
            type_str_repr = repr(type_str)
            if type_str != normalized_type_str:
                type_str_repr = '{} (normalized to {})'.format(
                    type_str_repr,
                    repr(normalized_type_str),
                )

            raise ValueError(
                "Cannot process type {}: tuple types not supported".format(
                    type_str_repr,
                )
            )

        abi_type.validate()

        sub = abi_type.sub
        if isinstance(sub, tuple):
            sub = 'x'.join(map(str, sub))
        elif isinstance(sub, int):
            sub = str(sub)
        else:
            sub = ''

        arrlist = abi_type.arrlist
        if isinstance(arrlist, tuple):
            arrlist = list(map(list, arrlist))
        else:
            arrlist = []

        return abi_type.base, sub, arrlist

    def collapse_type(base, sub, arrlist):
        return base + str(sub) + ''.join(map(repr, arrlist))


def is_encodable(_type, value):
    if not isinstance(_type, str):
        raise ValueError("is_encodable only accepts type strings")

    if _type[0] == "(":  # it's a tuple. check encodability of each component
        components = _type.strip("()").split(",")
        values = value
        if not any(
            [isinstance(values, collection) for collection in [list, tuple]]
        ):
            return False

        if len(components) != len(values):
            return False

        return all(
            [
                is_encodable(component, value)
                for component, value
                in zip(components, values)
            ]
        )

    base, sub, arrlist = process_type(_type)

    if arrlist:
        if not is_list_like(value):
            return False
        if arrlist[-1] and len(value) != arrlist[-1][0]:
            return False
        sub_type = (base, sub, arrlist[:-1])
        return all(is_encodable(collapse_type(*sub_type), sub_value) for sub_value in value)
    elif base == 'address' and is_ens_name(value):
        # ENS names can be used anywhere an address is needed
        # Web3.py will resolve the name to an address before encoding it
        return True
    elif base == 'bytes' and isinstance(value, str):
        # Hex-encoded bytes values can be used anywhere a bytes value is needed
        if is_hex(value) and len(value) % 2 == 0:
            # Require hex-encoding of full bytes (even length)
            bytes_val = to_bytes(hexstr=value)
            return eth_abi_is_encodable(_type, bytes_val)
        else:
            return False
    elif base == 'string' and isinstance(value, bytes):
        # bytes that were encoded with utf-8 can be used anywhere a string is needed
        try:
            string_val = to_text(value)
        except UnicodeDecodeError:
            return False
        else:
            return eth_abi_is_encodable(_type, string_val)
    else:
        return eth_abi_is_encodable(_type, value)


def filter_by_encodability(args, kwargs, contract_abi):
    return [
        function_abi
        for function_abi
        in contract_abi
        if check_if_arguments_can_be_encoded(function_abi, args, kwargs)
    ]


def get_abi_inputs(function_abi, arg_values):
    """Similar to get_abi_input_types(), but gets values too.

    Returns a zip of types and their corresponding argument values.
    Importantly, looks in `function_abi` for tuples, and for any found, (a)
    translates them from the ABI dict representation to the parenthesized type
    list representation that's expected by eth_abi, and (b) translates their
    corresponding arguments values from the python dict representation to the
    tuple representation expected by eth_abi.

    >>> get_abi_inputs(
    ...     {'constant': True,
    ...      'inputs': [{'components': [{'name': 'makerAddress', 'type': 'address'},
    ...                                 {'name': 'takerAddress', 'type': 'address'},
    ...                                 {'name': 'feeRecipientAddress', 'type': 'address'},
    ...                                 {'name': 'senderAddress', 'type': 'address'},
    ...                                 {'name': 'makerAssetAmount', 'type': 'uint256'},
    ...                                 {'name': 'takerAssetAmount', 'type': 'uint256'},
    ...                                 {'name': 'makerFee', 'type': 'uint256'},
    ...                                 {'name': 'takerFee', 'type': 'uint256'},
    ...                                 {'name': 'expirationTimeSeconds',
    ...                                  'type': 'uint256'},
    ...                                 {'name': 'salt', 'type': 'uint256'},
    ...                                 {'name': 'makerAssetData', 'type': 'bytes'},
    ...                                 {'name': 'takerAssetData', 'type': 'bytes'}],
    ...                  'name': 'order',
    ...                  'type': 'tuple'}],
    ...      'name': 'getOrderInfo',
    ...      'outputs': [{'components': [{'name': 'orderStatus', 'type': 'uint8'},
    ...                                  {'name': 'orderHash', 'type': 'bytes32'},
    ...                                  {'name': 'orderTakerAssetFilledAmount',
    ...                                   'type': 'uint256'}],
    ...                   'name': 'orderInfo',
    ...                   'type': 'tuple'}],
    ...      'payable': False,
    ...      'stateMutability': 'view',
    ...      'type': 'function'},
    ...     ({'expirationTimeSeconds': 12345,
    ...       'feeRecipientAddress': '0x0000000000000000000000000000000000000000',
    ...       'makerAddress': '0x0000000000000000000000000000000000000000',
    ...       'makerAssetAmount': 1000000000000000000,
    ...       'makerAssetData': b'00'*20,
    ...       'makerFee': 0,
    ...       'salt': 12345,
    ...       'senderAddress': '0x0000000000000000000000000000000000000000',
    ...       'takerAddress': '0x0000000000000000000000000000000000000000',
    ...       'takerAssetAmount': 1000000000000000000,
    ...       'takerAssetData': b'00'*20,
    ...       'takerFee': 0},)
    ... )
    (['(address,address,address,address,uint256,uint256,uint256,uint256,uint256,uint256,bytes,bytes)'], (('0x0000000000000000000000000000000000000000', '0x0000000000000000000000000000000000000000', '0x0000000000000000000000000000000000000000', '0x0000000000000000000000000000000000000000', 1000000000000000000, 1000000000000000000, 0, 0, 12345, 12345, b'0000000000000000000000000000000000000000', b'0000000000000000000000000000000000000000'),))

    >>> get_abi_inputs(
    ...     {'constant': True,
    ...      'inputs': [{'components': [{'name': 'makerAddress', 'type': 'address'},
    ...                                 {'name': 'takerAddress', 'type': 'address'},
    ...                                 {'name': 'feeRecipientAddress', 'type': 'address'},
    ...                                 {'name': 'senderAddress', 'type': 'address'},
    ...                                 {'name': 'makerAssetAmount', 'type': 'uint256'},
    ...                                 {'name': 'takerAssetAmount', 'type': 'uint256'},
    ...                                 {'name': 'makerFee', 'type': 'uint256'},
    ...                                 {'name': 'takerFee', 'type': 'uint256'},
    ...                                 {'name': 'expirationTimeSeconds',
    ...                                  'type': 'uint256'},
    ...                                 {'name': 'salt', 'type': 'uint256'},
    ...                                 {'name': 'makerAssetData', 'type': 'bytes'},
    ...                                 {'name': 'takerAssetData', 'type': 'bytes'}],
    ...                  'name': 'order',
    ...                  'type': 'tuple'}],
    ...      'name': 'getOrderInfo',
    ...      'outputs': [{'components': [{'name': 'orderStatus', 'type': 'uint8'},
    ...                                  {'name': 'orderHash', 'type': 'bytes32'},
    ...                                  {'name': 'orderTakerAssetFilledAmount',
    ...                                   'type': 'uint256'}],
    ...                   'name': 'orderInfo',
    ...                   'type': 'tuple'}],
    ...      'payable': False,
    ...      'stateMutability': 'view',
    ...      'type': 'function'},
    ...     (('0x0000000000000000000000000000000000000000',
    ...       '0x0000000000000000000000000000000000000000',
    ...       '0x0000000000000000000000000000000000000000',
    ...       '0x0000000000000000000000000000000000000000',
    ...       1000000000000000000,
    ...       1000000000000000000,
    ...       0,
    ...       0,
    ...       12345,
    ...       12345,
    ...       b'0000000000000000000000000000000000000000',
    ...       b'0000000000000000000000000000000000000000'),),
    ... )
    (['(address,address,address,address,uint256,uint256,uint256,uint256,uint256,uint256,bytes,bytes)'], (('0x0000000000000000000000000000000000000000', '0x0000000000000000000000000000000000000000', '0x0000000000000000000000000000000000000000', '0x0000000000000000000000000000000000000000', 1000000000000000000, 1000000000000000000, 0, 0, 12345, 12345, b'0000000000000000000000000000000000000000', b'0000000000000000000000000000000000000000'),))
    """  # noqa: E501 (line too long)
    new_types = []
    new_arguments = tuple()
    for abi_input, arg_value in zip(function_abi["inputs"], arg_values):
        if abi_input["type"] == "tuple":
            component_types = []
            component_values = []
            for component, value in zip(abi_input["components"], arg_value):
                component_types.append(component["type"])
                if isinstance(arg_value, dict):
                    component_values.append(arg_value[component["name"]])
                elif isinstance(arg_value, tuple):
                    component_values.append(value)
                else:
                    raise TypeError(
                        "Unknown value type {} for ABI type 'tuple'"
                        .format(type(arg_value))
                    )
            new_types.append("(" + ",".join(component_types) + ")")
            new_arguments += (tuple(component_values),)
        else:
            new_arguments += (arg_value,)
    return new_types, new_arguments


def check_if_arguments_can_be_encoded(function_abi, args, kwargs):
    try:
        arguments = merge_args_and_kwargs(function_abi, args, kwargs)
    except TypeError:
        return False

    if len(function_abi.get('inputs', [])) != len(arguments):
        return False

    types, arguments = get_abi_inputs(function_abi, arguments)

    return all(
        is_encodable(_type, arg)
        for _type, arg in zip(types, arguments)
    )


def merge_args_and_kwargs(function_abi, args, kwargs):
    if len(args) + len(kwargs) != len(function_abi.get('inputs', [])):
        raise TypeError(
            "Incorrect argument count.  Expected '{0}'.  Got '{1}'".format(
                len(function_abi['inputs']),
                len(args) + len(kwargs),
            )
        )

    if not kwargs:
        return args

    args_as_kwargs = {
        arg_abi['name']: arg
        for arg_abi, arg in zip(function_abi['inputs'], args)
    }
    duplicate_keys = set(args_as_kwargs).intersection(kwargs.keys())
    if duplicate_keys:
        raise TypeError(
            "{fn_name}() got multiple values for argument(s) '{dups}'".format(
                fn_name=function_abi['name'],
                dups=', '.join(duplicate_keys),
            )
        )

    sorted_arg_names = [arg_abi['name'] for arg_abi in function_abi['inputs']]

    unknown_kwargs = {key for key in kwargs.keys() if key not in sorted_arg_names}
    if unknown_kwargs:
        if function_abi.get('name'):
            raise TypeError(
                "{fn_name}() got unexpected keyword argument(s) '{dups}'".format(
                    fn_name=function_abi.get('name'),
                    dups=', '.join(unknown_kwargs),
                )
            )
        # show type instead of name in the error message incase key 'name' is missing.
        raise TypeError(
            "Type: '{_type}' got unexpected keyword argument(s) '{dups}'".format(
                _type=function_abi.get('type'),
                dups=', '.join(unknown_kwargs),
            )
        )

    sorted_args = list(zip(
        *sorted(
            itertools.chain(kwargs.items(), args_as_kwargs.items()),
            key=lambda kv: sorted_arg_names.index(kv[0])
        )
    ))
    if sorted_args:
        return sorted_args[1]
    else:
        return tuple()


def get_constructor_abi(contract_abi):
    candidates = [
        abi for abi in contract_abi if abi['type'] == 'constructor'
    ]
    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) == 0:
        return None
    elif len(candidates) > 1:
        raise ValueError("Found multiple constructors.")


DYNAMIC_TYPES = ['bytes', 'string']

INT_SIZES = range(8, 257, 8)
BYTES_SIZES = range(1, 33)
UINT_TYPES = ['uint{0}'.format(i) for i in INT_SIZES]
INT_TYPES = ['int{0}'.format(i) for i in INT_SIZES]
BYTES_TYPES = ['bytes{0}'.format(i) for i in BYTES_SIZES] + ['bytes32.byte']

STATIC_TYPES = list(itertools.chain(
    ['address', 'bool'],
    UINT_TYPES,
    INT_TYPES,
    BYTES_TYPES,
))

BASE_TYPE_REGEX = '|'.join((
    _type + '(?![a-z0-9])'
    for _type
    in itertools.chain(STATIC_TYPES, DYNAMIC_TYPES)
))

SUB_TYPE_REGEX = (
    r'\['
    '[0-9]*'
    r'\]'
)

TYPE_REGEX = (
    '^'
    '(?:{base_type})'
    '(?:(?:{sub_type})*)?'
    '$'
).format(
    base_type=BASE_TYPE_REGEX,
    sub_type=SUB_TYPE_REGEX,
)


def is_recognized_type(abi_type):
    return bool(re.match(TYPE_REGEX, abi_type))


def is_bool_type(abi_type):
    return abi_type == 'bool'


def is_uint_type(abi_type):
    return abi_type in UINT_TYPES


def is_int_type(abi_type):
    return abi_type in INT_TYPES


def is_address_type(abi_type):
    return abi_type == 'address'


def is_bytes_type(abi_type):
    return abi_type in BYTES_TYPES + ['bytes']


def is_string_type(abi_type):
    return abi_type == 'string'


@curry
def is_length(target_length, value):
    return len(value) == target_length


def size_of_type(abi_type):
    """
    Returns size in bits of abi_type
    """
    if 'string' in abi_type:
        return None
    if 'byte' in abi_type:
        return None
    if '[' in abi_type:
        return None
    if abi_type == 'bool':
        return 8
    if abi_type == 'address':
        return 160
    return int(re.sub(r"\D", "", abi_type))


END_BRACKETS_OF_ARRAY_TYPE_REGEX = r"\[[^]]*\]$"


def sub_type_of_array_type(abi_type):
    if not is_array_type(abi_type):
        raise ValueError(
            "Cannot parse subtype of nonarray abi-type: {0}".format(abi_type)
        )

    return re.sub(END_BRACKETS_OF_ARRAY_TYPE_REGEX, '', abi_type, 1)


def length_of_array_type(abi_type):
    if not is_array_type(abi_type):
        raise ValueError(
            "Cannot parse length of nonarray abi-type: {0}".format(abi_type)
        )

    inner_brackets = re.search(END_BRACKETS_OF_ARRAY_TYPE_REGEX, abi_type).group(0).strip("[]")
    if not inner_brackets:
        return None
    else:
        return int(inner_brackets)


ARRAY_REGEX = (
    "^"
    "[a-zA-Z0-9_]+"
    "({sub_type})+"
    "$"
).format(sub_type=SUB_TYPE_REGEX)


def is_array_type(abi_type):
    return bool(re.match(ARRAY_REGEX, abi_type))


NAME_REGEX = (
    '[a-zA-Z_]'
    '[a-zA-Z0-9_]*'
)


ENUM_REGEX = (
    '^'
    '{lib_name}'
    r'\.'
    '{enum_name}'
    '$'
).format(lib_name=NAME_REGEX, enum_name=NAME_REGEX)


def is_probably_enum(abi_type):
    return bool(re.match(ENUM_REGEX, abi_type))


@to_tuple
def normalize_event_input_types(abi_args):
    for arg in abi_args:
        if is_recognized_type(arg['type']):
            yield arg
        elif is_probably_enum(arg['type']):
            yield {k: 'uint8' if k == 'type' else v for k, v in arg.items()}
        else:
            yield arg


def abi_to_signature(abi):
    function_signature = "{fn_name}({fn_input_types})".format(
        fn_name=abi['name'],
        fn_input_types=','.join([
            arg['type'] for arg in normalize_event_input_types(abi.get('inputs', []))
        ]),
    )
    return function_signature


########################################################
#
#  Conditionally modifying data, tagged with ABI Types
#
########################################################


@curry
def map_abi_data(normalizers, types, data):
    '''
    This function will apply normalizers to your data, in the
    context of the relevant types. Each normalizer is in the format:

    def normalizer(datatype, data):
        # Conditionally modify data
        return (datatype, data)

    Where datatype is a valid ABI type string, like "uint".

    In case of an array, like "bool[2]", normalizer will receive `data`
    as an iterable of typed data, like `[("bool", True), ("bool", False)]`.

    Internals
    ---

    This is accomplished by:

    1. Decorating the data tree with types
    2. Recursively mapping each of the normalizers to the data
    3. Stripping the types back out of the tree
    '''
    pipeline = itertools.chain(
        [abi_data_tree(types)],
        map(data_tree_map, normalizers),
        [partial(recursive_map, strip_abi_type)],
    )

    return pipe(data, *pipeline)


@curry
def abi_data_tree(types, data):
    '''
    Decorate the data tree with pairs of (type, data). The pair tuple is actually an
    ABITypedData, but can be accessed as a tuple.

    As an example:

    >>> abi_data_tree(types=["bool[2]", "uint"], data=[[True, False], 0])
    [ABITypedData(abi_type='bool[2]', data=[ABITypedData(abi_type='bool', data=True), ABITypedData(abi_type='bool', data=False)]), ABITypedData(abi_type='uint256', data=0)]
    '''  # noqa: E501 (line too long)
    return [
        abi_sub_tree(data_type, data_value)
        for data_type, data_value
        in zip(types, data)
    ]


@curry
def data_tree_map(func, data_tree):
    '''
    Map func to every ABITypedData element in the tree. func will
    receive two args: abi_type, and data
    '''
    def map_to_typed_data(elements):
        if (
            isinstance(elements, str) and
            len(elements) > 0 and
            elements[0] == "("
        ):
            return elements
        elif isinstance(elements, ABITypedData):
            if (
                isinstance(elements.abi_type, str) and
                elements.abi_type[0] == "("
            ):
                return elements
            elif elements.abi_type is not None:
                return ABITypedData(func(*elements))
        return elements
    return recursive_map(map_to_typed_data, data_tree)


class ABITypedData(namedtuple('ABITypedData', 'abi_type, data')):
    '''
    This class marks data as having a certain ABI-type.

    >>> addr1 = "0x" + "0" * 20
    >>> addr2 = "0x" + "f" * 20
    >>> a1 = ABITypedData(['address', addr1])
    >>> a2 = ABITypedData(['address', addr2])
    >>> addrs = ABITypedData(['address[]', [a1, a1]])

    You can access the fields using tuple() interface, or with
    attributes:

    >>> assert a1.abi_type == a1[0]
    >>> assert a1.data == a1[1]

    Unlike a typical `namedtuple`, you initialize with a single
    positional argument that is iterable, to match the init
    interface of all other relevant collections.
    '''
    def __new__(cls, iterable):
        return super().__new__(cls, *iterable)


def abi_sub_tree(data_type, data_value):
    if (
        isinstance(data_type, str) and
        data_type[0] == "(" and
        isinstance(data_value, tuple)
    ):
        return ABITypedData([data_type, data_value])

    if data_type is None:
        return ABITypedData([None, data_value])

    try:
        base, sub, arrlist = data_type
    except ValueError:
        base, sub, arrlist = process_type(data_type)

    collapsed = collapse_type(base, sub, arrlist)

    if arrlist:
        sub_type = (base, sub, arrlist[:-1])
        return ABITypedData([
            collapsed,
            [
                abi_sub_tree(sub_type, sub_value)
                for sub_value in data_value
            ],
        ])
    else:
        return ABITypedData([collapsed, data_value])


def strip_abi_type(elements):
    if isinstance(elements, ABITypedData):
        return elements.data
    else:
        return elements
