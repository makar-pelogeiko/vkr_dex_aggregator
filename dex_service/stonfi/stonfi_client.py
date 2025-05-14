import asyncio
import typing

from pytoniq_core import Cell, Slice, StateInit, Builder, begin_cell, Address
from pytoniq import LiteClient, Contract, WalletV4R2, LiteBalancer
import hashlib

TON = "TON"
USDT = "USDT"
DECIMALS = "decimals"
ADDR = "address"
ADDR_STR = "address_str"
STONFI_WALLET = "stonfi_wallet"

TOKEN_PRICE = "tokenPriceWithFee"
GOTTEN = "gottenAmount"
FEE = "feeProportion"


def debug_print(data):
    print(data)
    pass


class StonfiClient:

    def __init__(self):
        self.provider = LiteBalancer.from_mainnet_config(trust_level=2)

        self.TON_USDT_POOL = "EQD8TJ8xEWB1SpnRE4d89YO3jl0W0EiBnNS4IBaHaUmdfizE"
        self.USDT = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
        self.TON = "EQDa4VOnTYlLvDJ0gZjNYm5PXfSmmtL6Vs6A_CZEtXCNICq_"

        self.STONFI_USDT_ADDR = "EQBO7JIbnU1WoNlGdgFtScJrObHXkBp-FT5mAz8UagiG9KQR"
        self.STONFI_TON_ADDR = "EQARULUYsmJq1RiZ-YiH-IJLcAZUVkVff-KBPwEmmaQGH6aC"

        self.USDT_DECIMAL = 10 ** 6
        self.TON_DECIMAL = 10 ** 9

        self.ton_usdt_pool_address = Address(self.TON_USDT_POOL)
        self.usdt_address = Address(self.USDT)
        self.ton_address = Address(self.TON)

        self.stonfi_usdt_address = Address(self.STONFI_USDT_ADDR)
        self.stonfi_ton_address = Address(self.STONFI_TON_ADDR)

        self.token_pretty_name = {
            self.TON: TON,
            self.STONFI_TON_ADDR: TON,
            self.USDT: USDT,
            self.STONFI_USDT_ADDR: USDT
        }

        self.token_to_stonfi_address = {
            TON: self.stonfi_ton_address,
            USDT: self.stonfi_usdt_address
        }

        self.token_dict = {
            TON: {
                DECIMALS: self.TON_DECIMAL,
                ADDR: self.ton_address,
                ADDR_STR: self.TON,
                STONFI_WALLET: self.stonfi_ton_address

            },
            USDT: {
                DECIMALS: self.USDT_DECIMAL,
                ADDR: self.usdt_address,
                ADDR_STR: self.USDT,
                STONFI_WALLET: self.stonfi_usdt_address
            }
        }

        self.ton_usdt_contract = None

    async def start_client(self):
        await self.provider.start_up()
        self.ton_usdt_contract = await Contract.from_address(self.provider, self.ton_usdt_pool_address)

    async def dispose(self):
        await self.provider.close_all()

    @staticmethod
    def hash_key_to_int(key: str) -> int:
        """
        when load_dict() used, keys of given dict are represented by hash. this function converts string to hash
        representation
        :return:
        """
        return int.from_bytes(hashlib.sha256(key.encode('utf-8')).digest(), 'big')

    async def get_usdt_jetton_data(self) -> dict:
        result = await self.provider.run_get_method(self.usdt_address, "get_jetton_data", [])
        metadata = result[3].copy()
        dp = metadata.begin_parse()
        dp.load_uint(8)
        data_dict = dp.load_dict(256)
        keys_hashed = list(data_dict.keys())
        expected_keys = {self.hash_key_to_int("uri"): "uri", self.hash_key_to_int("decimals"): "decimals"}
        parsed_dict = {}
        for k in keys_hashed:
            if k in expected_keys.keys():
                parsed_dict[expected_keys[k]] = data_dict[k].load_snake_string()[1:]
            else:
                parsed_dict[k] = data_dict[k].load_snake_string()[1:]
        debug_print(f"usdt metadata dict: {parsed_dict}")
        return parsed_dict

    def convert_token_to_address_str(self, token: str) -> Address:
        if token.upper() in self.token_dict:
            return self.token_dict[token.upper()][STONFI_WALLET]
        elif token in self.token_pretty_name:
            return self.token_dict[self.token_pretty_name[token]][STONFI_WALLET]
        else:
            debug_print(f"token not found: {token}")
            return Address(token)

    def convert_token_to_short_name(self, token: typing.Union[str, Address]) -> str:
        if token.upper() in self.token_dict:
            return token.upper()
        elif token in self.token_pretty_name:
            return self.token_pretty_name[token]
        elif isinstance(token, Address) and token.to_str() in self.token_pretty_name:
            return self.token_pretty_name[token.to_str()]
        else:
            raise RuntimeError(f"can not find token: {token}")

    async def get_stonfi_token_price(self, given_token: str, given_amount: int):
        """
        [296700997, 296998, 0] -> fee in received token: 296998 / 296700997 = 0.001001001
        :return: swap data
        """
        debug_print(f"get_stonfi_token_price({given_token}, {given_amount:,})")
        address_token = self.convert_token_to_address_str(given_token)
        address_cell = begin_cell().store_address(address_token).end_cell()
        address_slice = Slice.from_cell(address_cell)
        result = await self.ton_usdt_contract.run_get_method("get_expected_outputs", [given_amount, address_slice])
        debug_print(f"result: {result}")
        token_in = self.convert_token_to_short_name(given_token)
        token_out = USDT if token_in == TON else TON
        dec_in = self.token_dict[token_in][DECIMALS]
        dec_out = self.token_dict[token_out][DECIMALS]
        debug_print(f"token_in: {token_in}; dec_in: {dec_in:,}; token_out: {token_out}; dec_out: {dec_out:,} || address_token: {address_token}")
        price_with_fee = (result[0] * dec_in) / (given_amount * dec_out)
        swap_data = {
            TOKEN_PRICE: price_with_fee,
            GOTTEN: result[0] / dec_out,
            FEE: (result[1] + result[2]) / result[0]
        }
        debug_print(f"swap data: {swap_data}")
        return swap_data

    async def get_stonfi_pool_data(self):
        result = await self.ton_usdt_contract.run_get_method("get_pool_data", [])
        print(result)
        print(f"address 1: {result[2].load_address()}; address 2: {result[3].load_address()}")
        return result


async def get_price():
    print("start get_price method")
    stonfi = StonfiClient()
    await stonfi.start_client()
    # print("connected to client")
    # await stonfi.get_stonfi_pool_data()
    # await dedust.get_reserves()
    print("connected to client, hard method run")
    await stonfi.get_stonfi_token_price(stonfi.TON, 1 * stonfi.TON_DECIMAL)
    # await stonfi.get_usdt_jetton_data()

    await stonfi.dispose()


if __name__ == '__main__':
    asyncio.run(get_price())
