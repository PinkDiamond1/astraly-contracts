# https://github.com/dewi-tim/cairo-contracts/blob/feature-erc1155/tests/token/erc1155/test_ERC1155_Mintable_Burnable.py
import pytest
import pytest_asyncio

from signers import MockSigner
from utils import *

mock_signer = MockSigner(123456789987654321)
account_path = 'openzeppelin/account/presets/Account.cairo'
erc1155_path = 'AstralyLotteryToken.cairo'
ido_path = 'AstralyIDOContract.cairo'
factory_path = 'AstralyIDOFactory.cairo'
receiver_path = 'mocks/ERC1155_receiver_mock.cairo'
rnd_nbr_gen_path = 'utils/xoroshiro128_starstar.cairo'


def uint_array(l):
    return list(map(uint, l))


def uarr2cd(arr):
    acc = [len(arr)]
    for lo, hi in arr:
        acc.append(lo)
        acc.append(hi)
    return acc
# Constants


TRUE = 1
FALSE = 0
NON_BOOLEAN = 2
ZERO_ADDRESS = 0

DATA = []

TOKEN_ID = uint(0)
MINT_AMOUNT = uint(1000)
BURN_AMOUNT = uint(500)
TRANSFER_AMOUNT = uint(500)
INVALID_UINT = uint(MAX_UINT256[0]+1)

ACCOUNT = 123
ACCOUNTS = [123, 234, 345]
TOKEN_IDS = uint_array([0, 1, 2])
MINT_AMOUNTS = uint_array([1000, 2000, 3000])
BURN_AMOUNTS = uint_array([500, 1000, 1500])
TRANSFER_AMOUNTS = uint_array([500, 1000, 1500])
TRANSFER_DIFFERENCE = [uint(m[0]-t[0])
                       for m, t in zip(MINT_AMOUNTS, TRANSFER_AMOUNTS)]
INVALID_AMOUNTS = uint_array([1, MAX_UINT256[0]+1, 1])
INVALID_IDS = uint_array([0, MAX_UINT256[0]+1, 1])

MAX_UINT_AMOUNTS = [uint(1), MAX_UINT256, uint(1)]

id_ERC165 = int('0x01ffc9a7', 16)
id_IERC1155 = int('0xd9b67a26', 16)
id_IERC1155_MetadataURI = int('0x0e89341c', 16)
id_mandatory_unsupported = int('0xffffffff', 16)
id_random = int('0xaabbccdd', 16)

SUPPORTED_INTERFACES = [id_ERC165, id_IERC1155, id_IERC1155_MetadataURI]
UNSUPPORTED_INTERFACES = [id_mandatory_unsupported, id_random]

DECIMALS = 18
INIT_SUPPLY = to_uint(1000000000000000000000000)
CAP = to_uint(1000000000000000000000000000000)
UINT_ONE = to_uint(1)
UINT_ZERO = to_uint(0)
NB_QUEST = 2

REWARDS_PER_BLOCK = to_uint(10)
START_BLOCK = 0
END_BLOCK = START_BLOCK + 10000

TOKEN_URI = [186294699441980128189380696103414374861828827125449954958229537633255900247,
             43198068668795004939573357158436613902855023868408433]


# Fixtures

@pytest.fixture(scope='module')
def event_loop():
    return asyncio.new_event_loop()


@pytest.fixture(scope='module')
def contract_defs():
    account_def = get_contract_def(account_path)
    erc1155_def = get_contract_def(erc1155_path)
    receiver_def = get_contract_def(receiver_path)
    ido_def = get_contract_def(ido_path)
    factory_def = get_contract_def(factory_path)
    zk_pad_token_def = get_contract_def('AstralyToken.cairo')
    zk_pad_stake_def = get_contract_def('AstralyStaking.cairo')
    task_def = get_contract_def('AstralyTask.cairo')
    return account_def, erc1155_def, receiver_def, ido_def, zk_pad_token_def, zk_pad_stake_def, factory_def, task_def


@pytest_asyncio.fixture(scope='module')
async def erc1155_init(contract_defs):
    account_def, erc1155_def, receiver_def, ido_def, zk_pad_token_def, zk_pad_stake_def, factory_def, task_def = contract_defs
    starknet = await Starknet.empty()
    await starknet.declare(contract_class=account_def)
    account1 = await starknet.deploy(
        contract_class=account_def,
        constructor_calldata=[mock_signer.public_key]
    )
    account2 = await starknet.deploy(
        contract_class=account_def,
        constructor_calldata=[mock_signer.public_key]
    )
    ido_class = await starknet.declare(contract_class=ido_def)
    ido = await starknet.deploy(contract_class=ido_def, constructor_calldata=[account1.contract_address])
    ido2 = await starknet.deploy(contract_class=ido_def, constructor_calldata=[account1.contract_address])
    await starknet.declare(contract_class=factory_def)
    factory = await starknet.deploy(contract_class=factory_def, constructor_calldata=[ido_class.class_hash, account1.contract_address])
    await starknet.declare(contract_class=task_def)
    task = await starknet.deploy(contract_class=task_def, constructor_calldata=[factory.contract_address])
    await starknet.declare(contract_class=erc1155_def)
    erc1155 = await starknet.deploy(
        contract_class=erc1155_def,
        constructor_calldata=[
            len(TOKEN_URI), *TOKEN_URI, account1.contract_address, factory.contract_address]
    )
    await starknet.declare(contract_class=receiver_def)
    receiver = await starknet.deploy(
        contract_class=receiver_def
    )
    await starknet.declare(contract_class=zk_pad_token_def)
    zk_pad_token = await starknet.deploy(
        contract_class=zk_pad_token_def,
        constructor_calldata=[
            str_to_felt("Astraly"),
            str_to_felt("ZKP"),
            DECIMALS,
            *INIT_SUPPLY,
            account1.contract_address,  # recipient
            account1.contract_address,  # owner
            *CAP,
        ],
    )
    rnd_nbr_gen_def = get_contract_def(rnd_nbr_gen_path)
    await starknet.declare(contract_class=rnd_nbr_gen_def)
    rnd_nbr_gen = await starknet.deploy(
        contract_class=rnd_nbr_gen_def,
        constructor_calldata=[1],  # seed
    )

    zk_pad_stake_class = await starknet.declare(contract_class=zk_pad_stake_def)
    zk_pad_stake_implementation = await starknet.deploy(contract_class=zk_pad_stake_def)

    proxy_def = get_contract_def('openzeppelin/upgrades/presets/Proxy.cairo')
    await starknet.declare(contract_class=proxy_def)
    zk_pad_stake_proxy = await starknet.deploy(contract_class=proxy_def,
                                               constructor_calldata=[zk_pad_stake_class.class_hash])
    await mock_signer.send_transaction(account1, zk_pad_stake_proxy.contract_address, "initializer", [
        str_to_felt("xAstraly"),
        str_to_felt("xZKP"),
        zk_pad_token.contract_address,
        account1.contract_address,
        *REWARDS_PER_BLOCK,
        START_BLOCK,
        END_BLOCK
    ])
    MERKLE_INFO = get_leaves(
        [account1.contract_address, receiver.contract_address], [NB_QUEST, NB_QUEST])

    await mock_signer.send_transaction(account1, factory.contract_address, "set_task_address", [task.contract_address])
    root = generate_merkle_root(list(map(lambda x: x[0], MERKLE_INFO)))
    await mock_signer.send_transaction(account1, factory.contract_address, "set_merkle_root", [root, 0])

    await mock_signer.send_transaction(account1, factory.contract_address, 'set_lottery_ticket_contract_address', [erc1155.contract_address])
    await mock_signer.send_transaction(account1, factory.contract_address, 'set_random_number_generator_address', [rnd_nbr_gen.contract_address])

    return (
        starknet.state,
        account1,
        account2,
        erc1155,
        receiver,
        ido,
        zk_pad_token,
        zk_pad_stake_proxy,
        factory,
        ido2
    )


