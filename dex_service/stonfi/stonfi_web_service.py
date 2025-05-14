from fastapi import FastAPI
from stonfi_client import StonfiClient, ADDR_STR, TOKEN_PRICE, GOTTEN, TON, USDT, DECIMALS, FEE
import redis
import consul
import socket
import os
import uuid
import time

app = FastAPI()
stonfi = StonfiClient()
SERVICE_NAME = "dex-stonfi"
SERVICE_ID = f"{SERVICE_NAME}-{uuid.uuid1()}"
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", default=8100))
CONSUL_HOST = os.environ.get("CONSUL_HOST", default="localhost")
CONSUL_PORT = int(os.environ.get("CONSUL_PORT", default=8500))
REDIS_HOST = os.environ.get("REDIS_HOST", default="localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", default=6379))
CACHE_SEC = float(os.environ.get("CACHE_SEC", default=0.1))

CONSUL_CLIENT = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)

REDIS_CLIENT = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

PAIRS = ["ton-usdt"]

stonfi_url = "https://app.ston.fi/swap?chartVisible=false"
URL_TOKENS_NOTATION = {
    TON: "TON",
    USDT: "USD₮"
}


class FastDict:
    def __init__(self, max_time_to_hold=0.1):
        self.data = {}
        self.max_time_to_hold = max_time_to_hold

    def put_data(self, key, value):
        self.data[key] = (time.time(), value)

    def get_data(self, key, max_time=None):
        max_time = self.max_time_to_hold if max_time is None else max_time
        if key not in self.data:
            return None
        stamp, value = self.data[key]
        if time.time() <= max_time + stamp:
            return value
        else:
            self.data.pop(key, 1)
            return None


fast_price = FastDict(CACHE_SEC)


def get_ready_token_name(token: str) -> str | None:
    if token in stonfi.token_pretty_name:
        return token
    if token.upper() in stonfi.token_dict:
        return stonfi.token_dict[token.upper()][ADDR_STR]
    print(f"BAD token: {token}")
    return None


@app.on_event("startup")
async def startup_event():
    await stonfi.start_client()

    service_host = socket.gethostbyname(socket.gethostname())
    print(f"service_host: {service_host}; for health check: http://{service_host}:{SERVICE_PORT}/health")
    check = consul.Check.http(url=f"http://{service_host}:{SERVICE_PORT}/health", interval="20s", deregister="45s")

    try:
        CONSUL_CLIENT.agent.service.register(
            name=SERVICE_NAME,
            service_id=SERVICE_ID,
            address=service_host,
            port=SERVICE_PORT,
            check=check
        )
        print(f"Registered '{SERVICE_NAME}' in Consul at {CONSUL_HOST}:{CONSUL_PORT}")
        print(f"SERVICE_ID: {SERVICE_ID}")
    except Exception as e:
        print(f"Failed to register service in Consul: {e}")

    for pair in PAIRS:
        REDIS_CLIENT.sadd(pair, SERVICE_NAME)
        print(f"redis pair created: {pair}, value: {SERVICE_NAME}")


@app.on_event("shutdown")
def deregister_service():
    try:
        CONSUL_CLIENT.agent.service.deregister(SERVICE_ID)
        print(f"Deregistered '{SERVICE_NAME}' from Consul")
    except Exception as e:
        print(f"Failed to deregister service from Consul: {e}")
    REDIS_CLIENT.close()


@app.get("/test")
async def get_test_method():
    return "test string"


@app.get("/test-pojo")
async def get_test_pojo_method():
    return {"result": f"test from {SERVICE_ID} ", "id": 1}


@app.get("/health")
async def health_check():
    return {"status": f"ok {SERVICE_ID}"}


@app.get("/redis/{key_r}/{val_r}")
async def get_to_redis(key_r: str, val_r: str):
    print(f"set key = {key_r}, val = {val_r}")
    REDIS_CLIENT.sadd(key_r, val_r)
    return "ok"


@app.get("/redis/{key_r}")
async def get_from_redis(key_r: str):
    print("get by key")
    r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    v = r.smembers(key_r)
    print(f"value: {v}")
    r.close()
    return f"value: {v}"


@app.get("/swap/{source_token}/{destination_token}/{amount}")
async def get_swap_data(source_token: str, destination_token: str, amount: int):
    src_ready = get_ready_token_name(source_token)
    dest_ready = get_ready_token_name(destination_token)
    if src_ready is None or dest_ready is None or amount <= 0:
        return {"result": {}, "status": "bad input"}

    ft_short_name = stonfi.convert_token_to_short_name(source_token)
    key = src_ready + '-=-' + dest_ready
    curr_price = fast_price.get_data(key)
    result = None
    if curr_price is not None:
        result = {TOKEN_PRICE: curr_price[0],
                  GOTTEN: curr_price[0] * amount / stonfi.token_dict[ft_short_name][DECIMALS],
                  FEE: curr_price[1]
                  }
    else:
        result = await stonfi.get_stonfi_token_price(src_ready, amount)
        fast_price.put_data(key, (result[TOKEN_PRICE], result[FEE]))
    # result = await stonfi.get_stonfi_token_price(src_ready, amount)

    ft = URL_TOKENS_NOTATION[ft_short_name]
    tt = URL_TOKENS_NOTATION[stonfi.convert_token_to_short_name(destination_token)]
    result["exchangeURL"] = stonfi_url
    result[
        "currentURL"] = f"{stonfi_url}&ft={ft}&tt={tt}&fa=%22{amount / stonfi.token_dict[ft_short_name][DECIMALS]}%22"
    print(f"response: tokenPriceWithFee= {result[TOKEN_PRICE]}; gottenAmount={result[GOTTEN]}")
    # https://app.ston.fi/swap?chartVisible=false&ft=TON&tt=USD%E2%82%AE&fa="1"
    # https://app.ston.fi/swap?chartVisible=false&ft=TON&tt=USD%E2%82%AE&fa=%221%22
    return result
