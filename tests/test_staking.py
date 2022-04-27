import time

import pytest
from utils import (
    Signer, to_uint, from_uint, str_to_felt, MAX_UINT256, get_contract_def, cached_contract, assert_revert,
    assert_event_emitted, get_block_timestamp, set_block_timestamp
)
from starkware.starknet.definitions.error_codes import StarknetErrorCode
from starkware.starknet.testing.starknet import Starknet

INIT_SUPPLY = to_uint(1_000_000)
CAP = to_uint(1_000_000_000_000)
UINT_ONE = to_uint(1)
UINT_ZERO = to_uint(0)
NAME = str_to_felt("xZkPad")
SYMBOL = str_to_felt("xZKP")
DECIMALS = 18

owner = Signer(1234)


def advance_clock(starknet_state, num_seconds):
    set_block_timestamp(
        starknet_state, get_block_timestamp(
            starknet_state) + num_seconds
    )


def days_to_seconds(days: int):
    return days * 24 * 60 * 60


@pytest.fixture(scope='module')
async def get_starknet():
    starknet = await Starknet.empty()
    set_block_timestamp(starknet.state, int(time.time()))
    return starknet


@pytest.fixture(scope='module')
def contract_defs():
    account_def = get_contract_def('openzeppelin/account/Account.cairo')
    proxy_def = get_contract_def('openzeppelin/upgrades/Proxy.cairo')
    zk_pad_token_def = get_contract_def('ZkPadToken.cairo')
    zk_pad_stake_def = get_contract_def('ZkPadStaking.cairo')
    return account_def, proxy_def, zk_pad_token_def, zk_pad_stake_def


@pytest.fixture(scope='module')
async def contacts_init(contract_defs, get_starknet):
    starknet = get_starknet
    account_def, proxy_def, zk_pad_token_def, zk_pad_stake_def = contract_defs

    owner_account = await starknet.deploy(
        contract_def=account_def,
        constructor_calldata=[owner.public_key]
    )

    zk_pad_token = await starknet.deploy(
        contract_def=zk_pad_token_def,
        constructor_calldata=[
            str_to_felt("ZkPad"),
            str_to_felt("ZKP"),
            DECIMALS,
            *INIT_SUPPLY,
            owner_account.contract_address,  # recipient
            owner_account.contract_address,  # owner
            *CAP,
            123124
        ],
    )

    zk_pad_stake_implementation = await starknet.deploy(contract_def=zk_pad_stake_def)

    zk_pad_stake_proxy = await starknet.deploy(contract_def=proxy_def,
                                               constructor_calldata=[zk_pad_stake_implementation.contract_address])
    await owner.send_transaction(owner_account, zk_pad_stake_proxy.contract_address, "initializer", [
        NAME,
        SYMBOL,
        zk_pad_token.contract_address,
        owner_account.contract_address
    ])

    return (
        owner_account,
        zk_pad_token,
        zk_pad_stake_proxy
    )


@pytest.fixture
async def contracts_factory(contract_defs, contacts_init, get_starknet):
    account_def, proxy_def, zk_pad_token_def, zk_pad_stake_def = contract_defs
    owner_account, zk_pad_token, zk_pad_stake = contacts_init
    _state = get_starknet.state.copy()
    token = cached_contract(_state, zk_pad_token_def, zk_pad_token)
    stake = cached_contract(_state, zk_pad_stake_def, zk_pad_stake)
    owner_cached = cached_contract(_state, account_def, owner_account)

    async def deploy_contract_func(contract_name, constructor_calldata=None):
        contract_def = get_contract_def(contract_name)
        starknet = Starknet(_state)
        deployed_contract = await starknet.deploy(
            contract_def=contract_def,
            constructor_calldata=constructor_calldata)
        contract = cached_contract(_state, contract_def, deployed_contract)

        return contract

    async def deploy_account_func(public_key):
        account_def, _, _, _ = contract_defs
        starknet = Starknet(_state)
        deployed_account = await starknet.deploy(
            contract_def=account_def,
            constructor_calldata=[public_key]
        )
        cached_account = cached_contract(_state, account_def, deployed_account)
        return cached_account

    return token, stake, owner_cached, deploy_account_func, deploy_contract_func, _state