@pytest.fixture
def erc1155_factory(contract_defs, erc1155_init):
    account_def, erc1155_def, receiver_def, ido_def, _, _, _, _ = contract_defs
    state, account1, account2, erc1155, receiver, ido, _, _, _, _ = erc1155_init
    _state = state.copy()
    account1 = cached_contract(_state, account_def, account1)
    account2 = cached_contract(_state, account_def, account2)
    erc1155 = cached_contract(_state, erc1155_def, erc1155)
    receiver = cached_contract(_state, receiver_def, receiver)
    ido = cached_contract(_state, ido_def, ido)
    return erc1155, account1, account2, receiver, ido


@pytest_asyncio.fixture(scope='module')
async def erc1155_minted_init(contract_defs, erc1155_init):
    account_def, erc1155_def, receiver_def, ido_def, _, _, factory_def, _ = contract_defs
    state, owner, account, erc1155, receiver, ido, _, _, factory, _ = erc1155_init
    _state = state.copy()
    owner = cached_contract(_state, account_def, owner)
    account = cached_contract(_state, account_def, account)
    erc1155 = cached_contract(_state, erc1155_def, erc1155)
    receiver = cached_contract(_state, receiver_def, receiver)
    ido = cached_contract(_state, ido_def, ido)
    factory = cached_contract(_state, factory_def, factory)
    await mock_signer.send_transaction(
        owner, erc1155.contract_address, 'mintBatch',
        [
            account.contract_address,  # to
            *uarr2cd(TOKEN_IDS),  # ids
            *uarr2cd(MINT_AMOUNTS),  # amounts
            0  # data
        ]
    )

    # Create mock IDO
    await mock_signer.send_transaction(owner, factory.contract_address, "create_ido", [owner.contract_address])

    return _state, erc1155, owner, account, receiver, ido


@pytest.fixture
def erc1155_minted_factory(contract_defs, erc1155_minted_init):
    account_def, erc1155_def, receiver_def, ido_def, _, _, _, _ = contract_defs
    state, erc1155, owner, account, receiver, ido = erc1155_minted_init
    _state = state.copy()
    owner = cached_contract(_state, account_def, owner)
    account = cached_contract(_state, account_def, account)
    erc1155 = cached_contract(_state, erc1155_def, erc1155)
    receiver = cached_contract(_state, receiver_def, receiver)
    ido = cached_contract(_state, ido_def, ido)

    return erc1155, owner, account, receiver, ido


@pytest_asyncio.fixture(scope='module')
async def full_init(contract_defs, erc1155_init):
    account_def, erc1155_def, receiver_def, ido_def, zk_pad_token_def, zk_pad_stake_def, factory_def, _ = contract_defs
    state, owner, account, erc1155, receiver, ido, zk_pad_token, zk_pad_stake, factory, ido2 = erc1155_init
    _state = state.copy()
    owner = cached_contract(_state, account_def, owner)
    account = cached_contract(_state, account_def, account)
    erc1155 = cached_contract(_state, erc1155_def, erc1155)
    receiver = cached_contract(_state, receiver_def, receiver)
    ido = cached_contract(_state, ido_def, ido)
    ido2 = cached_contract(_state, ido_def, ido2)
    factory = cached_contract(_state, factory_def, factory)
    zk_pad_token = cached_contract(_state, zk_pad_token_def, zk_pad_token)
    zk_pad_stake = cached_contract(_state, zk_pad_stake_def, zk_pad_stake)
    await mock_signer.send_transaction(
        owner, erc1155.contract_address, 'mintBatch',
        [
            owner.contract_address,  # to
            *uarr2cd(TOKEN_IDS),  # ids
            *uarr2cd(MINT_AMOUNTS),  # amounts
            0  # data
        ]
    )
    # Deposit ZKP in the vault
    # max approve
    await mock_signer.send_transaction(
        owner,
        zk_pad_token.contract_address,
        "approve",
        [zk_pad_stake.contract_address, *MAX_UINT256],
    )

    amount = to_uint(10000000000000000000000)  # 10000

    # deposit asset tokens to the vault, get shares
    tx = await mock_signer.send_transaction(
        owner,
        zk_pad_stake.contract_address,
        "deposit",
        [*amount, owner.contract_address],
    )

    # set xzkp address
    await mock_signer.send_transaction(
        owner,
        erc1155.contract_address,
        "set_xzkp_contract_address",
        [zk_pad_stake.contract_address],
    )

    # create 2 mock IDOs
    await mock_signer.send_transaction(owner, factory.contract_address, "create_ido", [owner.contract_address])
    await mock_signer.send_transaction(owner, factory.contract_address, "create_ido", [owner.contract_address])
    MERKLE_INFO = get_leaves(
        [owner.contract_address, receiver.contract_address], [NB_QUEST, NB_QUEST])

    root = generate_merkle_root(list(map(lambda x: x[0], MERKLE_INFO)))
    await mock_signer.send_transaction(owner, factory.contract_address, "set_merkle_root", [root, 0])
    # print("ROOT", root)
    # print("INFO", MERKLE_INFO)

    return _state, erc1155, owner, account, receiver, ido, zk_pad_token, zk_pad_stake


