import asyncio

from pytoniq_core import Cell, Slice, StateInit, Builder, begin_cell, Address
from pytoniq import LiteClient, Contract, WalletV4R2, LiteBalancer
import hashlib

TON = "TON"
USDT = "USDT"
DECIMALS = "decimals"
ADDR = "address"
ADDR_STR = "address_str"

TOKEN_PRICE = "tokenPriceWithFee"
GOTTEN = "gottenAmount"
FEE = "feeProportion"


def debug_print(data):
    print(data)
    pass


class DedustClient:

    def __init__(self):
        # self.client = LiteClient.from_mainnet_config(6, trust_level=2)
        self.provider = LiteBalancer.from_mainnet_config(trust_level=2)

        self.TON_USDT_POOL = "EQA-X_yo3fzzbDbJ_0bzFWKqtRuZFIRa1sJsveZJ1YpViO3r"
        self.USDT = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
        self.TON = "EQDa4VOnTYlLvDJ0gZjNYm5PXfSmmtL6Vs6A_CZEtXCNICq_"

        self.USDT_DECIMAL = 10 ** 6
        self.TON_DECIMAL = 10 ** 9

        self.ton_usdt_pool_address = Address(self.TON_USDT_POOL)
        self.usdt_address = Address(self.USDT)
        self.ton_address = Address(self.TON)

        self.token_pretty_name = {
            self.TON: TON,
            self.USDT: USDT
        }

        self.token_dict = {
            TON: {
                DECIMALS: self.TON_DECIMAL,
                ADDR: self.ton_address,
                ADDR_STR: self.TON
            },
            USDT: {
                DECIMALS: self.USDT_DECIMAL,
                ADDR: self.usdt_address,
                ADDR_STR: self.USDT
            }
        }

        self.ton_usdt_contract = None

    async def start_client(self):
        # await self.client.connect()
        await self.provider.start_up()
        self.ton_usdt_contract = await Contract.from_address(self.provider, self.ton_usdt_pool_address)

    async def dispose(self):
        # await self.client.close()
        await self.provider.close_all()

    @staticmethod
    def hash_key_to_int(key: str) -> int:
        """
        when load_dict() used, keys of given dict are represented by hash. this function converts string to hash
        representation
        :return:
        """
        return int.from_bytes(hashlib.sha256(key.encode('utf-8')).digest(), 'big')

    def address_to_cell(self, address: Address) -> Cell:
        if address == self.ton_address:
            return begin_cell().store_uint(0b0000, 4).end_cell()
        else:
            return begin_cell() \
                .store_uint(0b0001, 4) \
                .store_int(address.wc, 8) \
                .store_bytes(address.hash_part) \
                .end_cell()

    def slice_to_address(self, src: Slice) -> Address:
        token_type = src.load_uint(4)
        if token_type == 0:
            return self.ton_address
        else:
            return Address((src.load_int(8), src.load_bytes(32)))

    async def get_reserves(self):
        result = await self.ton_usdt_contract.run_get_method("get_reserves")
        debug_print(f"TON reserves: {result[0]}; USDT reserves: {result[1]}")

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

    async def get_usdt_ton_price(self, given_token: str, given_amount: int):
        debug_print(f"get_usdt_ton_price({given_token}, {given_amount})")
        token_cell = self.address_to_cell(self.ton_address if given_token == self.TON else self.usdt_address)
        token_slice = Slice.from_cell(token_cell)
        result = await self.ton_usdt_contract.run_get_method("estimate_swap_out", [token_slice, given_amount])
        debug_print(f"raw result: {result}")
        gotten_token = self.slice_to_address(result[0])
        name = "TON" if gotten_token == self.ton_address else "USDT"
        decimal_gotten = self.TON_DECIMAL if gotten_token == self.ton_address else self.USDT_DECIMAL
        decimal_given = self.USDT_DECIMAL if gotten_token == self.ton_address else self.TON_DECIMAL
        debug_print(f"gotten token {name} in amount of {result[1] / decimal_gotten} and fee: "
                    f"{result[2] / decimal_given} in given token")
        # price of token without fee
        # (result[1] * decimal_given) /
        # (decimal_gotten * given_amount * (1 - result[2] / given_amount)),
        swap_data = {TOKEN_PRICE: (result[1] * decimal_given) /
                                  (decimal_gotten * given_amount),
                     GOTTEN: result[1] / decimal_gotten,
                     FEE: result[2] / given_amount
                     }
        debug_print(f"given d: {decimal_given}, gotten d {decimal_gotten}")
        debug_print(f"swap data: {swap_data}")
        return swap_data


async def get_price():
    print("start get_price method")
    dedust = DedustClient()
    await dedust.start_client()
    print("connected to client")

    # await dedust.get_reserves()
    print("connected to client, hard method run")
    await dedust.get_usdt_ton_price(dedust.TON, 7 * dedust.TON_DECIMAL)
    await dedust.get_usdt_jetton_data()

    await dedust.dispose()


if __name__ == '__main__':
    asyncio.run(get_price())