@pytest.mark.asyncio
@pytest.mark.order(1)
async def test_init(contracts_factory):
    zk_pad_token, zk_pad_staking, _, _, _, _ = contracts_factory
    assert (await zk_pad_staking.name().invoke()).result.name == NAME
    assert (await zk_pad_staking.symbol().invoke()).result.symbol == SYMBOL
    assert (await zk_pad_staking.decimals().invoke()).result.decimals == 18
    assert (await zk_pad_staking.asset().invoke()).result.assetTokenAddress == zk_pad_token.contract_address
    assert (await zk_pad_staking.totalAssets().invoke()).result.totalManagedAssets == to_uint(0)


async def cache_on_state(state, contract_def, deployment_func):
    deployment = await deployment_func
    return cached_contract(state, contract_def, deployment)


@pytest.mark.asyncio
async def test_proxy_upgrade(contract_defs, contacts_init):
    account_def, proxy_def, _, zk_pad_stake_def = contract_defs
    erc20_def = get_contract_def('openzeppelin/token/erc20/ERC20.cairo')
    starknet = await Starknet.empty()
    user = Signer(123)
    owner_account = await cache_on_state(starknet.state, account_def, starknet.deploy(
        contract_def=account_def,
        constructor_calldata=[owner.public_key]
    ))
    user_account = await cache_on_state(starknet.state, account_def, starknet.deploy(
        contract_def=account_def,
        constructor_calldata=[user.public_key]
    ))

    erc20_contract = await cache_on_state(
        starknet.state, erc20_def, starknet.deploy(contract_def=erc20_def, constructor_calldata=[
            str_to_felt("ZkPad"),
            str_to_felt("ZKP"),
            DECIMALS,
            *INIT_SUPPLY,
            owner_account.contract_address
        ]))

    zk_pad_stake_implementation = await cache_on_state(
        starknet.state, zk_pad_stake_def, starknet.deploy(contract_def=zk_pad_stake_def))

    zk_pad_stake_proxy = await cache_on_state(starknet.state, zk_pad_stake_def, starknet.deploy(contract_def=proxy_def,
                                                                                                constructor_calldata=[
                                                                                                    zk_pad_stake_implementation.contract_address]))

    await owner.send_transaction(owner_account, zk_pad_stake_proxy.contract_address, "initializer", [
        NAME,
        SYMBOL,
        erc20_contract.contract_address,
        owner_account.contract_address
    ])

    current_zk_pad_stake_implementation_address = (
        await user.send_transaction(user_account, zk_pad_stake_proxy.contract_address, "getImplementation",
                                    [])).result.response[0]
    assert zk_pad_stake_implementation.contract_address == current_zk_pad_stake_implementation_address

    new_zk_pad_implementation = await cache_on_state(
        starknet.state, zk_pad_stake_def, starknet.deploy(contract_def=zk_pad_stake_def))
    await assert_revert(
        user.send_transaction(
            user_account, zk_pad_stake_proxy.contract_address, "upgrade",
            [new_zk_pad_implementation.contract_address]),
        "Proxy: caller is not admin",
        StarknetErrorCode.TRANSACTION_FAILED
    )
    await owner.send_transaction(owner_account, zk_pad_stake_proxy.contract_address, "upgrade",
                                 [new_zk_pad_implementation.contract_address])
    current_zk_pad_stake_implementation_address = (
        await user.send_transaction(user_account, zk_pad_stake_proxy.contract_address, "getImplementation",
                                    [])).result.response[0]
    assert new_zk_pad_implementation.contract_address == current_zk_pad_stake_implementation_address


@pytest.mark.asyncio
async def test_conversions(contract_defs, contracts_factory):
    _, zk_pad_staking, _, _, _, _ = contracts_factory
    shares = to_uint(1000)
    assets = to_uint(1000)

    # convertToAssets(convertToShares(assets)) == assets
    converted_shares = (await zk_pad_staking.convertToShares(assets).invoke()).result.shares
    converted_assets = (await zk_pad_staking.convertToAssets(converted_shares).invoke()).result.assets
    assert assets == converted_assets

    # convertToShares(convertToAssets(shares)) == shares
    converted_assets = (await zk_pad_staking.convertToAssets(shares).invoke()).result.assets
    converted_shares = (await zk_pad_staking.convertToShares(converted_assets).invoke()).result.shares
    assert shares == converted_shares