@pytest.fixture
def full_factory(contract_defs, full_init):
    account_def, erc1155_def, receiver_def, ido_def, zk_pad_token_def, zk_pad_stake_def, _, _ = contract_defs
    state, erc1155, owner, account, receiver, ido, zk_pad_token, zk_pad_stake = full_init
    _state = state.copy()
    owner = cached_contract(_state, account_def, owner)
    account = cached_contract(_state, account_def, account)
    erc1155 = cached_contract(_state, erc1155_def, erc1155)
    receiver = cached_contract(_state, receiver_def, receiver)
    ido = cached_contract(_state, ido_def, ido)
    zk_pad_token = cached_contract(_state, zk_pad_token_def, zk_pad_token)
    zk_pad_stake = cached_contract(_state, zk_pad_stake_def, zk_pad_stake)
    return erc1155, owner, account, receiver, ido, zk_pad_token, zk_pad_stake

# Tests

#
# Constructor
#


@pytest.mark.asyncio
async def test_constructor(erc1155_factory):
    erc1155, _, _, _, _ = erc1155_factory

    execution_info = await erc1155.uri(0).invoke()
    print(execution_info.result)
    assert execution_info.result.uri == TOKEN_URI

#
# ERC165
#


@pytest.mark.asyncio
async def test_supports_interface(erc1155_factory):
    erc1155, _, _, _, _ = erc1155_factory

    for supported_id in SUPPORTED_INTERFACES:
        execution_info = await erc1155.supportsInterface(
            supported_id
        ).invoke()
        assert execution_info.result.is_supported == TRUE

    for unsupported_id in UNSUPPORTED_INTERFACES:
        execution_info = await erc1155.supportsInterface(
            unsupported_id
        ).invoke()
        assert execution_info.result.is_supported == FALSE

#
# Set/Get approval
#


@pytest.mark.asyncio
async def test_set_approval_for_all(erc1155_factory):
    erc1155, account, _, _, _ = erc1155_factory

    operator = ACCOUNT
    approval = TRUE

    await mock_signer.send_transaction(
        account, erc1155.contract_address, 'setApprovalForAll',
        [operator, approval]
    )

    execution_info = await erc1155.isApprovedForAll(
        account.contract_address,
        operator
    ).invoke()

    assert execution_info.result.is_approved == approval

    operator = ACCOUNT
    approval = FALSE

    await mock_signer.send_transaction(
        account, erc1155.contract_address, 'setApprovalForAll',
        [operator, approval]
    )

    execution_info = await erc1155.isApprovedForAll(
        account.contract_address,
        operator
    ).invoke()

    assert execution_info.result.is_approved == approval


@pytest.mark.asyncio
async def test_set_approval_for_all_non_boolean(erc1155_factory):
    erc1155, account, _, _, _ = erc1155_factory

    operator = ACCOUNT
    approval = NON_BOOLEAN

    await assert_revert(mock_signer.send_transaction(
        account, erc1155.contract_address, 'setApprovalForAll',
        [operator, approval]
    ))

#
# Balance getters
#


@pytest.mark.asyncio
async def test_balance_of(erc1155_minted_factory):
    erc1155, _, account, _, _ = erc1155_minted_factory
    user = account.contract_address
    execution_info = await erc1155.balanceOf(user, TOKEN_IDS[0]).invoke()
    assert execution_info.result.balance == MINT_AMOUNTS[0]


@pytest.mark.asyncio
async def test_balance_of_zero_address(erc1155_factory):
    erc1155, _, _, _, _ = erc1155_factory

    await assert_revert(
        erc1155.balanceOf(ZERO_ADDRESS, TOKEN_ID).invoke(),
        "ERC1155: balance query for the zero address")


@pytest.mark.asyncio
async def test_balance_of_batch(erc1155_minted_factory):
    erc1155, _, account, _, _ = erc1155_minted_factory
    accounts = [account.contract_address]*3
    execution_info = await erc1155.balanceOfBatch(accounts, TOKEN_IDS).invoke()
    assert execution_info.result.balances == MINT_AMOUNTS


@pytest.mark.asyncio
async def test_balance_of_batch_zero_address(erc1155_factory):
    erc1155, _, _, _, _ = erc1155_factory
    accounts = [ACCOUNT, ZERO_ADDRESS, ACCOUNT]

    await assert_revert(
        erc1155.balanceOfBatch(accounts, TOKEN_IDS).invoke(),
        "ERC1155: balance query for the zero address")


@pytest.mark.asyncio
async def test_balance_of_batch_uneven_arrays(erc1155_factory):
    erc1155, _, _, _, _ = erc1155_factory

    accounts = ACCOUNTS
    ids = TOKEN_IDS

    # len(accounts) != len(ids)
    await assert_revert(
        erc1155.balanceOfBatch(accounts[:2], ids).invoke(),
        "ERC1155: accounts and ids length mismatch")
    await assert_revert(
        erc1155.balanceOfBatch(accounts, ids[:2]).invoke(),
        "ERC1155: accounts and ids length mismatch")


#
# Minting
#

@pytest.mark.asyncio
async def test_mint(erc1155_factory):
    erc1155, owner, account, _, _ = erc1155_factory
    recipient = account.contract_address
    token_id = TOKEN_ID
    amount = MINT_AMOUNT

    await mock_signer.send_transaction(
        owner, erc1155.contract_address, 'mint',
        [
            recipient,
            *token_id,
            *amount,
            0  # data
        ]
    )

    execution_info = await erc1155.balanceOf(recipient, token_id).invoke()
    assert execution_info.result.balance == amount


@pytest.mark.asyncio
async def test_mint_to_zero_address(erc1155_factory):
    erc1155, owner, account, _, _ = erc1155_factory

    recipient = ZERO_ADDRESS
    token_id = TOKEN_ID
    amount = MINT_AMOUNT

    # minting to 0 address should fail
    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mint',
            [
                recipient,  # to
                *token_id,
                *amount,
                0  # data
            ]
        ),
        "ERC1155: mint to the zero address"
    )


@pytest.mark.asyncio
async def test_mint_overflow(erc1155_factory):
    erc1155, owner, account, _, _ = erc1155_factory

    recipient = account.contract_address
    token_id = TOKEN_ID

    # Bring recipient's balance to max possible, should pass (recipient's balance is 0)
    amount = MAX_UINT256
    await mock_signer.send_transaction(
        owner, erc1155.contract_address, 'mint',
        [
            recipient,  # to
            *token_id,
            *amount,
            0  # data
        ]
    )

    # Issuing recipient any more should revert due to overflow
    amount = uint(1)
    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mint',
            [
                recipient,  # to
                *token_id,
                *amount,
                0  # data
            ]
        ),
        "SafeUint256: addition overflow"
    )

    # upon rejection, there should be MAX balance
    execution_info = await erc1155.balanceOf(recipient, token_id).invoke()
    assert execution_info.result.balance == MAX_UINT256


@pytest.mark.asyncio
async def test_mint_invalid_uint(erc1155_factory):
    erc1155, owner, account, _, _ = erc1155_factory

    recipient = account.contract_address
    token_id = TOKEN_ID
    invalid_id = INVALID_UINT
    amount = MINT_AMOUNT
    invalid_amount = INVALID_UINT

    # issuing an invalid uint256 (i.e. either the low or high felts >= 2**128) should revert
    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mint',
            [
                recipient,  # to
                *token_id,
                *invalid_amount,
                0  # data
            ]
        ),
        "ERC1155: invalid uint256 in calldata"
    )
    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mint',
            [
                recipient,  # to
                *invalid_id,
                *amount,
                0  # data
            ]
        ),
        "ERC1155: invalid uint256 in calldata"
    )

    # balance should remain 0 <- redundant
    # execution_info = await erc1155.balanceOf(recipient,token_id).invoke()
    # assert execution_info.result.balance == uint(0)

#
# Burning
#


@pytest.mark.asyncio
async def test_burn(erc1155_minted_factory):
    erc1155, _, account, _, _ = erc1155_minted_factory

    subject = account.contract_address
    token_id = TOKEN_ID
    burn_amount = BURN_AMOUNT

    await mock_signer.send_transaction(
        account, erc1155.contract_address, 'burn',
        [subject, *token_id, *burn_amount]
    )

    execution_info = await erc1155.balanceOf(subject, token_id).invoke()
    assert execution_info.result.balance == sub_uint(MINT_AMOUNT, burn_amount)


@pytest.mark.asyncio
async def test_burn_insufficient_balance(erc1155_factory):
    erc1155, _, account, _, _ = erc1155_factory

    subject = account.contract_address
    token_id = TOKEN_ID
    burn_amount = BURN_AMOUNT

    # Burn non-0 amount w/ 0 balance
    await assert_revert(
        mock_signer.send_transaction(
            account, erc1155.contract_address, 'burn',
            [subject, *token_id, *burn_amount]
        ))


@pytest.mark.asyncio
async def test_burn_with_quest(full_factory):
    erc1155, owner, _, receiver, ido, zk_pad_token, zk_pad_stake = full_factory
    subject = owner.contract_address
    token_id = TOKEN_ID
    burn_amount = BURN_AMOUNT
    MERKLE_INFO = get_leaves(
        [owner.contract_address, receiver.contract_address], [NB_QUEST, NB_QUEST])
    leaves = list(map(lambda x: x[0], MERKLE_INFO))
    # print("LEAVES", leaves)
    proof = generate_merkle_proof(leaves, 0)
    verif = verify_merkle_proof(pedersen_hash(subject, NB_QUEST), proof)
    # print("PROOF", proof)
    print("valid", verif)

    await mock_signer.send_transaction(
        owner, erc1155.contract_address, 'burn_with_quest',
        [subject, *token_id, *burn_amount, NB_QUEST, len(proof), *proof])


# batch minting


@pytest.mark.asyncio
async def test_mint_batch(erc1155_factory):
    erc1155, owner, account, _, _ = erc1155_factory

    recipient = account.contract_address
    token_ids = TOKEN_IDS
    amounts = MINT_AMOUNTS

    # mint amount[i] of token_id[i] to recipient
    await mock_signer.send_transaction(
        owner, erc1155.contract_address, 'mintBatch',
        [recipient, *uarr2cd(token_ids), *uarr2cd(amounts), 0])

    execution_info = await erc1155.balanceOfBatch([recipient]*3, token_ids).invoke()
    assert execution_info.result.balances == amounts


@pytest.mark.asyncio
async def test_mint_batch_to_zero_address(erc1155_factory):
    erc1155, owner, _, _, _ = erc1155_factory

    recipient = ZERO_ADDRESS
    token_ids = TOKEN_IDS
    amounts = MINT_AMOUNTS

    # mint amount[i] of token_id[i] to recipient
    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mintBatch',
            [recipient, *uarr2cd(token_ids), *uarr2cd(amounts), 0]),
        "ERC1155: mint to the zero address"
    )


@pytest.mark.asyncio
async def test_mint_batch_overflow(erc1155_factory):
    erc1155, owner, account, _, _ = erc1155_factory

    recipient = account.contract_address
    token_ids = TOKEN_IDS
    amounts = MAX_UINT_AMOUNTS

    # Bring 1 recipient's balance to max possible, should pass (recipient's balance is 0)
    await mock_signer.send_transaction(
        owner, erc1155.contract_address, 'mintBatch',
        [recipient, *uarr2cd(token_ids), *uarr2cd(amounts), 0])

    # Issuing recipient any more on just 1 token_id should revert due to overflow
    amounts = uint_array([0, 1, 0])
    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mintBatch',
            [recipient, *uarr2cd(token_ids), *uarr2cd(amounts), 0]),
        "SafeUint256: addition overflow"
    )


@pytest.mark.asyncio
async def test_mint_batch_invalid_uint(erc1155_factory):
    erc1155, owner, _, _, _ = erc1155_factory

    recipient = ACCOUNT
    token_ids = TOKEN_IDS
    invalid_ids = INVALID_IDS
    amounts = MINT_AMOUNTS
    invalid_amounts = INVALID_AMOUNTS

    # attempt passing an invalid amount in batch
    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mintBatch',
            [recipient, *uarr2cd(token_ids), *uarr2cd(invalid_amounts), 0]),
        "ERC1155: invalid uint256 in calldata"
    )

    # attempt passing an invalid id in batch
    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mintBatch',
            [recipient, *uarr2cd(invalid_ids), *uarr2cd(amounts), 0]),
        "ERC1155: invalid uint256 in calldata"
    )


@pytest.mark.asyncio
async def test_mint_batch_uneven_arrays(erc1155_factory):
    erc1155, owner, _, _, _ = erc1155_factory

    recipient = ACCOUNT
    token_ids = TOKEN_IDS
    amounts = MINT_AMOUNTS

    # uneven token_ids vs amounts
    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mintBatch',
            [recipient, *uarr2cd(token_ids), *uarr2cd(amounts[:2]), 0]),
        "ERC1155: ids and amounts length mismatch"
    )

    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mintBatch',
            [recipient, *uarr2cd(token_ids[:2]), *uarr2cd(amounts), 0]),
        "ERC1155: ids and amounts length mismatch"
    )

#
# batch burning
#