@pytest.mark.asyncio
async def test_deposit_redeem_flow(contracts_factory):
    zk_pad_token, zk_pad_staking, owner_account, deploy_account_func, _, starknet_state = contracts_factory

    user1 = Signer(2345)
    user1_account = await deploy_account_func(user1.public_key)

    await owner.send_transaction(
        owner_account,
        zk_pad_token.contract_address,
        "mint",
        [user1_account.contract_address, *to_uint(100_000)],
    )
    assert (
               await zk_pad_token.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(100_000)

    assert (
               await zk_pad_staking.maxDeposit(user1_account.contract_address).invoke()
           ).result.maxAssets == MAX_UINT256

    # max approve
    await user1.send_transaction(
        user1_account,
        zk_pad_token.contract_address,
        "approve",
        [zk_pad_staking.contract_address, *MAX_UINT256],
    )

    amount = to_uint(10_000)

    # deposit asset tokens to the vault, get shares
    tx = await user1.send_transaction(
        user1_account,
        zk_pad_staking.contract_address,
        "deposit",
        [*amount, user1_account.contract_address],
    )
    assert (
               await zk_pad_staking.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == amount
    assert_event_emitted(tx, zk_pad_staking.contract_address, "Deposit", data=[
        user1_account.contract_address,
        user1_account.contract_address,
        *amount,
        *tx.result.response
    ])
    assert (
               await zk_pad_token.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(90_000)

    advance_clock(starknet_state, days_to_seconds(365) + 1)
    # redeem vault shares, get back assets
    tx = await user1.send_transaction(
        user1_account,
        zk_pad_staking.contract_address,
        "redeem",
        [*amount, user1_account.contract_address,
         user1_account.contract_address],
    )

    assert (
               await zk_pad_staking.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(0)
    assert_event_emitted(tx, zk_pad_staking.contract_address, "Withdraw", data=[
        user1_account.contract_address,
        user1_account.contract_address,
        user1_account.contract_address,
        *tx.result.response,
        *amount,
    ])
    assert (
               await zk_pad_token.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(100_000)


@pytest.mark.asyncio
async def test_deposit_for_time_and_redeem_flow(contracts_factory):
    zk_pad_token, zk_pad_staking, owner_account, deploy_account_func, _, starknet_state = contracts_factory

    user1 = Signer(2345)
    user1_account = await deploy_account_func(user1.public_key)

    await owner.send_transaction(
        owner_account,
        zk_pad_token.contract_address,
        "mint",
        [user1_account.contract_address, *to_uint(100_000)],
    )
    assert (
               await zk_pad_token.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(100_000)

    assert (
               await zk_pad_staking.maxDeposit(user1_account.contract_address).invoke()
           ).result.maxAssets == MAX_UINT256

    # max approve
    await user1.send_transaction(
        user1_account,
        zk_pad_token.contract_address,
        "approve",
        [zk_pad_staking.contract_address, *MAX_UINT256],
    )

    amount = to_uint(10_000)
    current_timestamp = get_block_timestamp(starknet_state)

    # deposit asset tokens to the vault, get shares
    tx = await user1.send_transaction(
        user1_account,
        zk_pad_staking.contract_address,
        "depositForTime",
        [*amount, user1_account.contract_address, 365 * 2],
    )
    assert (
               await zk_pad_staking.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == amount

    set_block_timestamp(
        starknet_state, current_timestamp + days_to_seconds(365 * 2) + 1)
    tx = await user1.send_transaction(
        user1_account,
        zk_pad_staking.contract_address,
        "redeem",
        [*amount, user1_account.contract_address,
         user1_account.contract_address],
    )

    assert (
               await zk_pad_staking.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(0)
    assert_event_emitted(tx, zk_pad_staking.contract_address, "Withdraw", data=[
        user1_account.contract_address,
        user1_account.contract_address,
        user1_account.contract_address,
        *tx.result.response,
        *amount,
    ])
    assert (
               await zk_pad_token.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(100_000)


@pytest.mark.asyncio
async def test_mint_withdraw_flow(contracts_factory):
    zk_pad_token, zk_pad_staking, owner_account, deploy_account_func, _, starknet_state = contracts_factory

    user1 = Signer(2345)
    user1_account = await deploy_account_func(user1.public_key)

    await owner.send_transaction(
        owner_account,
        zk_pad_token.contract_address,
        "mint",
        [user1_account.contract_address, *to_uint(100_000)],
    )
    assert (
               await zk_pad_token.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(100_000)

    assert (
               await zk_pad_staking.maxMint(user1_account.contract_address).invoke()
           ).result.maxShares == MAX_UINT256
    assert (
               await zk_pad_staking.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(0)

    # max approve
    await user1.send_transaction(
        user1_account, zk_pad_token.contract_address, "approve", [
            zk_pad_staking.contract_address, *MAX_UINT256]
    )

    amount = to_uint(10_000)

    # mint shares for assets
    tx = await user1.send_transaction(
        user1_account,
        zk_pad_staking.contract_address,
        "mint",
        [*amount, user1_account.contract_address],
    )

    assert (
               await zk_pad_staking.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == amount
    assert_event_emitted(tx, zk_pad_staking.contract_address, "Deposit", data=[
        user1_account.contract_address,
        user1_account.contract_address,
        *amount,
        *tx.result.response
    ])

    assert (
               await zk_pad_token.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(90_000)
    advance_clock(starknet_state, days_to_seconds(365) + 1)
    # withdraw shares, get back assets
    tx = await user1.send_transaction(
        user1_account,
        zk_pad_staking.contract_address,
        "withdraw",
        [*amount, user1_account.contract_address,
         user1_account.contract_address],
    )

    assert (
               await zk_pad_staking.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(0)

    assert_event_emitted(tx, zk_pad_staking.contract_address, "Withdraw", data=[
        user1_account.contract_address,
        user1_account.contract_address,
        user1_account.contract_address,
        *amount,
        *tx.result.response,
    ])
    assert (
               await zk_pad_token.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(100_000)


@pytest.mark.asyncio
async def test_allowances(contracts_factory):
    zk_pad_token, zk_pad_staking, owner_account, deploy_account_func, _, starknet_state = contracts_factory

    user1 = Signer(2345)
    user1_account = await deploy_account_func(user1.public_key)

    user2 = Signer(3456)
    user2_account = await deploy_account_func(user2.public_key)

    user3 = Signer(4567)
    user3_account = await deploy_account_func(user3.public_key)

    amount = to_uint(100_000)

    # mint assets to user1
    await owner.send_transaction(
        owner_account,
        zk_pad_token.contract_address,
        "mint",
        [user1_account.contract_address, *amount],
    )
    assert (await zk_pad_token.balanceOf(user1_account.contract_address).invoke()).result.balance == amount

    # have user1 get shares in vault
    await user1.send_transaction(
        user1_account, zk_pad_token.contract_address, "approve", [
            zk_pad_staking.contract_address, *MAX_UINT256]
    )
    await user1.send_transaction(
        user1_account, zk_pad_staking.contract_address, "mint", [
            *amount, user1_account.contract_address]
    )

    advance_clock(starknet_state, days_to_seconds(365) + 1)
    # max approve user2
    await user1.send_transaction(
        user1_account,
        zk_pad_staking.contract_address,
        "approve",
        [user2_account.contract_address, *MAX_UINT256],
    )

    # approve user3 for 10K
    await user1.send_transaction(
        user1_account,
        zk_pad_staking.contract_address,
        "approve",
        [user3_account.contract_address, *to_uint(10_000)],
    )

    #
    # have user2 withdraw 50K assets from user1 vault position
    #
    assert (
               await zk_pad_staking.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(100_000)
    assert (
               await zk_pad_staking.balanceOf(user2_account.contract_address).invoke()
           ).result.balance == to_uint(0)
    assert (
               await zk_pad_token.balanceOf(user2_account.contract_address).invoke()
           ).result.balance == to_uint(0)

    await user2.send_transaction(
        user2_account,
        zk_pad_staking.contract_address,
        "withdraw",
        [*to_uint(50_000), user2_account.contract_address,
         user1_account.contract_address],
    )

    assert (
               await zk_pad_staking.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(50_000)
    assert (
               await zk_pad_staking.balanceOf(user2_account.contract_address).invoke()
           ).result.balance == to_uint(0)
    assert (
               await zk_pad_token.balanceOf(user2_account.contract_address).invoke()
           ).result.balance == to_uint(50_000)
    assert (
               await zk_pad_staking.allowance(
                   user1_account.contract_address, user2_account.contract_address
               ).invoke()
           ).result.remaining == MAX_UINT256

    #
    # have user3 withdraw 10K assets from user1 vault position
    #
    assert (
               await zk_pad_staking.balanceOf(user3_account.contract_address).invoke()
           ).result.balance == to_uint(0)
    assert (
               await zk_pad_token.balanceOf(user3_account.contract_address).invoke()
           ).result.balance == to_uint(0)

    await user3.send_transaction(
        user3_account,
        zk_pad_staking.contract_address,
        "withdraw",
        [*to_uint(10_000), user3_account.contract_address,
         user1_account.contract_address],
    )

    assert (
               await zk_pad_staking.balanceOf(user1_account.contract_address).invoke()
           ).result.balance == to_uint(40_000)
    assert (
               await zk_pad_staking.balanceOf(user3_account.contract_address).invoke()
           ).result.balance == to_uint(0)
    assert (
               await zk_pad_token.balanceOf(user3_account.contract_address).invoke()
           ).result.balance == to_uint(10_000)
    assert (
               await zk_pad_staking.allowance(
                   user1_account.contract_address, user3_account.contract_address
               ).invoke()
           ).result.remaining == to_uint(0)

    # user3 tries withdrawing again, has insufficient allowance, :burn:
    await assert_revert(user3.send_transaction(
        user3_account,
        zk_pad_staking.contract_address,
        "withdraw",
        [*to_uint(1), user3_account.contract_address,
         user1_account.contract_address],
    ), error_code=StarknetErrorCode.TRANSACTION_FAILED)


@pytest.mark.asyncio
async def test_permissions(contracts_factory):
    zk_pad_token, zk_pad_staking, owner_account, deploy_account_func, _, _ = contracts_factory
    user1 = Signer(2345)
    user1_account = await deploy_account_func(user1.public_key)

    await assert_revert(
        user1.send_transaction(
            user1_account, zk_pad_staking.contract_address, "addWhitelistedToken", [123, 123]),
        "Ownable: caller is not the owner")

    await owner.send_transaction(owner_account, zk_pad_staking.contract_address, "addWhitelistedToken", [123, 123])

    await assert_revert(
        user1.send_transaction(
            user1_account, zk_pad_staking.contract_address, "removeWhitelistedToken", [123]),
        "Ownable: caller is not the owner")

    await assert_revert(user1.send_transaction(user1_account, zk_pad_staking.contract_address, "setStakeBoost", [25]))


@pytest.mark.asyncio
async def test_deposit_lp(contracts_factory):
    zk_pad_token, zk_pad_staking, owner_account, deploy_account_func, deploy_contract_func, starknet_state = contracts_factory

    user1 = Signer(2345)
    user1_account = await deploy_account_func(user1.public_key)

    deposit_amount = 10_000
    boost_value = int(2.5 * 10)
    initial_lock_time = 365  # days

    mint_calculator = await deploy_contract_func("tests/mocks/test_mint_calculator.cairo")
    mock_lp_token = await deploy_contract_func("tests/mocks/test_erc20.cairo", [
        str_to_felt("ZKP ETH LP"),
        str_to_felt("ZKP/ETH"),
        DECIMALS,
        *to_uint(deposit_amount * 2),
        user1_account.contract_address,
        owner_account.contract_address
    ])

    # just to have balance for withdraw after earn interest
    await user1.send_transaction(
        user1_account,
        mock_lp_token.contract_address,
        "transfer",
        [zk_pad_staking.contract_address, *to_uint(deposit_amount)]
    )  # TODO: Remove after implementing the withdraw from investment strategies function

    await owner.send_transaction(owner_account, zk_pad_staking.contract_address, "setStakeBoost", [boost_value])

    await owner.send_transaction(owner_account, zk_pad_staking.contract_address, "addWhitelistedToken", [
        mock_lp_token.contract_address,
        mint_calculator.contract_address
    ])

    assert (
               await zk_pad_staking.isTokenWhitelisted(mock_lp_token.contract_address).call()
           ).result.res == 1

    assert (
               await mock_lp_token.balanceOf(user1_account.contract_address).call()
           ).result.balance == to_uint(deposit_amount)
    zkp_assets_value = (
        await mint_calculator.getAmountToMint(to_uint(deposit_amount)).call()
    ).result.amount
    assert zkp_assets_value == to_uint(deposit_amount)  # mock tokens
    converted_to_shares = (await zk_pad_staking.previewDeposit(zkp_assets_value).call()).result.shares

    current_boost_value = (await zk_pad_staking.getCurrentBoostValue().call()).result.res
    assert boost_value == current_boost_value

    expect_to_mint = int(current_boost_value * ((from_uint(converted_to_shares) * initial_lock_time) / 730) / 10)
    preview_deposit = (
        await zk_pad_staking.previewDepositLP(mock_lp_token.contract_address, to_uint(deposit_amount),
                                              initial_lock_time).call()
    ).result.shares
    assert preview_deposit == to_uint(expect_to_mint)

    await user1.send_transaction(
        user1_account,
        mock_lp_token.contract_address,
        "approve",
        [zk_pad_staking.contract_address, *to_uint(deposit_amount)]
    )

    vault_balance_before_deposit = (
        await mock_lp_token.balanceOf(zk_pad_staking.contract_address).call()).result.balance
    timestamp = get_block_timestamp(starknet_state)

    await user1.send_transaction(
        user1_account,
        zk_pad_staking.contract_address,
        "depositLP",
        [mock_lp_token.contract_address,
         *to_uint(deposit_amount), user1_account.contract_address, initial_lock_time]
    )
    user_xzkp_balance = (await zk_pad_staking.balanceOf(user1_account.contract_address).call()).result.balance
    assert user_xzkp_balance == to_uint(expect_to_mint)

    vault_balance_after_deposit = (await mock_lp_token.balanceOf(zk_pad_staking.contract_address).call()).result.balance
    assert from_uint(vault_balance_after_deposit) == from_uint(
        vault_balance_before_deposit) + deposit_amount

    user_stake_info = (await zk_pad_staking.getUserStakeInfo(user1_account.contract_address).call()).result

    assert user_stake_info.unlock_time == timestamp + days_to_seconds(365)
    assert mock_lp_token.contract_address in user_stake_info.tokens

    await assert_revert(user1.send_transaction(user1_account, zk_pad_staking.contract_address, "redeemLP", [
        mock_lp_token.contract_address, *user_xzkp_balance, user1_account.contract_address,
        user1_account.contract_address]),
                        reverted_with="lower than deposit unlock time")

    set_block_timestamp(starknet_state, user_stake_info.unlock_time + 1)

    vault_balance_before_redeem = (await mock_lp_token.balanceOf(zk_pad_staking.contract_address).call()).result.balance

    redeem_tx = await user1.send_transaction(user1_account, zk_pad_staking.contract_address, "redeemLP", [
        mock_lp_token.contract_address, *user_xzkp_balance, user1_account.contract_address,
        user1_account.contract_address])

    vault_balance_after_redeem = (await mock_lp_token.balanceOf(zk_pad_staking.contract_address).call()).result.balance

    assert from_uint(vault_balance_before_redeem) == from_uint(
        vault_balance_after_redeem) + from_uint(preview_deposit)

    assert_event_emitted(redeem_tx, zk_pad_staking.contract_address, "Redeem_lp", [
        user1_account.contract_address,
        user1_account.contract_address,
        mock_lp_token.contract_address,
        *preview_deposit,
        *preview_deposit
    ])

    assert (
               await mock_lp_token.balanceOf(user1_account.contract_address).call()
           ).result.balance == preview_deposit