# @pytest.mark.asyncio
# async def test_burn_batch(erc1155_minted_factory):
#     erc1155, _, account, _, _ = erc1155_minted_factory

#     burner = account.contract_address
#     token_ids = TOKEN_IDS
#     burn_amounts = BURN_AMOUNTS

#     await mock_signer.send_transaction(
#         account, erc1155.contract_address, 'burnBatch',
#         [burner, *uarr2cd(token_ids), *uarr2cd(burn_amounts)])

#     execution_info = await erc1155.balanceOfBatch([burner]*3, token_ids).invoke()
#     assert execution_info.result.balances == [
#         sub_uint(m, b) for m, b in zip(MINT_AMOUNTS, burn_amounts)]


# @pytest.mark.asyncio
# async def test_burn_batch_from_zero_address(erc1155_minted_factory):
#     erc1155, _, _, _, _ = erc1155_minted_factory
#     burner = ZERO_ADDRESS
#     token_ids = TOKEN_IDS
#     amounts = [uint(0)]*3

#     # Attempt to burn nothing (since cannot mint non_zero balance to burn)
#     # call from 0 address
#     await assert_revert(
#         erc1155.burnBatch(burner, token_ids, amounts).invoke()  # ,
#         # "ERC1155: burn from the zero address"
#     )


# @pytest.mark.asyncio
# async def test_burn_batch_insufficent_balance(erc1155_minted_factory):
#     erc1155, _, account, _, _ = erc1155_minted_factory

#     burner = account.contract_address
#     token_ids = TOKEN_IDS
#     amounts = [MINT_AMOUNTS[0], add_uint(
#         MINT_AMOUNTS[1], uint(1)), MINT_AMOUNTS[2]]

#     await assert_revert(
#         mock_signer.send_transaction(
#             account, erc1155.contract_address, 'burnBatch',
#             [burner, *uarr2cd(token_ids), *uarr2cd(amounts)]),
#         "ERC1155: burn amount exceeds balance"
#     )

#     # todo nonzero balance


# @pytest.mark.asyncio
# async def test_burn_batch_invalid_uint(erc1155_factory):
#     erc1155, owner, account, _, _ = erc1155_factory
#     burner = account.contract_address
#     token_ids = TOKEN_IDS
#     mint_amounts = MAX_UINT_AMOUNTS
#     burn_amounts = INVALID_AMOUNTS

#     # mint max possible to avoid insufficient balance
#     await mock_signer.send_transaction(
#         owner, erc1155.contract_address, 'mintBatch',
#         [burner, *uarr2cd(token_ids), *uarr2cd(mint_amounts), 0])

#     # attempt passing an invalid uint in batch
#     await assert_revert(
#         mock_signer.send_transaction(
#             account, erc1155.contract_address, 'burnBatch',
#             [burner, *uarr2cd(token_ids), *uarr2cd(burn_amounts)]),
#         "ERC1155: invalid uint in calldata"
#     )


# @pytest.mark.asyncio
# async def test_burn_batch_uneven_arrays(erc1155_minted_factory):
#     erc1155, _, account, _, _ = erc1155_minted_factory

#     burner = account.contract_address
#     amounts = BURN_AMOUNTS
#     token_ids = TOKEN_IDS

#     # uneven token_ids vs amounts
#     await assert_revert(
#         mock_signer.send_transaction(
#             account, erc1155.contract_address, 'burnBatch',
#             [burner, *uarr2cd(token_ids), *uarr2cd(amounts[:2])]),
#         "ERC1155: ids and amounts length mismatch"
#     )
#     await assert_revert(
#         mock_signer.send_transaction(
#             account, erc1155.contract_address, 'burnBatch',
#             [burner, *uarr2cd(token_ids[:2]), *uarr2cd(amounts)]),
#         "ERC1155: ids and amounts length mismatch"
#     )

#
# Transfer
#


@pytest.mark.asyncio
async def test_safe_transfer_from(erc1155_minted_factory):
    erc1155, account1, account2, _, _ = erc1155_minted_factory

    sender = account2.contract_address
    recipient = account1.contract_address
    token_id = TOKEN_ID
    transfer_amount = TRANSFER_AMOUNT

    await mock_signer.send_transaction(
        account2, erc1155.contract_address, 'safeTransferFrom',
        [sender, recipient, *token_id, *transfer_amount, 0])

    execution_info = await erc1155.balanceOf(sender, token_id).invoke()
    assert execution_info.result.balance == sub_uint(
        MINT_AMOUNTS[0], transfer_amount)
    execution_info = await erc1155.balanceOf(recipient, token_id).invoke()
    assert execution_info.result.balance == transfer_amount


@pytest.mark.asyncio
async def test_safe_transfer_from_approved(erc1155_minted_factory):
    erc1155, account1, account2, _, _ = erc1155_minted_factory

    operator = account1.contract_address
    sender = account2.contract_address
    recipient = account1.contract_address
    token_id = TOKEN_ID
    transfer_amount = TRANSFER_AMOUNT
    approval = TRUE

    # account2 approves account
    await mock_signer.send_transaction(
        account2, erc1155.contract_address, 'setApprovalForAll',
        [operator, approval])

    # account sends transaction
    await mock_signer.send_transaction(
        account1, erc1155.contract_address, 'safeTransferFrom',
        [sender, recipient, *token_id, *transfer_amount, 0])

    execution_info = await erc1155.balanceOf(sender, token_id).invoke()
    assert execution_info.result.balance == sub_uint(
        MINT_AMOUNTS[0], transfer_amount)
    execution_info = await erc1155.balanceOf(recipient, token_id).invoke()
    assert execution_info.result.balance == transfer_amount


@pytest.mark.asyncio
async def test_safe_transfer_from_invalid_uint(erc1155_factory):
    erc1155, owner, account, _, _ = erc1155_factory

    sender = account.contract_address
    recipient = owner.contract_address
    token_id = TOKEN_ID
    invalid_id = INVALID_UINT
    mint_amount = MAX_UINT256
    transfer_amount = uint(0)
    invalid_amount = INVALID_UINT

    # mint max uint to avoid possible insufficient balance error
    await mock_signer.send_transaction(
        owner, erc1155.contract_address, 'mint',
        [sender, *token_id, *mint_amount, 0])

    await assert_revert(
        mock_signer.send_transaction(
            account, erc1155.contract_address, 'safeTransferFrom',
            [sender, recipient, *token_id, *invalid_amount, 0]),
        "ERC1155: invalid uint in calldata"
    )
    # transfer 0 amount
    await assert_revert(
        mock_signer.send_transaction(
            account, erc1155.contract_address, 'safeTransferFrom',
            [sender, recipient, *invalid_id, *transfer_amount, 0]),
        "ERC1155: invalid uint in calldata"
    )


@pytest.mark.asyncio
async def test_safe_transfer_from_insufficient_balance(erc1155_minted_factory):
    erc1155, account, account2, _, _ = erc1155_minted_factory

    sender = account2.contract_address
    recipient = account.contract_address
    token_id = TOKEN_ID
    transfer_amount = add_uint(MINT_AMOUNTS[0], uint(1))

    await assert_revert(
        mock_signer.send_transaction(
            account2, erc1155.contract_address, 'safeTransferFrom',
            [sender, recipient, *token_id, *transfer_amount, 0]),
        "ERC1155: insufficient balance for transfer"
    )


@pytest.mark.asyncio
async def test_safe_transfer_from_unapproved(erc1155_minted_factory):
    erc1155, account1, account2, _, _ = erc1155_minted_factory

    sender = account2.contract_address
    recipient = account1.contract_address
    token_id = TOKEN_ID
    transfer_amount = TRANSFER_AMOUNT

    # unapproved account sends transaction, should fail
    await assert_revert(mock_signer.send_transaction(
        account1, erc1155.contract_address, 'safeTransferFrom',
        [sender, recipient, *token_id, *transfer_amount, 0]))


@pytest.mark.asyncio
async def test_safe_transfer_from_to_zero_address(erc1155_minted_factory):
    erc1155, _, account, _, _ = erc1155_minted_factory

    sender = account.contract_address
    recipient = ZERO_ADDRESS
    token_id = TOKEN_ID
    transfer_amount = TRANSFER_AMOUNT

    await assert_revert(mock_signer.send_transaction(
        account, erc1155.contract_address, 'safeTransferFrom',
        [sender, recipient, *token_id, *transfer_amount, 0]))


@pytest.mark.asyncio
async def test_safe_transfer_from_overflow(erc1155_minted_factory):
    erc1155, owner, account, _, _ = erc1155_minted_factory

    sender = account.contract_address
    recipient = owner.contract_address
    token_id = TOKEN_ID
    mint_amount = MINT_AMOUNT
    transfer_amount = TRANSFER_AMOUNT
    max_amount = MAX_UINT256

    # Bring recipient's balance to max possible, should pass (recipient's balance is 0)
    await mock_signer.send_transaction(
        owner, erc1155.contract_address, 'mint',
        [recipient, *token_id, *max_amount, 0])

    # Issuing recipient any more should revert due to overflow
    await assert_revert(mock_signer.send_transaction(
        account, erc1155.contract_address, 'safeTransferFrom',
        [sender, recipient, *token_id, *transfer_amount, 0]
    ))


# Batch Transfer
@pytest.mark.asyncio
async def test_safe_batch_transfer_from(erc1155_minted_factory):
    erc1155, account1, account2, _, _ = erc1155_minted_factory
    sender = account2.contract_address
    recipient = account1.contract_address
    token_ids = TOKEN_IDS
    transfer_amounts = TRANSFER_AMOUNTS
    difference = TRANSFER_DIFFERENCE

    execution_info = await mock_signer.send_transaction(
        account2, erc1155.contract_address, 'safeBatchTransferFrom',
        [sender, recipient, *uarr2cd(token_ids), *uarr2cd(transfer_amounts), 0])

    execution_info = await erc1155.balanceOfBatch([sender]*3+[recipient]*3, token_ids*2).invoke()
    assert execution_info.result.balances[:3] == difference
    assert execution_info.result.balances[3:] == transfer_amounts


@pytest.mark.asyncio
async def test_safe_batch_transfer_from_approved(erc1155_minted_factory):
    erc1155, account1, account2, _, _ = erc1155_minted_factory

    sender = account2.contract_address
    operator = account1.contract_address
    recipient = account1.contract_address
    token_ids = TOKEN_IDS
    transfer_amounts = TRANSFER_AMOUNTS
    difference = TRANSFER_DIFFERENCE
    approval = TRUE

    # account approves account2
    await mock_signer.send_transaction(
        account2, erc1155.contract_address, 'setApprovalForAll',
        [operator, approval])

    await mock_signer.send_transaction(
        account1, erc1155.contract_address, 'safeBatchTransferFrom',
        [sender, recipient, *uarr2cd(token_ids), *uarr2cd(transfer_amounts), 0])

    execution_info = await erc1155.balanceOfBatch([sender]*3+[recipient]*3, token_ids*2).invoke()
    assert execution_info.result.balances[:3] == difference
    assert execution_info.result.balances[3:] == transfer_amounts


@pytest.mark.asyncio
async def test_safe_batch_transfer_from_invalid_uint(erc1155_factory):
    erc1155, owner, account, _, _ = erc1155_factory

    sender = account.contract_address
    recipient = owner.contract_address
    token_ids = TOKEN_IDS
    invalid_ids = INVALID_IDS
    mint_amounts = MAX_UINT_AMOUNTS
    invalid_amounts = INVALID_AMOUNTS
    transfer_amounts = TRANSFER_AMOUNTS

    # mint amount[i] of token_id[i] to sender
    await mock_signer.send_transaction(
        owner, erc1155.contract_address, 'mintBatch',
        [sender, *uarr2cd(token_ids), *uarr2cd(mint_amounts), 0])

    await assert_revert(mock_signer.send_transaction(
        account, erc1155.contract_address, 'safeBatchTransferFrom',
        [sender, recipient, *uarr2cd(token_ids), *uarr2cd(invalid_amounts), 0]))
    # attempt transfer 0 due to insufficient balance error
    await assert_revert(mock_signer.send_transaction(
        account, erc1155.contract_address, 'safeBatchTransferFrom',
        [sender, recipient, *uarr2cd(invalid_ids), *uarr2cd(transfer_amounts), 0]))


@pytest.mark.asyncio
async def test_safe_batch_transfer_from_insufficient_balance(erc1155_minted_factory):
    erc1155, account1, account2, _, _ = erc1155_minted_factory
    sender = account2.contract_address
    recipient = account1.contract_address
    token_ids = TOKEN_IDS
    transfer_amounts = [MINT_AMOUNTS[0], add_uint(
        MINT_AMOUNTS[1], uint(1)), MINT_AMOUNTS[2]]

    await assert_revert(mock_signer.send_transaction(
        account2, erc1155.contract_address, 'safeBatchTransferFrom',
        [sender, recipient, *uarr2cd(token_ids), *uarr2cd(transfer_amounts), 0]))


@pytest.mark.asyncio
async def test_safe_batch_transfer_from_unapproved(erc1155_minted_factory):
    erc1155, account1, account2, _, _ = erc1155_minted_factory

    sender = account2.contract_address
    operator = account1.contract_address
    recipient = account1.contract_address
    token_ids = TOKEN_IDS
    transfer_amounts = TRANSFER_AMOUNTS

    await assert_revert(mock_signer.send_transaction(
        account1, erc1155.contract_address, 'safeBatchTransferFrom',
        [sender, recipient, *uarr2cd(token_ids), *uarr2cd(transfer_amounts), 0]))


@pytest.mark.asyncio
async def test_safe_batch_transfer_from_to_zero_address(erc1155_minted_factory):
    erc1155, _, account, _, _ = erc1155_minted_factory

    sender = account.contract_address
    recipient = ZERO_ADDRESS
    token_ids = TOKEN_IDS
    mint_amounts = MINT_AMOUNTS
    transfer_amounts = TRANSFER_AMOUNTS

    await assert_revert(mock_signer.send_transaction(
        account,
        erc1155.contract_address,
        'safeBatchTransferFrom', [sender, recipient, *uarr2cd(token_ids), *uarr2cd(transfer_amounts), 0]))


@pytest.mark.asyncio
async def test_safe_batch_transfer_from_uneven_arrays(erc1155_minted_factory):
    erc1155, account1, account2, _, _ = erc1155_minted_factory

    sender = account2.contract_address
    recipient = account1.contract_address
    transfer_amounts = TRANSFER_AMOUNTS
    token_ids = TOKEN_IDS

    # uneven token_ids vs amounts
    await assert_revert(mock_signer.send_transaction(
        account2, erc1155.contract_address, 'safeBatchTransferFrom',
        [sender, recipient, *uarr2cd(token_ids),
         *uarr2cd(transfer_amounts[:2]), 0]
    ))
    await assert_revert(mock_signer.send_transaction(
        account2, erc1155.contract_address, 'safeBatchTransferFrom',
        [sender, recipient, *uarr2cd(token_ids[:2]),
         *uarr2cd(transfer_amounts), 0]
    ))


@pytest.mark.asyncio
async def test_safe_batch_transfer_from_overflow(erc1155_minted_factory):
    erc1155, account1, account2, _, _ = erc1155_minted_factory

    sender = account2.contract_address
    recipient = account1.contract_address
    token_ids = TOKEN_IDS
    max_amounts = MAX_UINT_AMOUNTS
    transfer_amounts = uint_array([0, 1, 0])

    # Bring 1 recipient's balance to max possible, should pass (recipient's balance is 0)
    await mock_signer.send_transaction(
        account1, erc1155.contract_address, 'mintBatch',
        [recipient, *uarr2cd(token_ids), *uarr2cd(max_amounts), 0]
    )

    # Issuing recipient any more on just 1 token_id should revert due to overflow
    await assert_revert(mock_signer.send_transaction(
        account2, erc1155.contract_address, 'safeBatchTransferFrom',
        [sender, recipient, *uarr2cd(token_ids), *uarr2cd(transfer_amounts), 0]
    ))

#
# Unsafe recipients
#


@pytest.mark.asyncio
async def test_safe_transfer_from_to_uninstantiated_contract(erc1155_minted_factory):
    erc1155, _, account, _, _ = erc1155_minted_factory

    sender = account.contract_address
    recipient = 123
    token_id = TOKEN_ID
    transfer_amount = TRANSFER_AMOUNT

    await assert_revert(mock_signer.send_transaction(
        account, erc1155.contract_address, 'safeTransferFrom',
        [sender, recipient, *token_id, *transfer_amount, 0]))


@pytest.mark.asyncio
async def test_safe_transfer_from_to_unsafe_contract(erc1155_minted_factory):
    erc1155, _, account, _, _ = erc1155_minted_factory

    sender = account.contract_address
    recipient = erc1155.contract_address
    token_id = TOKEN_ID
    transfer_amount = TRANSFER_AMOUNT

    await assert_revert(mock_signer.send_transaction(
        account, erc1155.contract_address, 'safeTransferFrom',
        [sender, recipient, *token_id, *transfer_amount, 0]),
        "ERC1155: transfer to non ERC1155Receiver implementer")


@pytest.mark.asyncio
async def test_safe_transfer_from_receiver(erc1155_minted_factory):
    erc1155, _, account, receiver, _ = erc1155_minted_factory
    # mock ERC1155_receiver accepts iff data = []

    sender = account.contract_address
    recipient = receiver.contract_address
    token_id = TOKEN_ID
    transfer_amount = TRANSFER_AMOUNT
    data_cd = [0]
    await mock_signer.send_transaction(
        account, erc1155.contract_address, 'safeTransferFrom',
        [sender, recipient, *token_id, *transfer_amount, *data_cd])


@pytest.mark.asyncio
async def test_safe_transfer_from_receiver_rejection(erc1155_minted_factory):
    erc1155, _, account, receiver, _ = erc1155_minted_factory
    # mock ERC1155_receiver accepts iff data = []

    sender = account.contract_address
    recipient = receiver.contract_address
    token_id = TOKEN_ID
    transfer_amount = TRANSFER_AMOUNT
    data_cd = [1, 0]
    # data = [0], mock receiver should reject
    await assert_revert(mock_signer.send_transaction(
        account, erc1155.contract_address, 'safeTransferFrom',
        [sender, recipient, *token_id, *transfer_amount, *data_cd]),
        "ERC1155: ERC1155Receiver rejected tokens"
    )


@pytest.mark.asyncio
async def test_mint_to_unsafe_contract(erc1155_factory):
    erc1155, owner, account, _, _ = erc1155_factory

    recipient = erc1155.contract_address
    token_id = TOKEN_ID
    amount = MINT_AMOUNT

    # minting to 0 address should fail
    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mint',
            [
                recipient,  # to
                *token_id,
                *amount,
                0  # data
            ]
        ),
        "ERC1155: transfer to non ERC1155Receiver implementer"
    )


@pytest.mark.asyncio
async def test_mint_receiver_rejection(erc1155_factory):
    erc1155, owner, _, receiver, _ = erc1155_factory

    recipient = receiver.contract_address
    token_id = TOKEN_ID
    amount = MINT_AMOUNT

    # minting to 0 address should fail
    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mint',
            [
                recipient,  # to
                *token_id,
                *amount,
                1, 0  # data
            ]
        ),
        "ERC1155: ERC1155Receiver rejected tokens"
    )


@pytest.mark.asyncio
async def test_mint_receiver(erc1155_factory):
    erc1155, owner, _, receiver, _ = erc1155_factory
    recipient = receiver.contract_address
    token_id = TOKEN_ID
    amount = MINT_AMOUNT

    # minting to 0 address should fail
    await mock_signer.send_transaction(
        owner, erc1155.contract_address, 'mint',
        [
            recipient,  # to
            *token_id,
            *amount,
            0  # data
        ]
    )


@pytest.mark.asyncio
async def test_mint_batch_to_unsafe_contract(erc1155_factory):
    erc1155, owner, _, _, _ = erc1155_factory

    recipient = erc1155.contract_address
    token_ids = TOKEN_IDS
    amounts = MINT_AMOUNTS

    # mint amount[i] of token_id[i] to recipient
    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mintBatch',
            [recipient, *uarr2cd(token_ids), *uarr2cd(amounts), 0]),
        "ERC1155: transfer to non ERC1155Receiver implementer"
    )


@pytest.mark.asyncio
async def test_mint_batch_receiver(erc1155_factory):
    erc1155, owner, _, _, _ = erc1155_factory

    recipient = erc1155.contract_address
    token_ids = TOKEN_IDS
    amounts = MINT_AMOUNTS

    # mint amount[i] of token_id[i] to recipient
    await assert_revert(
        mock_signer.send_transaction(
            owner, erc1155.contract_address, 'mintBatch',
            [recipient, *uarr2cd(token_ids), *uarr2cd(amounts), 0]),
        "ERC1155: transfer to non ERC1155Receiver implementer"
    )


@pytest.mark.asyncio
async def test_safe_batch_transfer_from_to_unsafe_contract(erc1155_minted_factory):
    erc1155, _, account, _, _ = erc1155_minted_factory

    sender = account.contract_address
    recipient = erc1155.contract_address
    token_ids = TOKEN_IDS
    mint_amounts = MINT_AMOUNTS
    transfer_amounts = TRANSFER_AMOUNTS

    await assert_revert(mock_signer.send_transaction(
        account, erc1155.contract_address, 'safeBatchTransferFrom',
        [sender, recipient, *uarr2cd(token_ids), *uarr2cd(transfer_amounts), 0]),
        "ERC1155: transfer to non ERC1155Receiver implementer")


# @pytest.mark.asyncio
# async def test_mint_expired(erc1155_factory):
#     """Should revert when owner tries to mint after the ido launch (end of Round 0)"""
#     erc1155, owner, _, receiver, ido = erc1155_factory

#     recipient = receiver.contract_address
#     token_id = TOKEN_ID
#     amount = MINT_AMOUNT

#     # Update ido_launch_date to be in the past
#     await mock_signer.send_transaction(owner, ido.contract_address, 'set_ido_launch_date', [])

#     await assert_revert(mock_signer.send_transaction(
#         owner, erc1155.contract_address, 'mint',
#         [
#             recipient,  # to
#             *token_id,
#             *amount,
#             0  # data
#         ]
#     ), "AstralyLotteryToken::Standby Phase is over")


#
# claimLotteryTickets()
#

@pytest.mark.asyncio
async def test_claim_success(full_factory):
    erc1155, owner, _, receiver, ido, zk_pad_token, zk_pad_stake = full_factory

    IDO_ID = to_uint(0)
    user = owner.contract_address

    # Checks user has no tickets (only minted ones)
    execution_info = await erc1155.balanceOf(user, IDO_ID).invoke()
    assert execution_info.result.balance == uint(1000)

    # Claim tickets
    await mock_signer.send_transaction(owner, erc1155.contract_address, 'claimLotteryTickets', [*IDO_ID, 0])

    # Checks user balances match
    stake_info = await zk_pad_stake.balanceOf(user).invoke()
    execution_info2 = await erc1155.balanceOf(user, IDO_ID).invoke()
    nb_tickets = math.floor(pow(stake_info.result[0][0]/10**18, 3/5))
    assert execution_info2.result[0][0] == nb_tickets + 1000


@pytest.mark.asyncio
async def test_claim_twice_fail(full_factory):
    """Should revert when staker tries to claim tickets twice for one IDO"""
    erc1155, owner, _, receiver, ido, zk_pad_token, zk_pad_stake = full_factory

    IDO_ID = to_uint(0)
    user = owner.contract_address

    # Claim tickets
    await mock_signer.send_transaction(owner, erc1155.contract_address, 'claimLotteryTickets', [*IDO_ID, 0])

    # Attempt to claim again
    await assert_revert(mock_signer.send_transaction(owner, erc1155.contract_address, 'claimLotteryTickets', [
        *IDO_ID, 0]), "AstralyLotteryToken::Tickets already claimed")


@pytest.mark.asyncio
async def test_claim_twice_success(full_factory):
    """Should not revert when staker tries to claim tickets twice for two different IDOs"""
    erc1155, owner, _, receiver, ido, zk_pad_token, zk_pad_stake = full_factory

    IDO_ID1 = to_uint(0)
    IDO_ID2 = to_uint(1)
    user = owner.contract_address

    # Claim tickets for IDO 0
    await mock_signer.send_transaction(owner, erc1155.contract_address, 'claimLotteryTickets', [*IDO_ID1, 0])

    # Attempt to claim again for IDO 1
    await mock_signer.send_transaction(owner, erc1155.contract_address, 'claimLotteryTickets', [
        *IDO_ID2, 0])

# @pytest.mark.asyncio
# async def test_shhessh(full_factory) :
#     erc1155, owner, _, receiver, ido, zk_pad_token, zk_pad_stake = full_factory
#     balance=to_uint(100000000000000000000)
#     execution_info = await erc1155._balance_to_tickets(
#             balance
#         ).invoke()
#     print(execution_info.result[0][0])


@pytest.mark.asyncio
async def test_claim_no_tickets(full_factory):
    """Should revert when user tries to claim tickets without staking (no xZKP)"""
    erc1155, owner, user, receiver, ido, zk_pad_token, zk_pad_stake = full_factory

    IDO_ID = to_uint(0)

    # Checks user has no xZKP
    stake_info = await zk_pad_stake.balanceOf(user.contract_address).invoke()
    assert stake_info.result.balance == UINT_ZERO

    # Try to claim with a user with no xZKP tokens
    await assert_revert(mock_signer.send_transaction(user, erc1155.contract_address, 'claimLotteryTickets', [
        *IDO_ID, 0]), "AstralyLotteryToken::No tickets to claim")


@pytest.mark.asyncio
async def test_kyc(erc1155_factory):
    erc1155, owner, account, _, _ = erc1155_factory
    message = pedersen_hash(owner.contract_address, 0)
    sig = mock_signer.signer.sign(message)
    print(sig)
    await mock_signer.send_transaction(owner, erc1155.contract_address, 'checkKYCSignature', [len(sig), *sig])
